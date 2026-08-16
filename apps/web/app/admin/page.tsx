"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ApiError } from "@/lib/api";
import {
  AdminInvite,
  AdminTenantCreated,
  AdminTenantRow,
  FEATURE_FLAGS,
  admin,
  purgeTenant,
  resumeTenant,
} from "@/lib/admin";
import { InviteLink, NewWorkspace } from "./NewWorkspace";
import { ModulesEditor } from "./ModulesEditor";
import { EditWorkspace, SuspendWorkspace } from "./EditWorkspace";
import { CatalogueEditor } from "./CatalogueEditor";
import { DialogProvider, useAsk } from "@/components/ui";

const fmtDate = (iso: string | null) =>
  iso ? new Date(iso).toLocaleDateString("en-GB") : "—";

/** /admin sits outside the app layout, so it mounts its own dialog host. */
export default function AdminConsolePage() {
  return (
    <DialogProvider>
      <AdminConsole />
    </DialogProvider>
  );
}

function AdminConsole() {
  const router = useRouter();
  const ask = useAsk();
  const [rows, setRows] = useState<AdminTenantRow[] | null>(null);
  const [denied, setDenied] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [created, setCreated] = useState<AdminTenantCreated | null>(null);
  const [reissued, setReissued] = useState<{ name: string; invite: AdminInvite } | null>(null);
  const [editingModules, setEditingModules] = useState<AdminTenantRow | null>(null);
  const [editing, setEditing] = useState<AdminTenantRow | null>(null);
  const [suspending, setSuspending] = useState<AdminTenantRow | null>(null);

  const refresh = useCallback(async () => {
    try {
      setRows(await admin<AdminTenantRow[]>("/admin/tenants"));
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) router.push("/login");
      else if (err instanceof ApiError && err.status === 403) setDenied(true);
      else setError(err instanceof Error ? err.message : String(err));
    }
  }, [router]);

  useEffect(() => {
    // Fetch-on-mount: every setState in refresh happens after an await.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    refresh();
  }, [refresh]);

  async function reissueInvite(t: AdminTenantRow) {
    const email = await ask.text({
      title: `Owner invite for ${t.name}`,
      body: "The new invite is live as soon as you send it. Any earlier owner invite for this workspace stops working.",
      label: "Send to",
      inputType: "email",
      placeholder: "owner@client.co.uk",
      confirmLabel: "Create invite",
    });
    if (!email) return;
    try {
      const invite = await admin<AdminInvite>(`/admin/tenants/${t.id}/owner-invite`, {
        method: "POST",
        body: JSON.stringify({ email }),
      });
      // The invite is live from here. Hand it over on screen rather than
      // copying it silently: a clipboard rejection used to land in the catch
      // below and discard the only copy of a token that had really been made.
      setReissued({ name: t.name, invite });
      refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Invite failed — try again.");
    }
  }

  // Resume needs no confirmation — it only restores access, and the reason
  // that justified the suspension is already on screen.
  async function resume(t: AdminTenantRow) {
    try {
      await resumeTenant(t.id);
      refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not resume — try again.");
    }
  }

  // Purge is the irreversible second step: it takes the workspace's exact
  // name. The dialog keeps the confirm button inert until the name matches, so
  // a mistype cannot be submitted; the API still checks it as the real gate.
  async function purge(t: AdminTenantRow) {
    const confirmed = await ask.confirmTyped({
      title: `Delete ${t.name} for good`,
      body: (
        <>
          Its files, its model key and every row it owns go with it. This cannot be undone, and
          there is no backup to restore from.
        </>
      ),
      label: `Type “${t.name}” to confirm`,
      expected: t.name,
      confirmLabel: "Delete for good",
      tone: "danger",
    });
    if (!confirmed) return;
    try {
      await purgeTenant(t.id, t.name);
      refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Purge failed — nothing was deleted.");
    }
  }

  if (denied)
    return (
      <main className="mx-auto max-w-2xl p-10">
        <p className="rounded-card border border-edge bg-surface p-6 text-sm text-ink-muted">
          This console is for the platform operator.
        </p>
      </main>
    );

  return (
    <main className="min-h-screen">
      <div className="mx-auto max-w-6xl p-6">
        <header className="mb-6 flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="data text-ink-faint uppercase">Flowgrid</p>
            <h1 className="font-display text-[26px] font-medium tracking-[-0.01em]">
              Operator console
            </h1>
          </div>
          <button
            onClick={() => setCreating(true)}
            className="rounded-btn bg-accent px-4 py-2 text-sm font-medium text-accent-ink hover:bg-accent-deep"
          >
            New client workspace
          </button>
        </header>

        {error && (
          <p className="mb-3 rounded-card bg-danger-soft px-3 py-2 text-sm text-danger">
            {error}
          </p>
        )}

        {rows && (
          <div className="overflow-x-auto rounded-card border border-edge bg-surface">
            <table className="w-full text-sm">
              <thead>
                <tr className="data border-b border-line text-left text-ink-muted uppercase">
                  <th scope="col" className="px-4 py-2.5">Workspace</th>
                  <th scope="col" className="px-4 py-2.5">Created</th>
                  <th scope="col" className="px-4 py-2.5">Trial ends</th>
                  <th scope="col" className="px-4 py-2.5">Members</th>
                  <th scope="col" className="px-4 py-2.5">Month usage</th>
                  <th scope="col" className="px-4 py-2.5">Modules</th>
                  <th scope="col" className="px-4 py-2.5"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {rows.map((t) => (
                  <tr key={t.id} className={t.suspended_at ? "bg-card/60" : undefined}>
                    <td className="px-4 py-3 font-medium">
                      <span className={t.suspended_at ? "text-ink-muted" : undefined}>
                        {t.name}
                      </span>
                      {t.suspended_at && (
                        <span
                          className="stamp ml-2 text-danger"
                          title={t.suspended_reason ?? undefined}
                        >
                          suspended
                        </span>
                      )}
                    </td>
                    <td className="data px-4 py-3 text-ink-faint">{fmtDate(t.created_at)}</td>
                    <td className="px-4 py-3 text-ink-muted">{fmtDate(t.trial_ends_at)}</td>
                    <td className="data px-4 py-3">
                      {t.member_count}/{t.seats}
                      {t.pending_invites > 0 && (
                        <span className="text-ink-faint"> +{t.pending_invites} invited</span>
                      )}
                    </td>
                    <td className="data px-4 py-3">
                      ${t.month_cost_usd.toFixed(2)} · {t.month_requests} req
                    </td>
                    <td className="px-4 py-3">
                      <button
                        onClick={() => setEditingModules(t)}
                        title="Change this workspace's modules"
                        className="flex flex-wrap items-center gap-1 rounded-[8px] px-1 py-0.5 hover:bg-card"
                      >
                        {FEATURE_FLAGS.filter((f) => t.features[f.key] === true).map((f) => (
                          <span key={f.key} className="stamp text-ink-muted">
                            {f.key}
                          </span>
                        ))}
                        <span className="text-xs text-ink-faint underline">Edit</span>
                      </button>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center justify-end gap-3 text-xs">
                        <button
                          onClick={() => setEditing(t)}
                          className="text-ink-muted underline hover:text-ink"
                        >
                          Edit
                        </button>
                        <button
                          onClick={() => reissueInvite(t)}
                          className="text-ink-muted underline hover:text-ink"
                        >
                          Owner invite
                        </button>
                        {t.suspended_at ? (
                          <>
                            <button
                              onClick={() => resume(t)}
                              className="text-grounded underline hover:opacity-80"
                            >
                              Resume
                            </button>
                            <button
                              onClick={() => purge(t)}
                              title="Delete this workspace for good — files, key and rows"
                              className="text-danger underline hover:opacity-80"
                            >
                              Purge…
                            </button>
                          </>
                        ) : (
                          <button
                            onClick={() => setSuspending(t)}
                            className="text-danger underline hover:opacity-80"
                          >
                            Suspend
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="mt-8">
        <h2 className="mb-1 text-lg font-medium">Funder forms</h2>
        <p className="mb-3 text-sm text-ink-muted">
          The curated catalogue every workspace drafts against. Forms are transcribed inside a
          workspace and published from here.
        </p>
        <CatalogueEditor />
      </div>

      {creating && (
        <NewWorkspace
          onClose={() => setCreating(false)}
          onCreated={(t) => {
            setCreating(false);
            setCreated(t);
            refresh();
          }}
        />
      )}
      {editingModules && (
        <ModulesEditor
          tenant={editingModules}
          onClose={() => setEditingModules(null)}
          onSaved={() => {
            setEditingModules(null);
            refresh();
          }}
        />
      )}
      {editing && (
        <EditWorkspace
          tenant={editing}
          onClose={() => setEditing(null)}
          onSaved={() => {
            setEditing(null);
            refresh();
          }}
        />
      )}
      {suspending && (
        <SuspendWorkspace
          tenant={suspending}
          onClose={() => setSuspending(null)}
          onDone={() => {
            setSuspending(null);
            refresh();
          }}
        />
      )}
      {created && <InviteLink invite={created} onDone={() => setCreated(null)} />}
      {reissued && (
        <InviteLink
          invite={reissued}
          title={`New owner invite for ${reissued.name}`}
          onDone={() => setReissued(null)}
        />
      )}
    </main>
  );
}
