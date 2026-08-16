"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { Contact, crm } from "@/lib/crm";
import { btn, btnGhost, input } from "./ui";

/** CRM contacts linked to this project (shown only when the contacts
 *  feature flag is on). The full book lives at /app/contacts. */
export function ContactsTab({ id }: { id: string }) {
  const [linked, setLinked] = useState<Contact[]>([]);
  const [query, setQuery] = useState("");
  const [matches, setMatches] = useState<Contact[]>([]);
  const [failed, setFailed] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      setLinked(await crm<Contact[]>(`/contacts?project_id=${id}`));
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

  // Search server-side rather than pulling the whole book down to filter it:
  // a workspace that has run a couple of CSV imports has thousands of rows.
  useEffect(() => {
    const term = query.trim();
    const timer = setTimeout(async () => {
      if (term.length < 2) {
        setMatches([]);
        return;
      }
      try {
        setMatches(await crm<Contact[]>(`/contacts?limit=10&q=${encodeURIComponent(term)}`));
      } catch (err) {
        console.error("Contact search failed", err);
        setMatches([]);
      }
    }, 200);
    return () => clearTimeout(timer);
  }, [query]);

  async function link(contactId: string) {
    try {
      await crm(`/contacts/${contactId}/projects/${id}`, { method: "POST" });
      setQuery("");
      setActionError(null);
      await refresh();
    } catch (err) {
      // Without this the click is a silent no-op: the contact or project may
      // have been deleted by a teammate since this tab loaded.
      console.error("Failed to link contact", err);
      setActionError("Couldn't link that contact. Refresh and try again.");
    }
  }

  async function unlink(contactId: string) {
    try {
      await crm(`/contacts/${contactId}/projects/${id}`, { method: "DELETE" });
      setActionError(null);
      await refresh();
    } catch (err) {
      console.error("Failed to unlink contact", err);
      setActionError("Couldn't unlink that contact. Refresh and try again.");
    }
  }

  const linkable = matches.filter((c) => !c.project_ids.includes(id));

  return (
    <div>
      {actionError && (
        <p role="alert" className="mb-3 rounded-card bg-danger-soft px-3 py-2 text-sm text-danger">
          {actionError}
        </p>
      )}
      {failed && (
        <p role="alert" className="mb-3 rounded-card bg-danger-soft px-3 py-2 text-sm text-danger">
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
      <div className="mt-3">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search the contact book to link someone…"
          aria-label="Search contacts to link"
          className={input}
        />
        {query.trim().length >= 2 && (
          <ul className="mt-2 flex flex-col gap-1">
            {linkable.map((c) => (
              <li key={c.id} className="flex items-center justify-between gap-2 text-sm">
                <span className="min-w-0 truncate">
                  {c.name}
                  {c.company_name ? ` — ${c.company_name}` : ""}
                </span>
                <button onClick={() => link(c.id)} className={btn}>
                  Link
                </button>
              </li>
            ))}
            {linkable.length === 0 && (
              <li className="text-sm text-ink-muted">No matching contacts.</li>
            )}
          </ul>
        )}
      </div>
    </div>
  );
}
