"use client";

import { Fragment, useCallback, useEffect, useState } from "react";
import { Funding, Programme, fmtDate, fmtMoney, gw } from "@/lib/groundwork";
import { LoadError, useGwLoad } from "./load";
import { btn, btnGhost, input } from "./ui";

export function FundingTab({ id }: { id: string }) {
  const [stack, setStack] = useState<Funding[]>([]);
  const [browse, setBrowse] = useState(false);
  const [programmes, setProgrammes] = useState<Programme[]>([]);
  const [progFailed, setProgFailed] = useState(false);
  const [nation, setNation] = useState("");
  const [expanded, setExpanded] = useState<string | null>(null);

  const { failed, refresh } = useGwLoad<Funding[]>(`/projects/${id}/funding`, setStack);

  const loadProgrammes = useCallback(() => {
    const q = nation ? `?nation=${nation}` : "";
    return gw<Programme[]>(`/projects/funding-programmes${q}`)
      .then((rows) => {
        setProgrammes(rows);
        setProgFailed(false);
      })
      .catch((err) => {
        console.error("Failed to load funding programmes", err);
        setProgFailed(true);
      });
  }, [nation]);
  useEffect(() => {
    if (browse) loadProgrammes();
  }, [browse, loadProgrammes]);

  async function addFromCatalogue(p: Programme) {
    await gw(`/projects/${id}/funding`, {
      method: "POST",
      body: JSON.stringify({ programme_key: p.key, name: p.name, funder: p.funder, kind: p.kind === "capital" || p.kind === "revenue" || p.kind === "advice" ? "grant" : p.kind === "equity_match" ? "equity_match" : "loan" }),
    });
    refresh();
  }

  async function patch(f: Funding, body: object) {
    await gw(`/projects/${id}/funding/${f.id}`, { method: "PATCH", body: JSON.stringify(body) });
    refresh();
  }

  return (
    <div className="flex gap-4">
      <div className="min-w-0 flex-1">
        <LoadError failed={failed} onRetry={refresh} />
        <div className="mb-3 flex justify-between">
          <p className="text-sm text-ink-muted">The funding stack for this project.</p>
          <button onClick={() => setBrowse(!browse)} className={btn}>
            {browse ? "Close programmes" : "Browse programmes"}
          </button>
        </div>
        <table className="w-full rounded-card border border-edge bg-surface text-sm">
          <thead>
            <tr className="data border-b border-line text-left text-ink-muted uppercase">
              <th className="px-3 py-2">Source</th>
              <th className="px-3 py-2">Kind</th>
              <th className="px-3 py-2">Sought</th>
              <th className="px-3 py-2">Secured</th>
              <th className="px-3 py-2">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {stack.map((f) => (
              <Fragment key={f.id}>
                <tr onClick={() => setExpanded(expanded === f.id ? null : f.id)} className="cursor-pointer hover:bg-accent-soft">
                  <td className="px-3 py-2 font-medium">
                    {f.name}
                    {f.funder && <span className="block text-xs font-normal text-ink-faint">{f.funder}</span>}
                  </td>
                  <td className="data px-3 py-2">{f.kind}</td>
                  <td className="px-3 py-2">
                    <input
                      type="number"
                      defaultValue={f.amount_sought ?? ""}
                      onClick={(e) => e.stopPropagation()}
                      onBlur={(e) => patch(f, { amount_sought: e.target.value ? Number(e.target.value) : null })}
                      className={`w-28 ${input}`}
                    />
                  </td>
                  <td className="px-3 py-2">
                    <input
                      type="number"
                      defaultValue={f.amount_secured ?? ""}
                      onClick={(e) => e.stopPropagation()}
                      onBlur={(e) => patch(f, { amount_secured: e.target.value ? Number(e.target.value) : null })}
                      className={`w-28 ${input}`}
                    />
                  </td>
                  <td className="px-3 py-2">
                    <select value={f.status} onClick={(e) => e.stopPropagation()} onChange={(e) => patch(f, { status: e.target.value })} className={input}>
                      {["identified", "applying", "offered", "secured", "drawing", "complete", "declined"].map((s) => (
                        <option key={s} value={s}>
                          {s}
                        </option>
                      ))}
                    </select>
                  </td>
                </tr>
                {expanded === f.id && (
                  <tr>
                    <td colSpan={5} className="bg-paper px-3 py-2">
                      <p className="data mb-1 text-ink-muted uppercase">Drawdown schedule</p>
                      {f.drawdown_schedule.length === 0 ? (
                        <p className="text-xs text-ink-faint">No drawdowns planned yet.</p>
                      ) : (
                        <ul className="space-y-0.5 text-xs">
                          {f.drawdown_schedule.map((dd, i) => (
                            <li key={i} className="flex justify-between">
                              <span>{dd.label}</span>
                              <span className="data">
                                {fmtDate(dd.due_date)} · {fmtMoney(dd.amount ?? null)} · {dd.status}
                              </span>
                            </li>
                          ))}
                        </ul>
                      )}
                    </td>
                  </tr>
                )}
              </Fragment>
            ))}
          </tbody>
        </table>
      </div>

      {browse && (
        <aside className="w-96 shrink-0 rounded-card border border-edge bg-surface p-3">
          <select value={nation} onChange={(e) => setNation(e.target.value)} className={`mb-2 w-full ${input}`}>
            <option value="">All nations</option>
            <option value="england">England</option>
            <option value="scotland">Scotland</option>
            <option value="wales">Wales</option>
          </select>
          {progFailed && (
            <p role="alert" className="mb-2 flex items-center justify-between gap-2 rounded-card bg-danger-soft px-2 py-1.5 text-xs text-danger">
              Programme catalogue failed to load.
              <button onClick={loadProgrammes} className="shrink-0 underline">
                Retry
              </button>
            </p>
          )}
          <ul className="max-h-130 space-y-2 overflow-y-auto">
            {programmes.map((p) => (
              <li key={p.key} className="rounded-card border border-line p-2 text-sm">
                <p className="font-medium">
                  {p.name}
                  {p.stale && (
                    <span className="stamp ml-1 text-warn bg-warn-soft" title={`Facts last verified ${fmtDate(p.last_verified)} — due a review`}>
                      verify
                    </span>
                  )}
                </p>
                <p className="data mt-0.5 text-ink-muted">
                  {p.funder} · {p.kind} · {p.status}
                </p>
                {p.amount_note && <p className="mt-0.5 text-xs text-ink-muted">{p.amount_note}</p>}
                <p className="mt-0.5 text-xs text-ink-faint">{p.eligibility}</p>
                <button onClick={() => addFromCatalogue(p)} className={`mt-1.5 ${btnGhost}`}>
                  Add to project
                </button>
              </li>
            ))}
          </ul>
        </aside>
      )}
    </div>
  );
}
