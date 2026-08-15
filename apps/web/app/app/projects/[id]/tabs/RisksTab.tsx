"use client";

import { useState } from "react";
import { Risk, gw } from "@/lib/groundwork";
import { LoadError, useGwLoad } from "./load";
import { btn, input } from "./ui";

export function RisksTab({ id }: { id: string }) {
  const [risks, setRisks] = useState<Risk[]>([]);
  const [desc, setDesc] = useState("");
  const [likelihood, setLikelihood] = useState(3);
  const [impact, setImpact] = useState(3);

  const { failed, refresh } = useGwLoad<Risk[]>(`/projects/${id}/risks`, setRisks);

  async function add(e: React.FormEvent) {
    e.preventDefault();
    await gw(`/projects/${id}/risks`, {
      method: "POST",
      body: JSON.stringify({ category: "manual", description: desc, likelihood, impact }),
    });
    setDesc("");
    refresh();
  }

  async function patch(r: Risk, body: object) {
    await gw(`/projects/${id}/risks/${r.id}`, { method: "PATCH", body: JSON.stringify(body) });
    refresh();
  }

  return (
    <div>
      <LoadError failed={failed} onRetry={refresh} />
      {risks.length === 0 && !failed ? (
        <p className="text-sm text-ink-faint">
          No risks on the register yet — describe the first one below.
        </p>
      ) : (
      <table className="w-full rounded-card border border-edge bg-surface text-sm">
        <thead>
          <tr className="data border-b border-line text-left text-ink-muted uppercase">
            <th className="px-3 py-2">Risk</th>
            <th className="px-3 py-2">L</th>
            <th className="px-3 py-2">I</th>
            <th className="px-3 py-2">Score</th>
            <th className="px-3 py-2">Mitigation</th>
            <th className="px-3 py-2">Status</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-line">
          {risks.map((r) => (
            <tr key={r.id} className={r.status === "closed" ? "opacity-50" : ""}>
              <td className="max-w-60 px-3 py-2">{r.description}</td>
              {(["likelihood", "impact"] as const).map((k) => (
                <td key={k} className="px-3 py-2">
                  <select value={r[k]} onChange={(e) => patch(r, { [k]: Number(e.target.value) })} className={input}>
                    {[1, 2, 3, 4, 5].map((n) => (
                      <option key={n} value={n}>
                        {n}
                      </option>
                    ))}
                  </select>
                </td>
              ))}
              <td className={`data px-3 py-2 ${r.likelihood * r.impact >= 16 ? "text-danger" : r.likelihood * r.impact >= 9 ? "text-warn" : ""}`}>
                {r.likelihood * r.impact}
              </td>
              <td className="max-w-60 px-3 py-2 text-xs text-ink-muted">{r.mitigation}</td>
              <td className="px-3 py-2">
                <select value={r.status} onChange={(e) => patch(r, { status: e.target.value })} className={input}>
                  <option value="open">open</option>
                  <option value="monitoring">monitoring</option>
                  <option value="closed">closed</option>
                </select>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      )}
      <form onSubmit={add} className="mt-3 flex flex-wrap items-center gap-2">
        <input required value={desc} onChange={(e) => setDesc(e.target.value)} placeholder="Describe a new risk…" className={`min-w-0 flex-1 ${input}`} />
        <label className="text-sm text-ink-muted">
          L{" "}
          <select value={likelihood} onChange={(e) => setLikelihood(Number(e.target.value))} className={input}>
            {[1, 2, 3, 4, 5].map((n) => (
              <option key={n}>{n}</option>
            ))}
          </select>
        </label>
        <label className="text-sm text-ink-muted">
          I{" "}
          <select value={impact} onChange={(e) => setImpact(Number(e.target.value))} className={input}>
            {[1, 2, 3, 4, 5].map((n) => (
              <option key={n}>{n}</option>
            ))}
          </select>
        </label>
        <button type="submit" className={btn}>
          Add risk
        </button>
      </form>
    </div>
  );
}
