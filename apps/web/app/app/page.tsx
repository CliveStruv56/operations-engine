"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase/client";
import { api, ApiError } from "@/lib/api";
import ChatPanel from "./chat";
import VaultPanel from "./vault";

type Tenant = {
  id: string;
  name: string;
  plan: string;
  seats: number;
  trial_ends_at: string | null;
  role: string;
};

type MembershipRef = { tenant_id: string; name: string; role: string };

export type Project = {
  id: string;
  name: string;
  description: string | null;
  archived: boolean;
  document_count: number;
};

const NAV = [
  { key: "chat", label: "Chat", hint: "Ask about your documents" },
  { key: "vault", label: "Vault", hint: "The documents behind the answers" },
] as const;

export default function WorkspacePage() {
  const router = useRouter();
  const [email, setEmail] = useState<string | null>(null);
  const [tenant, setTenant] = useState<Tenant | null>(null);
  const [memberships, setMemberships] = useState<MembershipRef[] | null>(null);
  const [newName, setNewName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<"chat" | "vault">("chat");
  const [projects, setProjects] = useState<Project[]>([]);
  const [activeProjectId, setActiveProjectId] = useState<string | null>(null);
  const [addingProject, setAddingProject] = useState(false);
  const [projectName, setProjectName] = useState("");

  const loadProjects = useCallback(async (tenantId: string) => {
    try {
      setProjects(await api<Project[]>("/projects", {}, tenantId));
    } catch {
      /* project list failing must not take down the workspace */
    }
  }, []);

  const loadTenant = useCallback(async (tenantId?: string) => {
    try {
      const me = await api<Tenant>("/tenants/me", {}, tenantId);
      setTenant(me);
      setMemberships(null);
      setError(null);
      if (tenantId) localStorage.setItem("tenantId", tenantId);
      loadProjects(me.id);
    } catch (e) {
      if (e instanceof ApiError && e.code === "tenant_required") {
        const list = (e.payload as { memberships?: MembershipRef[] })?.memberships ?? [];
        setMemberships(list);
      } else {
        setError(e instanceof Error ? e.message : String(e));
      }
    } finally {
      setLoading(false);
    }
  }, [loadProjects]);

  useEffect(() => {
    const supabase = createClient();
    supabase.auth.getUser().then(({ data }) => setEmail(data.user?.email ?? null));
    // Fetch-on-mount: every setState in loadTenant happens after an await.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    loadTenant(localStorage.getItem("tenantId") ?? undefined);
  }, [loadTenant]);

  async function createTenant(e: React.FormEvent) {
    e.preventDefault();
    try {
      const created = await api<{ id: string }>("/tenants", {
        method: "POST",
        body: JSON.stringify({ name: newName }),
      });
      await loadTenant(created.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  async function createProject(e: React.FormEvent) {
    e.preventDefault();
    if (!tenant) return;
    try {
      const created = await api<Project>(
        "/projects",
        { method: "POST", body: JSON.stringify({ name: projectName }) },
        tenant.id
      );
      setProjectName("");
      setAddingProject(false);
      await loadProjects(tenant.id);
      setActiveProjectId(created.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  async function logout() {
    await createClient().auth.signOut();
    localStorage.removeItem("tenantId");
    router.push("/login");
    router.refresh();
  }

  if (loading) {
    return (
      <main className="flex min-h-screen items-center justify-center">
        <p className="data text-ink-faint">Loading workspace…</p>
      </main>
    );
  }

  // No workspace yet: choose one, or found one.
  if (!tenant) {
    return (
      <main className="flex min-h-screen items-center justify-center p-6">
        <div className="w-full max-w-md">
          <p className="data mb-2 text-ink-faint uppercase">Operations Engine</p>
          {error && (
            <p className="mb-4 rounded-sm bg-danger-soft px-3 py-2 text-sm text-danger">{error}</p>
          )}

          {memberships && memberships.length > 0 ? (
            <section className="rounded-md border border-line bg-surface p-6 shadow-sm">
              <h1 className="text-xl font-semibold tracking-tight">Choose a workspace</h1>
              <div className="mt-4 divide-y divide-line border-y border-line">
                {memberships.map((m) => (
                  <button
                    key={m.tenant_id}
                    onClick={() => {
                      setLoading(true);
                      loadTenant(m.tenant_id);
                    }}
                    className="flex w-full items-center justify-between px-1 py-3 text-left hover:bg-accent-soft"
                  >
                    <span className="font-medium">{m.name}</span>
                    <span className="data text-ink-muted uppercase">{m.role}</span>
                  </button>
                ))}
              </div>
            </section>
          ) : (
            <section className="rounded-md border border-line bg-surface p-6 shadow-sm">
              <h1 className="text-xl font-semibold tracking-tight">Set up your workspace</h1>
              <p className="mt-1 text-sm text-ink-muted">
                Your team&apos;s documents and conversations live here.
              </p>
              <form onSubmit={createTenant} className="mt-5 space-y-3">
                <input
                  required
                  placeholder="Company name"
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  className="w-full rounded-sm border border-line bg-surface px-3 py-2 text-sm"
                />
                <button
                  type="submit"
                  className="w-full rounded-sm bg-accent px-4 py-2 text-sm font-medium text-accent-ink hover:opacity-90"
                >
                  Create workspace
                </button>
              </form>
            </section>
          )}
        </div>
      </main>
    );
  }

  return (
    <main className="flex h-screen">
      <aside className="flex w-60 shrink-0 flex-col border-r border-line">
        <div className="border-b border-line px-5 py-4">
          <p className="data text-ink-faint uppercase">Operations Engine</p>
          <h1 className="mt-1 truncate text-base font-semibold tracking-tight">{tenant.name}</h1>
        </div>

        <nav className="min-h-0 flex-1 overflow-y-auto p-3">
          {NAV.map((item) => (
            <button
              key={item.key}
              onClick={() => setTab(item.key)}
              className={`mb-1 block w-full rounded-sm border-l-2 px-3 py-2 text-left text-sm transition-colors ${
                tab === item.key
                  ? "border-accent bg-accent-soft font-medium"
                  : "border-transparent text-ink-muted hover:bg-surface hover:text-ink"
              }`}
            >
              {item.label}
              <span className="mt-0.5 block text-xs font-normal text-ink-faint">{item.hint}</span>
            </button>
          ))}

          <p className="data mt-5 mb-1 px-3 text-ink-faint uppercase">Projects</p>
          <button
            onClick={() => setActiveProjectId(null)}
            className={`mb-0.5 block w-full rounded-sm border-l-2 px-3 py-1.5 text-left text-sm ${
              activeProjectId === null
                ? "border-accent bg-accent-soft font-medium"
                : "border-transparent text-ink-muted hover:bg-surface hover:text-ink"
            }`}
          >
            Everything
          </button>
          {projects
            .filter((p) => !p.archived)
            .map((p) => (
              <button
                key={p.id}
                onClick={() => setActiveProjectId(p.id)}
                className={`mb-0.5 flex w-full items-baseline justify-between gap-2 rounded-sm border-l-2 px-3 py-1.5 text-left text-sm ${
                  activeProjectId === p.id
                    ? "border-accent bg-accent-soft font-medium"
                    : "border-transparent text-ink-muted hover:bg-surface hover:text-ink"
                }`}
              >
                <span className="truncate">{p.name}</span>
                <span className="data shrink-0 text-ink-faint">{p.document_count}</span>
              </button>
            ))}
          {addingProject ? (
            <form onSubmit={createProject} className="mt-1 px-3">
              <input
                autoFocus
                required
                value={projectName}
                onChange={(e) => setProjectName(e.target.value)}
                onBlur={() => !projectName && setAddingProject(false)}
                placeholder="Project name"
                className="w-full rounded-sm border border-line bg-surface px-2 py-1 text-sm"
              />
            </form>
          ) : (
            <button
              onClick={() => setAddingProject(true)}
              className="mt-1 block w-full px-3 py-1 text-left text-xs text-ink-faint hover:text-ink"
            >
              + New project
            </button>
          )}
        </nav>

        <div className="space-y-2 border-t border-line px-5 py-4">
          <p className="data text-ink-muted uppercase">
            {tenant.plan} · {tenant.seats} seats · {tenant.role}
          </p>
          {tenant.trial_ends_at && (
            <p className="data text-warn">
              Trial ends {new Date(tenant.trial_ends_at).toLocaleDateString("en-GB")}
            </p>
          )}
          <p className="truncate text-xs text-ink-muted">{email}</p>
          <button onClick={logout} className="text-xs text-ink-muted underline hover:text-ink">
            Sign out
          </button>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col bg-surface">
        {error && (
          <p className="border-b border-line bg-danger-soft px-6 py-2 text-sm text-danger">
            {error}
          </p>
        )}
        {tab === "chat" ? (
          <ChatPanel
            tenantId={tenant.id}
            projects={projects}
            activeProjectId={activeProjectId}
          />
        ) : (
          <VaultPanel
            tenantId={tenant.id}
            projects={projects}
            activeProjectId={activeProjectId}
            onProjectsChanged={() => loadProjects(tenant.id)}
          />
        )}
      </div>
    </main>
  );
}
