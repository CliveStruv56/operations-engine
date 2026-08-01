"use client";

import { useState } from "react";
import { Stakeholder, fmtDate, gw } from "@/lib/groundwork";
import { LoadError, useGwLoad } from "./load";
import { btn, input } from "./ui";

export function StakeholdersTab({ id }: { id: string }) {
  const [people, setPeople] = useState<Stakeholder[]>([]);
  const [form, setForm] = useState({ name: "", org: "", role: "community", email: "" });

  const { failed, refresh } = useGwLoad<Stakeholder[]>(`/projects/${id}/stakeholders`, setPeople);

  async function add(e: React.FormEvent) {
    e.preventDefault();
    await gw(`/projects/${id}/stakeholders`, {
      method: "POST",
      body: JSON.stringify({
        name: form.name,
        org: form.org || null,
        role: form.role,
        email: form.email || null,
      }),
    });
    setForm({ name: "", org: "", role: "community", email: "" });
    refresh();
  }

  return (
    <div>
      <LoadError failed={failed} onRetry={refresh} />
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {people.map((p) => (
          <div key={p.id} className="rounded-card border border-edge bg-surface p-3 text-sm">
            <p className="font-medium">{p.name}</p>
            <p className="data mt-0.5 text-ink-muted uppercase">
              {p.role}
              {p.org ? ` · ${p.org}` : ""}
            </p>
            {p.email && <p className="mt-1 text-xs text-ink-muted">{p.email}</p>}
            {p.last_contact && (
              <p className="data mt-1 text-ink-faint">Last contact {fmtDate(p.last_contact)}</p>
            )}
          </div>
        ))}
      </div>
      <form onSubmit={add} className="mt-3 flex flex-wrap items-center gap-2">
        <input required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="Name" className={input} />
        <input value={form.org} onChange={(e) => setForm({ ...form, org: e.target.value })} placeholder="Organisation" className={input} />
        <select value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })} className={input}>
          {["lpa", "landowner", "funder", "contractor", "consultant", "community", "other"].map((r) => (
            <option key={r} value={r}>
              {r}
            </option>
          ))}
        </select>
        <input type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} placeholder="Email" className={input} />
        <button type="submit" className={btn}>
          Add
        </button>
      </form>
    </div>
  );
}
