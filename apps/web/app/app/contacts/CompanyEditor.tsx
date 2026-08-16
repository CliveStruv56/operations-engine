"use client";

import { useState } from "react";
import { ApiError } from "@/lib/api";
import { Company, CompanyForm, crm } from "@/lib/crm";
import { btn, btnGhost, input, label } from "./ui";
import { Panel } from "@/components/Panel";
import { useAsk } from "@/components/ui";

const empty: CompanyForm = {
  name: "",
  website: null,
  email: null,
  phone: null,
  address_line1: null,
  address_line2: null,
  city: null,
  postcode: null,
  notes: null,
};

function toForm(c: Company): CompanyForm {
  return {
    name: c.name,
    website: c.website,
    email: c.email,
    phone: c.phone,
    address_line1: c.address_line1,
    address_line2: c.address_line2,
    city: c.city,
    postcode: c.postcode,
    notes: c.notes,
  };
}

export function CompanyEditor({
  company,
  onClose,
  onSaved,
}: {
  company: Company | null; // null = create
  onClose: () => void;
  onSaved: () => void;
}) {
  const ask = useAsk();
  const [form, setForm] = useState<CompanyForm>(company ? toForm(company) : empty);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const set = (patch: Partial<CompanyForm>) => setForm((f) => ({ ...f, ...patch }));
  const opt = (v: string) => (v.trim() === "" ? null : v);

  async function save(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      if (company) {
        await crm(`/companies/${company.id}`, { method: "PATCH", body: JSON.stringify(form) });
      } else {
        await crm("/companies", { method: "POST", body: JSON.stringify(form) });
      }
      onSaved();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong — try again.");
      setSaving(false);
    }
  }

  async function remove() {
    if (!company) return;
    const confirmed = await ask.confirm({
      title: `Delete ${company.name}`,
      body:
        company.contact_count > 0
          ? `Its ${company.contact_count} contact${
              company.contact_count === 1 ? "" : "s"
            } stay in the contact book — they are kept, just no longer attached to a company.`
          : "It comes out of the contact book for everyone in the workspace.",
      confirmLabel: "Delete company",
      tone: "danger",
    });
    if (!confirmed) return;
    await crm(`/companies/${company.id}`, { method: "DELETE" });
    onSaved();
  }

  return (
    <Panel title={company ? "Edit company" : "New company"} onClose={onClose}>
      <form onSubmit={save} className="flex flex-col gap-3">
        {error && (
          <p className="rounded-[10px] bg-danger-soft px-3 py-2 text-sm text-danger">{error}</p>
        )}
        <div>
          <span className={label}>Name</span>
          <input
            required
            autoFocus
            value={form.name}
            onChange={(e) => set({ name: e.target.value })}
            className={input}
          />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <span className={label}>Email</span>
            <input
              type="email"
              value={form.email ?? ""}
              onChange={(e) => set({ email: opt(e.target.value) })}
              className={input}
            />
          </div>
          <div>
            <span className={label}>Phone</span>
            <input
              value={form.phone ?? ""}
              onChange={(e) => set({ phone: opt(e.target.value) })}
              className={input}
            />
          </div>
        </div>
        <div>
          <span className={label}>Website</span>
          <input
            value={form.website ?? ""}
            onChange={(e) => set({ website: opt(e.target.value) })}
            className={input}
          />
        </div>
        <div>
          <span className={label}>Address</span>
          <div className="flex flex-col gap-2">
            <input
              value={form.address_line1 ?? ""}
              onChange={(e) => set({ address_line1: opt(e.target.value) })}
              placeholder="Line 1"
              className={input}
            />
            <input
              value={form.address_line2 ?? ""}
              onChange={(e) => set({ address_line2: opt(e.target.value) })}
              placeholder="Line 2"
              className={input}
            />
            <div className="grid grid-cols-2 gap-2">
              <input
                value={form.city ?? ""}
                onChange={(e) => set({ city: opt(e.target.value) })}
                placeholder="Town / city"
                className={input}
              />
              <input
                value={form.postcode ?? ""}
                onChange={(e) => set({ postcode: opt(e.target.value) })}
                placeholder="Postcode"
                className={input}
              />
            </div>
          </div>
        </div>
        <div>
          <span className={label}>Notes</span>
          <textarea
            rows={3}
            value={form.notes ?? ""}
            onChange={(e) => set({ notes: opt(e.target.value) })}
            className={input}
          />
        </div>
        <div className="mt-1 flex items-center gap-3">
          <button type="submit" disabled={saving} className={btn}>
            {company ? "Save changes" : "Add company"}
          </button>
          {company && (
            <button type="button" onClick={remove} className={`${btnGhost} text-danger`}>
              Delete
            </button>
          )}
          <button type="button" onClick={onClose} className={`${btnGhost} ml-auto`}>
            Cancel
          </button>
        </div>
      </form>
    </Panel>
  );
}
