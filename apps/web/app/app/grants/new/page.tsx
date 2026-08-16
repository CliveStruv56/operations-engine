"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Spinner } from "@/components/activity";
import { CatalogueRow, Funder, catalogueWarning, gr } from "@/lib/grants";
import { GRANTS_DISABLED, ModuleDisabled, useModuleEnabled } from "../../module-gate";
import { useWorkspace } from "../../workspace";
import { btn, card, input } from "../ui";

export default function NewApplicationPage() {
  const router = useRouter();
  const ws = useWorkspace();
  const flagOn = useModuleEnabled("grants");
  const [funders, setFunders] = useState<Funder[]>([]);
  const [catalogue, setCatalogue] = useState<CatalogueRow[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState({
    title: "",
    funder_id: "",
    programme_key: "",
    project_id: "",
    amount_requested: "",
    deadline: "",
    restricted: true,
  });
  const [addingFunder, setAddingFunder] = useState(false);
  const [newFunderName, setNewFunderName] = useState("");

  useEffect(() => {
    if (flagOn !== true) return;
    gr<Funder[]>("/grants/funders").then(setFunders).catch(() => setFunders([]));
    gr<CatalogueRow[]>("/grants/funder-catalogue").then(setCatalogue).catch(() => setCatalogue([]));
  }, [flagOn]);

  if (flagOn === false) return <ModuleDisabled {...GRANTS_DISABLED} />;

  const chosen = catalogue.find((c) => c.key === form.programme_key);
  const warning = chosen ? catalogueWarning(chosen) : null;
  const devProjects = ws.projects.filter((p) => !p.archived);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const created = await gr<{ id: string }>("/grants/applications", {
        method: "POST",
        body: JSON.stringify({
          title: form.title,
          funder_id: form.funder_id || null,
          programme_key: form.programme_key || null,
          project_id: form.project_id || null,
          amount_requested: form.amount_requested || null,
          deadline: form.deadline || null,
          restricted: form.restricted,
        }),
      });
      router.push(`/app/grants/${created.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setBusy(false);
    }
  }

  async function addFunder() {
    if (!newFunderName.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const created = await gr<Funder>("/grants/funders", {
        method: "POST",
        body: JSON.stringify({ name: newFunderName.trim() }),
      });
      setFunders((rows) => [...rows, created].sort((a, b) => a.name.localeCompare(b.name)));
      setForm((f) => ({ ...f, funder_id: created.id }));
      setNewFunderName("");
      setAddingFunder(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="min-h-0 flex-1 overflow-y-auto">
      <div className="mx-auto max-w-2xl p-6">
        <p className="data text-ink-faint uppercase">
          <Link href="/app/grants" className="hover:text-ink">
            ← Grant funding
          </Link>
        </p>
        <h1 className="mt-1 mb-1 font-display text-[26px] font-medium tracking-[-0.01em]">
          New application
        </h1>
        <p className="mb-5 text-sm text-ink-muted">
          The full stage plan, task list and document checklist are created with it.
        </p>

        <form onSubmit={submit} className={`${card} space-y-4 p-5`}>
          <label className="block">
            <span className="data text-ink-muted uppercase">What are you applying for</span>
            <input
              required
              autoFocus
              value={form.title}
              onChange={(e) => setForm({ ...form, title: e.target.value })}
              placeholder="e.g. Community garden — three-year revenue"
              className={`${input} mt-1 w-full`}
            />
          </label>

          <div className="grid gap-4 sm:grid-cols-2">
            <label className="block">
              <span className="data text-ink-muted uppercase">Funder</span>
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
              {addingFunder ? (
                <div className="mt-2 flex gap-2">
                  <input
                    autoFocus
                    value={newFunderName}
                    onChange={(e) => setNewFunderName(e.target.value)}
                    placeholder="Funder's name"
                    className={`${input} min-w-0 flex-1`}
                  />
                  <button type="button" onClick={addFunder} disabled={busy} className={btn}>
                    Add
                  </button>
                  <button
                    type="button"
                    onClick={() => setAddingFunder(false)}
                    className="text-xs text-ink-muted underline"
                  >
                    Cancel
                  </button>
                </div>
              ) : (
                <button
                  type="button"
                  onClick={() => setAddingFunder(true)}
                  className="mt-1 text-xs text-ink-muted underline hover:text-ink"
                >
                  Add a funder
                </button>
              )}
            </label>

            <label className="block">
              <span className="data text-ink-muted uppercase">Catalogue programme</span>
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
          </div>

          {warning && (
            <p className="rounded-card bg-warn-soft px-3 py-2 text-sm text-warn">
              This catalogue entry is {warning}. Any bid drafted from it carries the same warning on
              its first page.
            </p>
          )}

          <div className="grid gap-4 sm:grid-cols-2">
            <label className="block">
              <span className="data text-ink-muted uppercase">Amount requested (£)</span>
              <input
                type="number"
                min="0"
                step="1"
                value={form.amount_requested}
                onChange={(e) => setForm({ ...form, amount_requested: e.target.value })}
                className={`${input} mt-1 w-full`}
              />
            </label>
            <label className="block">
              <span className="data text-ink-muted uppercase">Funder&rsquo;s deadline</span>
              <input
                type="date"
                value={form.deadline}
                onChange={(e) => setForm({ ...form, deadline: e.target.value })}
                className={`${input} mt-1 w-full`}
              />
            </label>
          </div>

          {devProjects.length > 0 && (
            <label className="block">
              <span className="data text-ink-muted uppercase">Linked project (optional)</span>
              <select
                value={form.project_id}
                onChange={(e) => setForm({ ...form, project_id: e.target.value })}
                className={`${input} mt-1 w-full`}
              >
                <option value="">Not linked</option>
                {devProjects.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </select>
              <span className="mt-1 block text-xs text-ink-faint">
                Linking a bid to the project it funds lets its drafts draw on that project&rsquo;s
                documents first.
              </span>
            </label>
          )}

          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={form.restricted}
              onChange={(e) => setForm({ ...form, restricted: e.target.checked })}
            />
            Restricted funding (spendable only on this project)
          </label>

          {error && (
            <p className="rounded-card bg-danger-soft px-3 py-2 text-sm text-danger">{error}</p>
          )}

          <button type="submit" disabled={busy || !form.title} className={btn}>
            {busy ? <Spinner /> : "Create application"}
          </button>
        </form>
      </div>
    </main>
  );
}
