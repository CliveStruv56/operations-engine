"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { Contact, crm } from "@/lib/crm";
import { btn, btnGhost, input } from "./ui";

/** CRM contacts linked to this project (shown only when the contacts
 *  feature flag is on). The full book lives at /app/contacts. */
export function ContactsTab({ id }: { id: string }) {
  const [linked, setLinked] = useState<Contact[]>([]);
  const [all, setAll] = useState<Contact[]>([]);
  const [pick, setPick] = useState("");
  const [failed, setFailed] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const [mine, everyone] = await Promise.all([
        crm<Contact[]>(`/contacts?project_id=${id}`),
        crm<Contact[]>("/contacts"),
      ]);
      setLinked(mine);
      setAll(everyone);
      setFailed(false);
    } catch (err) {
      console.error("Failed to load project contacts", err);
      setFailed(true);
    }
  }, [id]);

  useEffect(() => {
    // Fetch-on-mount: every setState in refresh happens after an await.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    refresh();
  }, [refresh]);

  async function link(e: React.FormEvent) {
    e.preventDefault();
    if (!pick) return;
    await crm(`/contacts/${pick}/projects/${id}`, { method: "POST" });
    setPick("");
    refresh();
  }

  async function unlink(contactId: string) {
    await crm(`/contacts/${contactId}/projects/${id}`, { method: "DELETE" });
    refresh();
  }

  const linkable = all.filter((c) => !c.project_ids.includes(id));

  return (
    <div>
      {failed && (
        <p role="alert" className="mb-3 rounded-[10px] bg-danger-soft px-3 py-2 text-sm text-danger">
          Contacts failed to load.{" "}
          <button onClick={refresh} className="underline">
            Retry
          </button>
        </p>
      )}
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {linked.map((c) => (
          <div key={c.id} className="rounded-card border border-edge bg-surface p-3 text-sm">
            <p className="font-medium">{c.name}</p>
            <p className="data mt-0.5 text-ink-muted uppercase">
              {c.job_title ?? "contact"}
              {c.company_name ? ` · ${c.company_name}` : ""}
            </p>
            {c.email && <p className="mt-1 text-xs text-ink-muted">{c.email}</p>}
            {(c.phone || c.mobile) && (
              <p className="mt-0.5 text-xs text-ink-muted">{c.phone ?? c.mobile}</p>
            )}
            <button onClick={() => unlink(c.id)} className={`${btnGhost} mt-2`}>
              Unlink
            </button>
          </div>
        ))}
      </div>
      {linked.length === 0 && !failed && (
        <p className="text-sm text-ink-muted">
          No contacts linked to this project yet — link people from the shared{" "}
          <Link href="/app/contacts" className="underline hover:text-ink">
            contact book
          </Link>
          .
        </p>
      )}
      <form onSubmit={link} className="mt-3 flex flex-wrap items-center gap-2">
        <select value={pick} onChange={(e) => setPick(e.target.value)} className={input}>
          <option value="">Link a contact…</option>
          {linkable.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
              {c.company_name ? ` — ${c.company_name}` : ""}
            </option>
          ))}
        </select>
        <button type="submit" disabled={!pick} className={btn}>
          Link
        </button>
      </form>
    </div>
  );
}
