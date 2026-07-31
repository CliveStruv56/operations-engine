"use client";

import { useCallback, useEffect, useState } from "react";
import { Condition, gw } from "@/lib/groundwork";
import { btn, input } from "./ui";

export function ConditionsTab({ id }: { id: string }) {
  const [conditions, setConditions] = useState<Condition[]>([]);
  const [form, setForm] = useState({ application_ref: "", number: "", description: "", pre: false });

  const refresh = useCallback(
    () => gw<Condition[]>(`/projects/${id}/conditions`).then(setConditions).catch(() => {}),
    [id]
  );
  useEffect(() => {

    refresh();
  }, [refresh]);

  async function add(e: React.FormEvent) {
    e.preventDefault();
    await gw(`/projects/${id}/conditions`, {
      method: "POST",
      body: JSON.stringify({
        application_ref: form.application_ref || null,
        number: form.number,
        description: form.description,
        pre_commencement: form.pre,
      }),
    });
    setForm({ application_ref: "", number: "", description: "", pre: false });
    refresh();
  }

  async function setStatus(c: Condition, status: string) {
    await gw(`/projects/${id}/conditions/${c.id}`, {
      method: "PATCH",
      body: JSON.stringify({ status }),
    });
    refresh();
  }

  return (
    <div>
      <table className="w-full rounded-md border border-line bg-surface text-sm">
        <thead>
          <tr className="data border-b border-line text-left text-ink-muted uppercase">
            <th className="px-3 py-2">No.</th>
            <th className="px-3 py-2">Condition</th>
            <th className="px-3 py-2">Application</th>
            <th className="px-3 py-2">Status</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-line">
          {conditions.map((c) => (
            <tr key={c.id}>
              <td className="data px-3 py-2">
                {c.number}
                {c.pre_commencement && (
                  <span className="stamp ml-1.5 text-warn bg-warn-soft" title="Must be discharged before works start">
                    pre-comm.
                  </span>
                )}
              </td>
              <td className="px-3 py-2">{c.description}</td>
              <td className="data px-3 py-2 text-ink-muted">{c.application_ref ?? "—"}</td>
              <td className="px-3 py-2">
                <select value={c.status} onChange={(e) => setStatus(c, e.target.value)} className={input}>
                  {["outstanding", "submitted", "discharged", "partially_discharged", "na"].map((s) => (
                    <option key={s} value={s}>
                      {s.replaceAll("_", " ")}
                    </option>
                  ))}
                </select>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <form onSubmit={add} className="mt-3 flex flex-wrap items-center gap-2">
        <input value={form.application_ref} onChange={(e) => setForm({ ...form, application_ref: e.target.value })} placeholder="LPA ref" className={`w-32 ${input}`} />
        <input required value={form.number} onChange={(e) => setForm({ ...form, number: e.target.value })} placeholder="No." className={`w-16 ${input}`} />
        <input required value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} placeholder="Condition wording…" className={`min-w-0 flex-1 ${input}`} />
        <label className="flex items-center gap-1 text-sm text-ink-muted">
          <input type="checkbox" checked={form.pre} onChange={(e) => setForm({ ...form, pre: e.target.checked })} className="accent-(--accent)" />
          Pre-commencement
        </label>
        <button type="submit" className={btn}>
          Add
        </button>
      </form>
    </div>
  );
}
