"use client";

import { useState } from "react";
import { Spinner } from "@/components/activity";
import { DraftJob, Measure, getDraftJob, gr, submitImpactCard } from "@/lib/grants";
import { openPresigned } from "@/lib/groundwork";
import { btn, btnGhost, card, input, th } from "../../ui";
import { LoadError, useGrantLoad } from "./load";

const POLL_MS = 3000;

/** The funder-facing one-pager. No model touches it, so every figure on it is
 *  a value somebody recorded — which is why it is safe to send outward. */
function ImpactCard({ id }: { id: string }) {
  const [job, setJob] = useState<DraftJob | null>(null);
  const [error, setError] = useState<string | null>(null);
  const running = job !== null && (job.status === "queued" || job.status === "running");

  async function generate() {
    setError(null);
    try {
      const started = await submitImpactCard(id);
      setJob(started);
      const timer = setInterval(async () => {
        try {
          const next = await getDraftJob(started.id);
          setJob(next);
          if (next.status !== "queued" && next.status !== "running") clearInterval(timer);
        } catch {
          clearInterval(timer);
        }
      }, POLL_MS);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  return (
    <div className={`${card} mb-4 p-4`}>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h3 className="font-medium">Impact card</h3>
          <p className="mt-0.5 text-sm text-ink-muted">
            A one-page PDF for the funder. Assembled straight from the recorded figures — no model
            writes any part of it.
          </p>
        </div>
        <button onClick={generate} disabled={running} className={btn}>
          {running ? (
            <>
              <Spinner className="mr-1.5" /> Building…
            </>
          ) : (
            "Create impact card"
          )}
        </button>
      </div>
      {job?.status === "succeeded" && job.download_url && (
        <button onClick={() => openPresigned(job.download_url!)} className={`${btnGhost} mt-3`}>
          Download the impact card
        </button>
      )}
      {job?.status === "failed" && (
        <p className="mt-3 rounded-[10px] bg-danger-soft px-3 py-2 text-sm text-danger">
          {job.error ?? "The impact card failed."}
        </p>
      )}
      {error && (
        <p className="mt-3 rounded-[10px] bg-danger-soft px-3 py-2 text-sm text-danger">{error}</p>
      )}
    </div>
  );
}

export function ImpactTab({ id }: { id: string }) {
  const [measures, setMeasures] = useState<Measure[]>([]);
  const [adding, setAdding] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [draft, setDraft] = useState({ name: "", unit: "count", baseline: "", target: "" });
  const { failed, refresh } = useGrantLoad<Measure[]>(
    `/grants/applications/${id}/measures`,
    setMeasures
  );

  async function add(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await gr(`/grants/applications/${id}/measures`, {
        method: "POST",
        body: JSON.stringify({
          name: draft.name,
          unit: draft.unit || "count",
          baseline: draft.baseline || null,
          target: draft.target || null,
        }),
      });
      setDraft({ name: "", unit: "count", baseline: "", target: "" });
      setAdding(false);
      refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  async function remove(measure: Measure) {
    if (
      !window.confirm(
        `Delete "${measure.name}"? Every outcome recorded against it goes too — the values have no meaning without the measure.`
      )
    )
      return;
    await gr(`/grants/applications/${id}/measures/${measure.id}`, { method: "DELETE" });
    refresh();
  }

  return (
    <div>
      <ImpactCard id={id} />
      <LoadError failed={failed} onRetry={refresh} />

      <div className="mb-3 flex items-center gap-3">
        <p className="text-sm text-ink-muted">
          What this grant promised to change. Values are recorded per reporting period.
        </p>
        <button onClick={() => setAdding((v) => !v)} className={`${btnGhost} ml-auto shrink-0`}>
          {adding ? "Cancel" : "Add a measure"}
        </button>
      </div>

      {adding && (
        <form onSubmit={add} className={`${card} mb-3 flex flex-wrap items-end gap-2 p-3`}>
          <label className="flex-1 text-xs text-ink-muted">
            Measure
            <input
              autoFocus
              required
              value={draft.name}
              onChange={(e) => setDraft({ ...draft, name: e.target.value })}
              placeholder="Beneficiaries reached"
              className={`${input} mt-0.5 block w-full`}
            />
          </label>
          <label className="text-xs text-ink-muted">
            Unit
            <input
              value={draft.unit}
              onChange={(e) => setDraft({ ...draft, unit: e.target.value })}
              placeholder="people"
              className={`${input} mt-0.5 block w-24`}
            />
          </label>
          <label className="text-xs text-ink-muted">
            Baseline
            <input
              type="number"
              value={draft.baseline}
              onChange={(e) => setDraft({ ...draft, baseline: e.target.value })}
              className={`${input} mt-0.5 block w-24`}
            />
          </label>
          <label className="text-xs text-ink-muted">
            Target
            <input
              type="number"
              value={draft.target}
              onChange={(e) => setDraft({ ...draft, target: e.target.value })}
              className={`${input} mt-0.5 block w-24`}
            />
          </label>
          <button type="submit" className={btn}>
            Add
          </button>
        </form>
      )}

      {error && (
        <p className="mb-3 rounded-[10px] bg-danger-soft px-3 py-2 text-sm text-danger">{error}</p>
      )}

      {measures.length === 0 ? (
        <div className={`${card} p-8 text-center`}>
          <p className="text-sm text-ink-muted">
            No measures yet. These are what the application promised — add them before the first
            monitoring return is due.
          </p>
        </div>
      ) : (
        <div className={`overflow-x-auto ${card}`}>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-line">
                <th className={th}>Measure</th>
                <th className={th}>Unit</th>
                <th className={th}>Baseline</th>
                <th className={th}>Target</th>
                <th className={th}></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {measures.map((measure) => (
                <tr key={measure.id}>
                  <td className="px-4 py-2.5 font-medium">{measure.name}</td>
                  <td className="data px-4 py-2.5 text-ink-faint">{measure.unit}</td>
                  <td className="data px-4 py-2.5">{measure.baseline ?? "—"}</td>
                  <td className="data px-4 py-2.5">{measure.target ?? "—"}</td>
                  <td className="px-4 py-2.5 text-right">
                    <button onClick={() => remove(measure)} className={btnGhost}>
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
