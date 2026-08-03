"use client";

import { useState } from "react";
import { Condition, fmtDate, gr } from "@/lib/grants";
import { btnGhost, card, input, th } from "../../ui";
import { LoadError, useGrantLoad } from "./load";

const STATUSES = ["outstanding", "submitted", "partially_discharged", "discharged", "na"];

export function ConditionsTab({ id }: { id: string }) {
  const [rows, setRows] = useState<Condition[]>([]);
  const [adding, setAdding] = useState(false);
  const [draft, setDraft] = useState({ number: "", description: "", pre_drawdown: false });
  const { failed, refresh } = useGrantLoad<Condition[]>(
    `/grants/applications/${id}/conditions`,
    setRows
  );

  async function setStatus(condition: Condition, status: string) {
    await gr(`/grants/applications/${id}/conditions/${condition.id}`, {
      method: "PATCH",
      body: JSON.stringify({ status }),
    });
    refresh();
  }

  async function add(e: React.FormEvent) {
    e.preventDefault();
    if (!draft.number.trim() || !draft.description.trim()) return;
    await gr(`/grants/applications/${id}/conditions`, {
      method: "POST",
      body: JSON.stringify(draft),
    });
    setDraft({ number: "", description: "", pre_drawdown: false });
    setAdding(false);
    refresh();
  }

  const outstanding = rows.filter((r) =>
    ["outstanding", "partially_discharged"].includes(r.status)
  ).length;

  return (
    <div>
      <LoadError failed={failed} onRetry={refresh} />
      <div className="mb-3 flex items-center gap-3">
        <span className="text-sm text-ink-muted">
          {outstanding} outstanding of {rows.length}
        </span>
        <button onClick={() => setAdding((v) => !v)} className={`${btnGhost} ml-auto`}>
          {adding ? "Cancel" : "Add a condition"}
        </button>
      </div>

      {adding && (
        <form onSubmit={add} className={`${card} mb-3 flex flex-wrap items-center gap-2 p-3`}>
          <input
            autoFocus
            value={draft.number}
            onChange={(e) => setDraft({ ...draft, number: e.target.value })}
            placeholder="No."
            className={`${input} w-16`}
          />
          <input
            value={draft.description}
            onChange={(e) => setDraft({ ...draft, description: e.target.value })}
            placeholder="What the funder requires"
            className={`${input} flex-1`}
          />
          <label className="flex items-center gap-1.5 text-sm">
            <input
              type="checkbox"
              checked={draft.pre_drawdown}
              onChange={(e) => setDraft({ ...draft, pre_drawdown: e.target.checked })}
            />
            Pre-drawdown
          </label>
          <button type="submit" className={input}>
            Add
          </button>
        </form>
      )}

      {rows.length === 0 ? (
        <div className={`${card} p-8 text-center`}>
          <p className="text-sm text-ink-muted">
            No conditions yet. The standard set is added automatically when you record the award —
            an application still being written has no offer, so it has no obligations either.
          </p>
        </div>
      ) : (
        <div className={`overflow-x-auto ${card}`}>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-line">
                <th className={th}>No.</th>
                <th className={th}>Condition</th>
                <th className={th}>Due</th>
                <th className={th}>Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {rows.map((row) => (
                <tr key={row.id}>
                  <td className="data px-4 py-2.5">{row.number}</td>
                  <td className="px-4 py-2.5">
                    {row.description}
                    {row.pre_drawdown && (
                      <span className="stamp ml-2 text-warn bg-warn-soft">
                        before drawdown
                      </span>
                    )}
                  </td>
                  <td className="data px-4 py-2.5 text-ink-faint">{fmtDate(row.due_date)}</td>
                  <td className="px-4 py-2.5">
                    <select
                      value={row.status}
                      onChange={(e) => setStatus(row, e.target.value)}
                      className={input}
                    >
                      {STATUSES.map((s) => (
                        <option key={s} value={s}>
                          {s.replace("_", " ")}
                        </option>
                      ))}
                    </select>
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
