"use client";

import { useState } from "react";
import { Budget, BudgetLine, fmtMoney, gw } from "@/lib/groundwork";
import { LoadError, useGwLoad } from "./load";
import { btn, btnGhost, input } from "./ui";

const CATEGORIES = ["land", "construction", "externals", "abnormals", "fees", "statutory", "contingency", "finance", "other"];

export function BudgetTab({ id }: { id: string }) {
  const [lines, setLines] = useState<BudgetLine[]>([]);
  const [dirty, setDirty] = useState(false);

  const { failed, refresh } = useGwLoad<Budget>(`/projects/${id}/budget`, (b) =>
    setLines(b.lines)
  );

  const update = (i: number, patch: Partial<BudgetLine>) => {
    setLines((ls) => ls.map((l, j) => (j === i ? { ...l, ...patch } : l)));
    setDirty(true);
  };

  async function save() {
    await gw(`/projects/${id}/budget`, { method: "PUT", body: JSON.stringify(lines) });
    setDirty(false);
  }

  const total = (k: "budget" | "forecast" | "actual") => lines.reduce((s, l) => s + (Number(l[k]) || 0), 0);
  const variance = total("forecast") - total("budget");

  return (
    <div>
      <LoadError failed={failed} onRetry={refresh} />
      <table className="w-full rounded-md border border-line bg-surface text-sm">
        <thead>
          <tr className="data border-b border-line text-left text-ink-muted uppercase">
            <th className="px-3 py-2">Category</th>
            <th className="px-3 py-2">Line</th>
            <th className="px-3 py-2">Budget</th>
            <th className="px-3 py-2">Forecast</th>
            <th className="px-3 py-2">Actual</th>
            <th className="px-3 py-2" />
          </tr>
        </thead>
        <tbody className="divide-y divide-line">
          {lines.map((l, i) => (
            <tr key={i}>
              <td className="px-3 py-1.5">
                <select value={l.category} onChange={(e) => update(i, { category: e.target.value })} className={input}>
                  {CATEGORIES.map((c) => (
                    <option key={c} value={c}>
                      {c}
                    </option>
                  ))}
                </select>
              </td>
              <td className="px-3 py-1.5">
                <input value={l.label} onChange={(e) => update(i, { label: e.target.value })} className={`w-full ${input}`} />
              </td>
              {(["budget", "forecast", "actual"] as const).map((k) => (
                <td key={k} className="px-3 py-1.5">
                  <input type="number" value={l[k]} onChange={(e) => update(i, { [k]: Number(e.target.value) })} className={`w-28 ${input}`} />
                </td>
              ))}
              <td className="px-3 py-1.5">
                <button onClick={() => { setLines((ls) => ls.filter((_, j) => j !== i)); setDirty(true); }} className={btnGhost}>
                  Remove
                </button>
              </td>
            </tr>
          ))}
        </tbody>
        <tfoot>
          <tr className="border-t border-line font-medium">
            <td className="px-3 py-2" colSpan={2}>
              Totals
            </td>
            <td className="px-3 py-2">{fmtMoney(total("budget"))}</td>
            <td className={`px-3 py-2 ${variance > 0 ? "text-danger" : ""}`}>{fmtMoney(total("forecast"))}</td>
            <td className="px-3 py-2">{fmtMoney(total("actual"))}</td>
            <td className={`data px-3 py-2 ${variance > 0 ? "text-danger" : "text-accent"}`}>
              {variance > 0 ? "+" : ""}
              {fmtMoney(variance)} var.
            </td>
          </tr>
        </tfoot>
      </table>
      <div className="mt-3 flex gap-2">
        <button onClick={() => { setLines((ls) => [...ls, { category: "other", label: "", budget: 0, forecast: 0, actual: 0 }]); setDirty(true); }} className={btnGhost}>
          + Add line
        </button>
        {dirty && (
          <button onClick={save} className={btn}>
            Save budget
          </button>
        )}
      </div>
    </div>
  );
}
