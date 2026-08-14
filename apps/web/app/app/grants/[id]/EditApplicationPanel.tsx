"use client";

import { useEffect, useState } from "react";
import { Spinner } from "@/components/activity";
import { Application, CatalogueRow, Funder, catalogueWarning, gr } from "@/lib/grants";
import { useWorkspace } from "../../workspace";
import { btn, btnGhost, input } from "../ui";

export function EditApplicationPanel({
  detail,
  onSaved,
  onCancel,
}: {
  detail: Application;
  onSaved: (next: Application) => void;
  onCancel: () => void;
}) {
  const ws = useWorkspace();
  const [funders, setFunders] = useState<Funder[]>([]);
  const [catalogue, setCatalogue] = useState<CatalogueRow[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState({
    title: detail.title,
    funder_id: detail.funder_id ?? "",
    programme_key: detail.programme_key ?? "",
    project_id: detail.project_id ?? "",
    amount_requested: detail.amount_requested?.toString() ?? "",
    amount_awarded: detail.amount_awarded?.toString() ?? "",
    deadline: detail.deadline ?? "",
    start_date: detail.start_date ?? "",
    end_date: detail.end_date ?? "",
    restricted: detail.restricted,
  });

  useEffect(() => {
    gr<Funder[]>("/grants/funders").then(setFunders).catch(() => setFunders([]));
    gr<CatalogueRow[]>("/grants/funder-catalogue").then(setCatalogue).catch(() => setCatalogue([]));
  }, []);

  const chosen = catalogue.find((c) => c.key === form.programme_key);
  const warning = chosen ? catalogueWarning(chosen) : null;
  const projects = ws.projects.filter((p) => !p.archived);

  async function save(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const next = await gr<Application>(`/grants/applications/${detail.id}`, {
        method: "PATCH",
        body: JSON.stringify({
          title: form.title,
          funder_id: form.funder_id || null,
          programme_key: form.programme_key || null,
          project_id: form.project_id || null,
          amount_requested: form.amount_requested || null,
          amount_awarded: form.amount_awarded || null,
          deadline: form.deadline || null,
          start_date: form.start_date || null,
          end_date: form.end_date || null,
          restricted: form.restricted,
        }),
      });
      onSaved(next);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={save} className="mb-4 space-y-3 rounded-card border border-edge bg-surface p-4">
      <label className="block text-sm">
        Title
        <input
          required
          value={form.title}
          onChange={(e) => setForm({ ...form, title: e.target.value })}
          className={`${input} mt-1 w-full`}
        />
      </label>
      <div className="grid gap-3 sm:grid-cols-2">
        <label className="block text-sm">
          Funder
          <select
            value={form.funder_id}
            onChange={(e) => setForm({ ...form, funder_id: e.target.value })}
            className={`${input} mt-1 w-full`}
          >
            <option value="">Not decided yet</option>
            {funders.map((f) => (
              <option key={f.id} value={f.id}>
                {f.name}
              </option>
            ))}
          </select>
        </label>
        <label className="block text-sm">
          Catalogue programme
          <select
            value={form.programme_key}
            onChange={(e) => setForm({ ...form, programme_key: e.target.value })}
            className={`${input} mt-1 w-full`}
          >
            <option value="">None</option>
            {catalogue.map((c) => (
              <option key={c.key} value={c.key}>
                {c.name}
              </option>
            ))}
          </select>
        </label>
        <label className="block text-sm">
          Amount requested (£)
          <input
            type="number"
            min="0"
            step="1"
            value={form.amount_requested}
            onChange={(e) => setForm({ ...form, amount_requested: e.target.value })}
            className={`${input} mt-1 w-full`}
          />
        </label>
        <label className="block text-sm">
          Amount awarded (£)
          <input
            type="number"
            min="0"
            step="1"
            value={form.amount_awarded}
            onChange={(e) => setForm({ ...form, amount_awarded: e.target.value })}
            className={`${input} mt-1 w-full`}
          />
        </label>
        <label className="block text-sm">
          Funder&rsquo;s deadline
          <input
            type="date"
            value={form.deadline}
            onChange={(e) => setForm({ ...form, deadline: e.target.value })}
            className={`${input} mt-1 w-full`}
          />
        </label>
        <label className="block text-sm">
          Linked project
          <select
            value={form.project_id}
            onChange={(e) => setForm({ ...form, project_id: e.target.value })}
            className={`${input} mt-1 w-full`}
          >
            <option value="">Not linked</option>
            {projects.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
        </label>
        <label className="block text-sm">
          Grant start
          <input
            type="date"
            value={form.start_date}
            onChange={(e) => setForm({ ...form, start_date: e.target.value })}
            className={`${input} mt-1 w-full`}
          />
        </label>
        <label className="block text-sm">
          Grant end
          <input
            type="date"
            value={form.end_date}
            onChange={(e) => setForm({ ...form, end_date: e.target.value })}
            className={`${input} mt-1 w-full`}
          />
        </label>
      </div>
      {warning && (
        <p className="rounded-[10px] bg-warn-soft px-3 py-2 text-sm text-warn">
          This catalogue entry is {warning}.
        </p>
      )}
      <label className="flex items-center gap-2 text-sm">
        <input
          type="checkbox"
          checked={form.restricted}
          onChange={(e) => setForm({ ...form, restricted: e.target.checked })}
        />
        Restricted funding
      </label>
      {error && (
        <p className="rounded-[10px] bg-danger-soft px-3 py-2 text-sm text-danger">{error}</p>
      )}
      <div className="flex items-center gap-3">
        <button type="submit" disabled={busy || !form.title} className={btn}>
          {busy ? <Spinner /> : "Save"}
        </button>
        <button type="button" onClick={onCancel} className={btnGhost}>
          Cancel
        </button>
      </div>
    </form>
  );
}
