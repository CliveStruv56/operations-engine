"use client";

import { useState } from "react";
import { Stage, fmtDate, gr } from "@/lib/grants";
import { useAsk } from "@/components/ui";
import { btn, btnGhost, card } from "../../ui";
import { LoadError, useGrantLoad } from "./load";

export function StagesTab({ id, onAdvanced }: { id: string; onAdvanced: () => void }) {
  const ask = useAsk();
  const [stages, setStages] = useState<Stage[]>([]);
  const [error, setError] = useState<string | null>(null);
  const { failed, refresh } = useGrantLoad<Stage[]>(
    `/grants/applications/${id}/stages`,
    setStages
  );

  async function toggle(stage: Stage, itemId: string) {
    setError(null);
    try {
      await gr(`/grants/applications/${id}/stages/${stage.id}/gate/${itemId}/toggle`, {
        method: "POST",
      });
      refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  async function signoff(stage: Stage) {
    const outstanding = stage.gate.filter((g) => !g.done);
    let exceptions: string | null = null;
    if (outstanding.length) {
      exceptions = await ask.text({
        title: `Sign off with ${outstanding.length} item${outstanding.length === 1 ? "" : "s"} outstanding`,
        body: (
          <>
            The gate is not clear. Whatever you write here is kept with the sign-off as the
            record of why the stage advanced anyway.
            <ul className="mt-2 list-disc pl-5">
              {outstanding.map((g) => (
                <li key={g.id}>{g.criterion}</li>
              ))}
            </ul>
          </>
        ),
        label: "Why are you signing off anyway?",
        confirmLabel: "Sign off stage",
        multiline: true,
      });
      if (!exceptions) return;
    }
    setError(null);
    try {
      await gr(`/grants/applications/${id}/stages/${stage.id}/signoff`, {
        method: "POST",
        body: JSON.stringify({ exceptions }),
      });
      refresh();
      onAdvanced();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  return (
    <div className="space-y-3">
      <LoadError failed={failed} onRetry={refresh} />
      {error && (
        <p className="rounded-card bg-danger-soft px-3 py-2 text-sm text-danger">{error}</p>
      )}
      {stages.map((stage) => (
        <div key={stage.id} className={`${card} p-4`}>
          <div className="mb-2 flex flex-wrap items-baseline justify-between gap-2">
            <h3 className="font-medium">
              {stage.position}. {stage.label}
              <span className="stamp ml-2">{stage.status}</span>
            </h3>
            {stage.gate_signed_off_at ? (
              <span className="data text-ink-faint uppercase">
                signed off {fmtDate(stage.gate_signed_off_at)}
              </span>
            ) : (
              <button onClick={() => signoff(stage)} className={btn}>
                Sign off this gate
              </button>
            )}
          </div>
          <ul className="space-y-1.5 text-sm">
            {stage.gate.map((item) => (
              <li key={item.id} className="flex items-start gap-2">
                <input
                  type="checkbox"
                  checked={item.done}
                  disabled={item.kind !== "manual" || stage.gate_signed_off_at !== null}
                  onChange={() => toggle(stage, item.id)}
                  className="mt-0.5"
                  title={
                    item.kind === "doc"
                      ? "Follows the bid pack — mark the document final to tick this"
                      : undefined
                  }
                />
                <span className={item.done ? "text-ink-muted line-through" : ""}>
                  {item.criterion}
                  {item.kind === "doc" && (
                    <span className="stamp ml-2 text-ink-faint">from the bid pack</span>
                  )}
                </span>
              </li>
            ))}
          </ul>
          {stage.gate_exceptions && (
            <p className="mt-2 whitespace-pre-line rounded-card bg-warn-soft px-3 py-2 text-sm text-warn">
              {stage.gate_exceptions}
            </p>
          )}
          {(stage.planned_start || stage.planned_end) && (
            <p className={`mt-2 ${btnGhost} no-underline`}>
              Planned {fmtDate(stage.planned_start)} → {fmtDate(stage.planned_end)}
            </p>
          )}
        </div>
      ))}
    </div>
  );
}
