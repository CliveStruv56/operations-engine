"use client";

import { useEffect, useState } from "react";
import {
  Measure,
  Outcome,
  ReportingPeriod,
  achievedShare,
  fmtDate,
  fmtNum,
  gr,
} from "@/lib/grants";
import { btn, btnGhost, card, input, th } from "../../ui";
import { LoadError, useGrantLoad } from "./load";

const STATUSES = ["upcoming", "open", "drafting", "submitted", "accepted", "na"];

/** Recording outcomes for one period — the values a monitoring return renders
 *  as a table. They come from here and nowhere else. */
function Outcomes({
  id,
  period,
  measures,
}: {
  id: string;
  period: ReportingPeriod;
  measures: Measure[];
}) {
  const [outcomes, setOutcomes] = useState<Outcome[]>([]);
  const [saving, setSaving] = useState<string | null>(null);
  const base = `/grants/applications/${id}/reporting-periods/${period.id}/outcomes`;
  const { failed, refresh } = useGrantLoad<Outcome[]>(base, setOutcomes);

  const byMeasure = new Map(outcomes.map((o) => [o.measure_id, o]));

  async function record(measure: Measure, value: string, narrative: string) {
    setSaving(measure.id);
    try {
      await gr(`${base}/${measure.id}`, {
        method: "PUT",
        body: JSON.stringify({ value: value === "" ? null : value, narrative: narrative || null }),
      });
      refresh();
    } finally {
      setSaving(null);
    }
  }

  if (measures.length === 0)
    return (
      <p className="px-4 py-4 text-sm text-ink-muted">
        Add impact measures on the Impact tab first — a monitoring return reports against them.
      </p>
    );

  return (
    <div className="px-4 pb-4">
      <LoadError failed={failed} onRetry={refresh} />
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-line">
            <th className={th}>Measure</th>
            <th className={th}>Target</th>
            <th className={th}>Achieved</th>
            <th className={th}>Against target</th>
            <th className={th}>In your own words</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-line">
          {measures.map((measure) => {
            const outcome = byMeasure.get(measure.id);
            const share = achievedShare(outcome?.value ?? null, measure.target);
            return (
              <tr key={measure.id}>
                <td className="px-2 py-2">{measure.name}</td>
                <td className="data px-2 py-2 text-ink-faint">
                  {fmtNum(measure.target)} {measure.unit}
                </td>
                <td className="px-2 py-2">
                  <input
                    type="number"
                    defaultValue={outcome?.value ?? ""}
                    onBlur={(e) => record(measure, e.target.value, outcome?.narrative ?? "")}
                    placeholder="not recorded"
                    className={`${input} w-24`}
                  />
                </td>
                <td className="data px-2 py-2">
                  {share == null ? (
                    <span className="text-ink-faint">—</span>
                  ) : (
                    `${Math.round(share * 100)}%`
                  )}
                </td>
                <td className="px-2 py-2">
                  <input
                    defaultValue={outcome?.narrative ?? ""}
                    onBlur={(e) =>
                      record(measure, String(outcome?.value ?? ""), e.target.value)
                    }
                    placeholder="What the number meant for people"
                    className={`${input} w-full`}
                  />
                  {saving === measure.id && (
                    <span className="data text-ink-faint">saving…</span>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <p className="mt-2 text-xs text-ink-faint">
        A measure left blank stays &ldquo;not recorded&rdquo; in the return — it is never reported
        as zero.
      </p>
    </div>
  );
}

export function ReportingTab({ id }: { id: string }) {
  const [periods, setPeriods] = useState<ReportingPeriod[]>([]);
  const [measures, setMeasures] = useState<Measure[]>([]);
  const [open, setOpen] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [draft, setDraft] = useState({
    label: "",
    period_start: "",
    period_end: "",
    due_date: "",
  });
  const { failed, refresh } = useGrantLoad<ReportingPeriod[]>(
    `/grants/applications/${id}/reporting-periods`,
    setPeriods
  );

  useEffect(() => {
    gr<Measure[]>(`/grants/applications/${id}/measures`)
      .then(setMeasures)
      .catch(() => setMeasures([]));
  }, [id]);

  async function add(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await gr(`/grants/applications/${id}/reporting-periods`, {
        method: "POST",
        body: JSON.stringify({ ...draft, due_date: draft.due_date || null }),
      });
      setDraft({ label: "", period_start: "", period_end: "", due_date: "" });
      setAdding(false);
      refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  async function setStatus(period: ReportingPeriod, status: string) {
    await gr(`/grants/applications/${id}/reporting-periods/${period.id}`, {
      method: "PATCH",
      body: JSON.stringify({ status }),
    });
    refresh();
  }

  return (
    <div>
      <LoadError failed={failed} onRetry={refresh} />
      <div className="mb-3 flex items-center gap-3">
        <p className="text-sm text-ink-muted">
          What the funder expects back, and when. Overdue returns show on the portfolio calendar.
        </p>
        <button onClick={() => setAdding((v) => !v)} className={`${btnGhost} ml-auto shrink-0`}>
          {adding ? "Cancel" : "Add a period"}
        </button>
      </div>

      {adding && (
        <form onSubmit={add} className={`${card} mb-3 flex flex-wrap items-end gap-2 p-3`}>
          <label className="text-xs text-ink-muted">
            Label
            <input
              autoFocus
              required
              value={draft.label}
              onChange={(e) => setDraft({ ...draft, label: e.target.value })}
              placeholder="Year 1"
              className={`${input} mt-0.5 block`}
            />
          </label>
          <label className="text-xs text-ink-muted">
            From
            <input
              type="date"
              required
              value={draft.period_start}
              onChange={(e) => setDraft({ ...draft, period_start: e.target.value })}
              className={`${input} mt-0.5 block`}
            />
          </label>
          <label className="text-xs text-ink-muted">
            To
            <input
              type="date"
              required
              value={draft.period_end}
              onChange={(e) => setDraft({ ...draft, period_end: e.target.value })}
              className={`${input} mt-0.5 block`}
            />
          </label>
          <label className="text-xs text-ink-muted">
            Due to the funder
            <input
              type="date"
              value={draft.due_date}
              onChange={(e) => setDraft({ ...draft, due_date: e.target.value })}
              className={`${input} mt-0.5 block`}
            />
          </label>
          <button type="submit" className={btn}>
            Add
          </button>
        </form>
      )}

      {error && (
        <p className="mb-3 rounded-card bg-danger-soft px-3 py-2 text-sm text-danger">{error}</p>
      )}

      <div className="space-y-3">
        {periods.map((period) => (
          <div key={period.id} className={card}>
            <div className="flex flex-wrap items-center gap-3 px-4 py-3">
              <button
                onClick={() => setOpen(open === period.id ? null : period.id)}
                className="font-medium hover:underline"
              >
                {period.label}
              </button>
              <span className="data text-ink-faint">
                {fmtDate(period.period_start)} → {fmtDate(period.period_end)}
              </span>
              <span
                className={`data ${period.overdue ? "text-danger" : "text-ink-muted"}`}
                title="Date the funder expects the return"
              >
                due {fmtDate(period.due_date)}
                {period.overdue && " · overdue"}
              </span>
              <select
                value={period.status}
                onChange={(e) => setStatus(period, e.target.value)}
                className={`${input} ml-auto`}
              >
                {STATUSES.map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </select>
            </div>
            {open === period.id && <Outcomes id={id} period={period} measures={measures} />}
          </div>
        ))}
        {periods.length === 0 && (
          <div className={`${card} p-8 text-center`}>
            <p className="text-sm text-ink-muted">
              No reporting periods yet. Add the ones the offer letter requires — the monitoring
              return is drafted against a period, and its figures come from the outcomes you record
              here.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
