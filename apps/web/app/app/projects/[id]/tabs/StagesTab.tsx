"use client";

import { useState } from "react";
import { Stage, fmtDate, gw } from "@/lib/groundwork";
import { LoadError, useGwLoad } from "./load";
import { btn, input } from "./ui";

export function StagesTab({ id, onAdvanced }: { id: string; onAdvanced: () => void }) {
  const [stages, setStages] = useState<Stage[]>([]);
  const [open, setOpen] = useState<string | null>(null);
  const [exceptions, setExceptions] = useState("");
  const [error, setError] = useState<string | null>(null);

  const { failed, refresh } = useGwLoad<Stage[]>(`/projects/${id}/stages`, setStages);

  async function toggle(stage: Stage, itemId: string) {
    try {
      await gw(`/projects/${id}/stages/${stage.id}/gate/${itemId}/toggle`, { method: "POST" });
      refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  async function signoff(stage: Stage) {
    setError(null);
    try {
      await gw(`/projects/${id}/stages/${stage.id}/signoff`, {
        method: "POST",
        body: JSON.stringify({ exceptions: exceptions || null }),
      });
      setExceptions("");
      refresh();
      onAdvanced();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  async function setDate(stage: Stage, field: string, value: string) {
    await gw(`/projects/${id}/stages/${stage.id}`, {
      method: "PATCH",
      body: JSON.stringify({ [field]: value || null }),
    });
    refresh();
  }

  return (
    <div className="space-y-3">
      <LoadError failed={failed} onRetry={refresh} className="mb-0" />
      {error && <p className="rounded-sm bg-danger-soft px-3 py-2 text-sm text-danger">{error}</p>}
      {stages.map((s) => {
        const outstanding = s.gate.filter((g) => !g.done).length;
        const expanded = open === s.id;
        return (
          <section key={s.id} className="rounded-md border border-line bg-surface">
            <button
              onClick={() => setOpen(expanded ? null : s.id)}
              className="flex w-full items-center justify-between px-4 py-3 text-left"
            >
              <span className="flex items-center gap-3">
                <span className="font-medium">{s.label}</span>
                {s.riba_ref && <span className="data text-ink-faint">{s.riba_ref}</span>}
                <span
                  className={`stamp ${
                    s.status === "passed"
                      ? "text-accent bg-accent-soft"
                      : s.status === "active"
                        ? "text-warn bg-warn-soft"
                        : s.status === "regressed"
                          ? "text-danger bg-danger-soft"
                          : "text-ink-faint"
                  }`}
                >
                  {s.status}
                </span>
              </span>
              <span className="data text-ink-muted">
                {s.gate_signed_off_at
                  ? `signed off ${fmtDate(s.gate_signed_off_at)}`
                  : `${s.gate.length - outstanding}/${s.gate.length} gate items`}
              </span>
            </button>
            {expanded && (
              <div className="border-t border-line px-4 py-3">
                <div className="mb-3 grid grid-cols-2 gap-2 sm:grid-cols-3">
                  {(
                    [
                      ["planned_start", "Planned start"],
                      ["planned_end", "Planned end"],
                      ["forecast_start", "Forecast start"],
                      ["forecast_end", "Forecast end"],
                      ["actual_start", "Actual start"],
                      ["actual_end", "Actual end"],
                    ] as const
                  ).map(([field, label]) => (
                    <label key={field} className="text-xs text-ink-muted">
                      {label}
                      <input
                        type="date"
                        defaultValue={(s[field] as string | null) ?? ""}
                        onBlur={(e) => setDate(s, field, e.target.value)}
                        className={`mt-0.5 block w-full ${input}`}
                      />
                    </label>
                  ))}
                </div>
                <ul className="space-y-1.5">
                  {s.gate.map((g) => (
                    <li key={g.id} className="flex items-center gap-2 text-sm">
                      {g.kind === "manual" ? (
                        <input
                          type="checkbox"
                          checked={g.done}
                          onChange={() => toggle(s, g.id)}
                          disabled={!!s.gate_signed_off_at}
                          className="accent-(--accent)"
                        />
                      ) : (
                        <span
                          title="Follows the document registry — reaches done when the linked document is final or submitted"
                          className={`data ${g.done ? "text-accent" : "text-ink-faint"}`}
                        >
                          {g.done ? "▣" : "▢"}
                        </span>
                      )}
                      <span className={g.done ? "text-ink-muted line-through" : ""}>
                        {g.criterion}
                      </span>
                      {g.kind === "doc" && (
                        <span className="data text-ink-faint">from registry: {g.ref}</span>
                      )}
                    </li>
                  ))}
                </ul>
                {s.gate_exceptions && (
                  <p className="mt-3 rounded-sm bg-warn-soft px-3 py-2 text-xs whitespace-pre-wrap text-warn">
                    Exceptions & notes: {s.gate_exceptions}
                  </p>
                )}
                {!s.gate_signed_off_at && (
                  <div className="mt-3 flex items-center gap-2">
                    {outstanding > 0 && (
                      <input
                        value={exceptions}
                        onChange={(e) => setExceptions(e.target.value)}
                        placeholder={`${outstanding} item(s) outstanding — record exceptions to sign off anyway`}
                        className={`min-w-0 flex-1 ${input}`}
                      />
                    )}
                    <button
                      onClick={() => signoff(s)}
                      disabled={outstanding > 0 && !exceptions}
                      className={btn}
                    >
                      Sign off gate
                    </button>
                  </div>
                )}
              </div>
            )}
          </section>
        );
      })}
    </div>
  );
}
