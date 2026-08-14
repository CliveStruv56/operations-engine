"use client";

import { Question } from "@/lib/questions";

const input = "w-full rounded-[10px] border border-line bg-surface px-3 py-2 text-sm";
const btnGhost = "text-xs text-ink-muted underline hover:text-ink";

export function QuestionRow({
  q,
  onChange,
  onRemove,
}: {
  q: Question;
  onChange: (next: Question) => void;
  onRemove: () => void;
}) {
  const missing = q.limit === null;
  return (
    <li className="rounded-card border border-edge bg-surface p-3">
      <div className="flex items-start gap-2">
        <span className="data mt-2 text-xs text-ink-faint">{q.order}</span>
        <div className="min-w-0 flex-1 space-y-2">
          <textarea
            value={q.text}
            onChange={(e) => onChange({ ...q, text: e.target.value })}
            rows={2}
            className={input}
            aria-label={`Question ${q.order}`}
          />
          <input
            value={q.guidance}
            onChange={(e) => onChange({ ...q, guidance: e.target.value })}
            placeholder="The funder's own note under this question, if any"
            className={`${input} text-xs`}
            aria-label={`Guidance for question ${q.order}`}
          />
          <div className="flex flex-wrap items-center gap-2 text-xs">
            <input
              type="number"
              min={1}
              value={q.limit ?? ""}
              onChange={(e) =>
                onChange({ ...q, limit: e.target.value ? Number(e.target.value) : null })
              }
              placeholder="limit"
              aria-label={`Limit for question ${q.order}`}
              className={`w-24 rounded-[10px] border px-2 py-1 ${
                missing ? "border-warn bg-warn-soft" : "border-line bg-surface"
              }`}
            />
            <select
              value={q.limit_kind}
              onChange={(e) =>
                onChange({ ...q, limit_kind: e.target.value as Question["limit_kind"] })
              }
              aria-label={`Units for question ${q.order}`}
              className="rounded-[10px] border border-line bg-surface px-2 py-1"
            >
              <option value="characters">characters</option>
              <option value="words">words</option>
            </select>
            <label className="flex items-center gap-1 text-ink-muted">
              <input
                type="checkbox"
                checked={q.uses_vault}
                onChange={(e) => onChange({ ...q, uses_vault: e.target.checked })}
              />
              cite the vault
            </label>
            {missing && (
              <span className="text-warn">no limit found — check the funder&apos;s form</span>
            )}
            <button onClick={onRemove} className={`${btnGhost} ml-auto`}>
              Remove
            </button>
          </div>
        </div>
      </div>
    </li>
  );
}
