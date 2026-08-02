"use client";

import { useState } from "react";
import { ApiError } from "@/lib/api";
import { Company, Contact, ContactForm, crm } from "@/lib/crm";
import { btn, btnGhost, input, label } from "./ui";
import { Panel } from "./Panel";

const empty: ContactForm = {
  name: "",
  company_id: null,
  job_title: null,
  email: null,
  phone: null,
  mobile: null,
  address: null,
  notes: null,
  tags: [],
};

function toForm(c: Contact): ContactForm {
  return {
    name: c.name,
    company_id: c.company_id,
    job_title: c.job_title,
    email: c.email,
    phone: c.phone,
    mobile: c.mobile,
    address: c.address,
    notes: c.notes,
    tags: c.tags,
  };
}

export function ContactEditor({
  contact,
  companies,
  onClose,
  onSaved,
}: {
  contact: Contact | null; // null = create
  companies: Company[];
  onClose: () => void;
  onSaved: () => void;
}) {
  const [form, setForm] = useState<ContactForm>(contact ? toForm(contact) : empty);
  const [tagsText, setTagsText] = useState(contact?.tags.join(", ") ?? "");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const set = (patch: Partial<ContactForm>) => setForm((f) => ({ ...f, ...patch }));
  // Empty text inputs persist as null, not "".
  const opt = (v: string) => (v.trim() === "" ? null : v);

  async function save(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    const body = {
      ...form,
      tags: tagsText.split(",").map((t) => t.trim()).filter(Boolean),
    };
    try {
      if (contact) {
        await crm(`/contacts/${contact.id}`, { method: "PATCH", body: JSON.stringify(body) });
      } else {
        await crm("/contacts", { method: "POST", body: JSON.stringify(body) });
      }
      onSaved();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong — try again.");
      setSaving(false);
    }
  }

  async function remove() {
    if (!contact || !window.confirm(`Delete ${contact.name} from contacts?`)) return;
    await crm(`/contacts/${contact.id}`, { method: "DELETE" });
    onSaved();
  }

  return (
    <Panel title={contact ? "Edit contact" : "New contact"} onClose={onClose}>
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
            <span className={label}>Job title</span>
            <input
              value={form.job_title ?? ""}
              onChange={(e) => set({ job_title: opt(e.target.value) })}
              className={input}
            />
          </div>
          <div>
            <span className={label}>Company</span>
            <select
              value={form.company_id ?? ""}
              onChange={(e) => set({ company_id: e.target.value || null })}
              className={input}
            >
              <option value="">No company</option>
              {companies.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </div>
        </div>
        <div>
          <span className={label}>Email</span>
          <input
            type="email"
            value={form.email ?? ""}
            onChange={(e) => set({ email: opt(e.target.value) })}
            className={input}
          />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <span className={label}>Phone</span>
            <input
              value={form.phone ?? ""}
              onChange={(e) => set({ phone: opt(e.target.value) })}
              className={input}
            />
          </div>
          <div>
            <span className={label}>Mobile</span>
            <input
              value={form.mobile ?? ""}
              onChange={(e) => set({ mobile: opt(e.target.value) })}
              className={input}
            />
          </div>
        </div>
        <div>
          <span className={label}>Address</span>
          <input
            value={form.address ?? ""}
            onChange={(e) => set({ address: opt(e.target.value) })}
            placeholder="Only if different from the company address"
            className={input}
          />
        </div>
        <div>
          <span className={label}>Tags</span>
          <input
            value={tagsText}
            onChange={(e) => setTagsText(e.target.value)}
            placeholder="supplier, planning, team — comma-separated"
            className={input}
          />
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
            {contact ? "Save changes" : "Add contact"}
          </button>
          {contact && (
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
