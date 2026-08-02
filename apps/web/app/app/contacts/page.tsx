"use client";

import { Suspense, useCallback, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { ApiError } from "@/lib/api";
import { Company, Contact, companyAddress, crm } from "@/lib/crm";
import { tenantId } from "@/lib/groundwork";
import { CompanyEditor } from "./CompanyEditor";
import { ContactEditor } from "./ContactEditor";
import { btn } from "./ui";

type View = "people" | "companies";
// Sentinel for "editor open in create mode" (vs null = closed).
const NEW = "new" as const;

export default function ContactsPage() {
  return (
    // useSearchParams needs a Suspense boundary at the page level.
    <Suspense>
      <ContactsPageInner />
    </Suspense>
  );
}

function ContactsPageInner() {
  const router = useRouter();
  const sp = useSearchParams();
  const [contacts, setContacts] = useState<Contact[] | null>(null);
  const [companies, setCompanies] = useState<Company[] | null>(null);
  const [view, setView] = useState<View>("people");
  const [q, setQ] = useState("");
  const [tag, setTag] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [enabled, setEnabled] = useState(true);
  const [editContact, setEditContact] = useState<Contact | typeof NEW | null>(null);
  const [editCompany, setEditCompany] = useState<Company | typeof NEW | null>(null);

  const refresh = useCallback(async () => {
    try {
      const [people, cos] = await Promise.all([
        crm<Contact[]>("/contacts"),
        crm<Company[]>("/companies"),
      ]);
      setContacts(people);
      setCompanies(cos);
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) setEnabled(false);
      else setError(err instanceof Error ? err.message : String(err));
    }
  }, []);

  useEffect(() => {
    if (!tenantId()) {
      router.push("/app");
      return;
    }
    // Fetch-on-mount: every setState in refresh happens after an await.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    refresh();
  }, [router, refresh]);

  // ⌘K hands off with ?c=<id>: open that contact's editor once loaded, then
  // strip the param so refresh/back doesn't reopen it.
  const wanted = sp.get("c");
  useEffect(() => {
    if (!wanted || !contacts) return;
    const hit = contacts.find((c) => c.id === wanted);
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (hit) setEditContact(hit);
    router.replace("/app/contacts");
  }, [wanted, contacts, router]);

  function closeEditors(saved: boolean) {
    setEditContact(null);
    setEditCompany(null);
    if (saved) refresh();
  }

  const needle = q.trim().toLowerCase();
  const people = (contacts ?? []).filter((c) => {
    if (tag && !c.tags.includes(tag)) return false;
    if (!needle) return true;
    return [c.name, c.email, c.job_title, c.company_name, ...c.tags]
      .filter(Boolean)
      .some((v) => v!.toLowerCase().includes(needle));
  });
  const cos = (companies ?? []).filter(
    (c) => !needle || [c.name, c.city, c.postcode].filter(Boolean).some((v) => v!.toLowerCase().includes(needle))
  );
  const allTags = [...new Set((contacts ?? []).flatMap((c) => c.tags))].sort();

  if (!enabled)
    return (
      <main className="min-h-0 flex-1 overflow-y-auto p-8">
        <p className="rounded-card border border-edge bg-surface p-6 text-sm text-ink-muted">
          Contacts aren&rsquo;t switched on for this workspace yet.
        </p>
      </main>
    );

  return (
    <main className="min-h-0 flex-1 overflow-y-auto">
      <div className="mx-auto max-w-6xl p-6">
        <header className="mb-5 flex flex-wrap items-center justify-between gap-3">
          <h1 className="font-display text-[26px] font-medium tracking-[-0.01em]">Contacts</h1>
          <button
            onClick={() => (view === "people" ? setEditContact(NEW) : setEditCompany(NEW))}
            className={btn}
          >
            {view === "people" ? "Add contact" : "Add company"}
          </button>
        </header>

        <div className="mb-4 flex flex-wrap items-center gap-3">
          <div className="flex rounded-[10px] border border-edge bg-surface p-0.5">
            {(["people", "companies"] as const).map((v) => (
              <button
                key={v}
                onClick={() => setView(v)}
                className={`rounded-[8px] px-3 py-1.5 text-sm capitalize ${
                  view === v ? "bg-accent text-accent-ink font-medium" : "text-ink-muted hover:text-ink"
                }`}
              >
                {v === "people" ? `People${contacts ? ` · ${contacts.length}` : ""}` : `Companies${companies ? ` · ${companies.length}` : ""}`}
              </button>
            ))}
          </div>
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder={view === "people" ? "Search people, companies, tags…" : "Search companies…"}
            className="w-64 rounded-[10px] border border-line bg-surface px-3 py-2 text-sm placeholder:text-ink-faint focus:outline-none focus:border-edge-strong"
          />
          {view === "people" &&
            allTags.map((t) => (
              <button
                key={t}
                onClick={() => setTag(tag === t ? null : t)}
                className={`stamp ${tag === t ? "bg-accent text-accent-ink border-accent" : "text-ink-muted hover:text-ink"}`}
              >
                {t}
              </button>
            ))}
        </div>

        {error && (
          <p className="rounded-[10px] bg-danger-soft px-3 py-2 text-sm text-danger">{error}</p>
        )}

        {view === "people" && contacts && (
          people.length === 0 ? (
            <Empty
              headline="Everyone your team deals with, in one shared address book."
              hint="Add people by hand now — funders, planners, contractors, suppliers — and link them to companies and projects."
            />
          ) : (
            <div className="overflow-x-auto rounded-card border border-edge bg-surface">
              <table className="w-full text-sm">
                <thead>
                  <tr className="data border-b border-line text-left text-ink-muted uppercase">
                    <th className="px-4 py-2.5">Name</th>
                    <th className="px-4 py-2.5">Company</th>
                    <th className="px-4 py-2.5">Email</th>
                    <th className="px-4 py-2.5">Phone</th>
                    <th className="px-4 py-2.5">Tags</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-line">
                  {people.map((c) => (
                    <tr
                      key={c.id}
                      onClick={() => setEditContact(c)}
                      className="cursor-pointer hover:bg-accent-soft"
                    >
                      <td className="px-4 py-3">
                        <span className="font-medium">{c.name}</span>
                        {c.job_title && (
                          <span className="block text-xs text-ink-muted">{c.job_title}</span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-ink-muted">{c.company_name ?? "—"}</td>
                      <td className="px-4 py-3 text-ink-muted">{c.email ?? "—"}</td>
                      <td className="px-4 py-3 text-ink-muted">
                        {c.phone ?? c.mobile ?? "—"}
                        {c.phone && c.mobile && (
                          <span className="block text-xs text-ink-faint">{c.mobile}</span>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        <span className="flex flex-wrap gap-1">
                          {c.tags.map((t) => (
                            <span key={t} className="stamp text-ink-muted">
                              {t}
                            </span>
                          ))}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )
        )}

        {view === "companies" && companies && (
          cos.length === 0 ? (
            <Empty
              headline="Companies keep shared details in one place."
              hint="Add an organisation once — address, phone, website — and every contact you link to it stays up to date."
            />
          ) : (
            <div className="overflow-x-auto rounded-card border border-edge bg-surface">
              <table className="w-full text-sm">
                <thead>
                  <tr className="data border-b border-line text-left text-ink-muted uppercase">
                    <th className="px-4 py-2.5">Name</th>
                    <th className="px-4 py-2.5">Address</th>
                    <th className="px-4 py-2.5">Phone</th>
                    <th className="px-4 py-2.5">People</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-line">
                  {cos.map((c) => (
                    <tr
                      key={c.id}
                      onClick={() => setEditCompany(c)}
                      className="cursor-pointer hover:bg-accent-soft"
                    >
                      <td className="px-4 py-3 font-medium">{c.name}</td>
                      <td className="px-4 py-3 text-ink-muted">{companyAddress(c) || "—"}</td>
                      <td className="px-4 py-3 text-ink-muted">{c.phone ?? "—"}</td>
                      <td className="data px-4 py-3">{c.contact_count}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )
        )}
      </div>

      {editContact !== null && (
        <ContactEditor
          contact={editContact === NEW ? null : editContact}
          companies={companies ?? []}
          onClose={() => closeEditors(false)}
          onSaved={() => closeEditors(true)}
        />
      )}
      {editCompany !== null && (
        <CompanyEditor
          company={editCompany === NEW ? null : editCompany}
          onClose={() => closeEditors(false)}
          onSaved={() => closeEditors(true)}
        />
      )}
    </main>
  );
}

function Empty({ headline, hint }: { headline: string; hint: string }) {
  return (
    <div className="rounded-card border border-edge bg-surface p-10 text-center">
      <p className="text-sm font-medium">{headline}</p>
      <p className="mt-1 text-sm text-ink-muted">{hint}</p>
    </div>
  );
}
