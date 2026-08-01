"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { gw } from "@/lib/groundwork";
import { Spinner } from "@/components/activity";

const TOGGLES = [
  { key: "wales", label: "In Wales", hint: "Adds the SAB drainage approval task" },
  {
    key: "hrb",
    label: "Higher-Risk Building",
    hint: "18m+/7+ storeys — adds the BSR gateway task and a reminder banner",
  },
  {
    key: "bng_exempt",
    label: "BNG exempt",
    hint: "Skips the biodiversity net gain task (self-build/small sites exemption)",
  },
  {
    key: "conservation_area",
    label: "Conservation area",
    hint: "Adds heritage officer pre-app engagement",
  },
] as const;

export default function NewProjectPage() {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState({
    name: "",
    client_org: "",
    delivery_route: "",
    homes_planned: "",
    start_date: "",
    target_completion: "",
    site_address: "",
  });
  const [flags, setFlags] = useState<Record<string, boolean>>({});

  const set = (k: string) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
    setForm((f) => ({ ...f, [k]: e.target.value }));

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const core = await gw<{ id: string }>("/projects", {
        method: "POST",
        body: JSON.stringify({ name: form.name }),
      });
      await gw(`/projects/${core.id}/setup`, {
        method: "POST",
        body: JSON.stringify({
          client_org: form.client_org || null,
          delivery_route: form.delivery_route || null,
          homes_planned: form.homes_planned ? Number(form.homes_planned) : null,
          start_date: form.start_date || null,
          target_completion: form.target_completion || null,
          site_address: form.site_address || null,
          applicability: flags,
        }),
      });
      router.push(`/app/projects/${core.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setBusy(false);
    }
  }

  const input = "w-full rounded-sm border border-line bg-surface px-3 py-2 text-sm";

  return (
    <main className="min-h-0 flex-1 overflow-y-auto">
      <div className="mx-auto max-w-2xl p-6">
      <p className="data text-ink-faint uppercase">
        <Link href="/app/projects" className="hover:text-ink">
          ← Development projects
        </Link>
      </p>
      <h1 className="mt-1 mb-6 text-xl font-semibold tracking-tight">New development project</h1>

      <form onSubmit={submit} className="space-y-5 rounded-md border border-line bg-surface p-6">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <label className="text-sm sm:col-span-2">
            Project name
            <input required value={form.name} onChange={set("name")} className={`mt-1 ${input}`} placeholder="e.g. Millbrook Meadow" />
          </label>
          <label className="text-sm">
            Client group
            <input value={form.client_org} onChange={set("client_org")} className={`mt-1 ${input}`} placeholder="e.g. Millbrook Meadow CLT" />
          </label>
          <label className="text-sm">
            Delivery route
            <select value={form.delivery_route} onChange={set("delivery_route")} className={`mt-1 ${input}`}>
              <option value="">Not decided yet</option>
              <option value="direct">Direct development</option>
              <option value="ha_partnership">Housing association partnership</option>
              <option value="council_enabled">Council-enabled</option>
            </select>
          </label>
          <label className="text-sm">
            Homes planned
            <input type="number" min={1} value={form.homes_planned} onChange={set("homes_planned")} className={`mt-1 ${input}`} />
          </label>
          <label className="text-sm">
            Site address
            <input value={form.site_address} onChange={set("site_address")} className={`mt-1 ${input}`} />
          </label>
          <label className="text-sm">
            Start date
            <input type="date" value={form.start_date} onChange={set("start_date")} className={`mt-1 ${input}`} />
          </label>
          <label className="text-sm">
            Target completion
            <input type="date" value={form.target_completion} onChange={set("target_completion")} className={`mt-1 ${input}`} />
          </label>
        </div>

        <fieldset className="space-y-2 border-t border-line pt-4">
          <legend className="data pb-1 text-ink-muted uppercase">What applies to this scheme?</legend>
          {TOGGLES.map((t) => (
            <label key={t.key} className="flex items-start gap-2 text-sm">
              <input
                type="checkbox"
                checked={flags[t.key] ?? false}
                onChange={(e) => setFlags((f) => ({ ...f, [t.key]: e.target.checked }))}
                className="mt-0.5 accent-(--accent)"
              />
              <span>
                {t.label}
                <span className="block text-xs text-ink-faint">{t.hint}</span>
              </span>
            </label>
          ))}
        </fieldset>

        {error && <p className="rounded-sm bg-danger-soft px-3 py-2 text-sm text-danger">{error}</p>}
        <button
          type="submit"
          disabled={busy}
          className="w-full rounded-sm bg-accent px-4 py-2 text-sm font-medium text-accent-ink hover:opacity-90 disabled:opacity-50"
        >
          {busy ? (
            <>
              <Spinner className="mr-1.5" /> Setting up the project spine…
            </>
          ) : (
            "Create project"
          )}
        </button>
        <p className="text-xs text-ink-faint">
          Creates the five-stage plan with gate checklists, the full task list, the document
          checklist and the standard risk register — ready to edit down.
        </p>
      </form>
      </div>
    </main>
  );
}
