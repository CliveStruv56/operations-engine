"use client";

// The answer sheet: a drafted answer per question, sized against the funder's
// own field limit and ready to paste into their portal.
//
// We do not touch the portal — it is an authenticated web app whose terms
// generally forbid automated access, and auto-submit is the one absolute
// guardrail. What we can do is the half the funders themselves describe:
// draft offline, then paste. So this screen optimises for one motion —
// read the question, check the count, copy, paste — and gets out of the way.

import { useState } from "react";
import { Answer, AnswerSheet as Sheet, countLabel, countTone } from "@/lib/questions";

/** Split on [TO CONFIRM: …] so the gaps can be marked without losing them. */
const TO_CONFIRM = /(\[TO CONFIRM:[^\]]*\])/g;

function AnswerText({ text }: { text: string }) {
  return (
    <p className="whitespace-pre-wrap text-sm leading-relaxed">
      {text.split(TO_CONFIRM).map((part, i) =>
        part.startsWith("[TO CONFIRM:") ? (
          <mark key={i} className="rounded bg-warn-soft px-1 text-warn">
            {part}
          </mark>
        ) : (
          <span key={i}>{part}</span>
        )
      )}
    </p>
  );
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  const [failed, setFailed] = useState(false);

  async function copy() {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setFailed(false);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Clipboard access can be refused (insecure origin, permissions). Say so
      // rather than silently doing nothing — the whole point of the screen is
      // getting this text somewhere else.
      setFailed(true);
    }
  }

  return (
    <button
      onClick={copy}
      className="rounded-[10px] border border-line px-2 py-1 text-xs hover:border-edge-strong"
      aria-live="polite"
    >
      {copied ? "Copied" : failed ? "Select and copy" : "Copy"}
    </button>
  );
}

function Sources({ answer }: { answer: Answer }) {
  const [open, setOpen] = useState(false);
  if (!answer.citations.length) return null;
  return (
    <div className="mt-2">
      <button onClick={() => setOpen(!open)} className="text-xs text-ink-muted underline">
        {answer.citations.length} {answer.citations.length === 1 ? "source" : "sources"}
      </button>
      {open && (
        <ul className="mt-1 space-y-0.5 text-xs text-ink-muted">
          {answer.citations.map((c) => (
            <li key={c.n}>
              {c.title}
              {c.pages ? `, ${c.pages}` : ""}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

/**
 * Where the answer came from, when that is worth saying.
 *
 * `grounded` green is reserved for trust states, and an answer taken straight
 * from a confirmed, dated, sourced fact is exactly that — it is the one thing
 * on this sheet nobody needs to check. A drafted answer gets no stamp at all;
 * saying "written by a model" on nine of eleven cards would be noise.
 */
function OriginStamp({ answer }: { answer: Answer }) {
  if (answer.origin === "claim")
    return (
      <span className="rounded-[10px] bg-grounded-tint px-2 py-0.5 text-xs font-medium text-grounded">
        From your register
      </span>
    );
  if (answer.origin === "claim_assisted")
    return <span className="text-xs text-ink-faint">Written from your register</span>;
  return null;
}

function AnswerCard({ answer, index }: { answer: Answer; index: number }) {
  return (
    <li className="rounded-card border border-edge bg-surface p-4">
      <div className="mb-2 flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-sm font-medium">
            <span className="text-ink-faint">{index + 1}.</span> {answer.question}
          </p>
          {answer.guidance && <p className="mt-0.5 text-xs text-ink-faint">{answer.guidance}</p>}
        </div>
        <CopyButton text={answer.text} />
      </div>

      <AnswerText text={answer.text} />

      <div className="mt-2 flex flex-wrap items-center gap-2">
        <span className={`data text-xs ${countTone(answer)}`}>{countLabel(answer)}</span>
        {answer.over_by > 0 && (
          <span className="rounded-[10px] bg-danger-soft px-2 py-0.5 text-xs text-danger">
            {answer.over_by.toLocaleString("en-GB")} over — shorten before pasting
          </span>
        )}
        <OriginStamp answer={answer} />
      </div>

      <Sources answer={answer} />
    </li>
  );
}

export function AnswerSheetView({
  sheet,
  stale,
  setName,
}: {
  sheet: Sheet;
  /** The question set is past its review date, or is the tenant's own copy. */
  stale?: string | null;
  setName?: string;
}) {
  const problems: string[] = [];
  if (sheet.over_limit)
    problems.push(`${sheet.over_limit} over the limit`);
  if (sheet.to_confirm)
    problems.push(`${sheet.to_confirm} ${sheet.to_confirm === 1 ? "item" : "items"} to confirm`);

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <p className="text-sm">
          {setName ? <span className="font-medium">{setName}</span> : "Answer sheet"} —{" "}
          {sheet.answers.length} {sheet.answers.length === 1 ? "answer" : "answers"}
        </p>
        {/* Lead with what needs attention: nobody should have to scroll a
            twenty-question form to find the two answers that will not fit. */}
        {problems.length > 0 ? (
          <p className="text-xs text-ink-muted">{problems.join(" · ")}</p>
        ) : (
          <p className="text-xs text-ink-faint">Everything fits</p>
        )}
      </div>

      {/* Said once at the top rather than left to be counted badge by badge —
          it is the number that tells somebody the register was worth filling
          in, and it is the only good news on the sheet. */}
      {sheet.from_register > 0 && (
        <p className="text-xs text-ink-muted">
          {sheet.from_register} of {sheet.answers.length}{" "}
          {sheet.from_register === 1 ? "answer came" : "answers came"} straight from your
          register — no drafting, nothing to check.
        </p>
      )}

      {stale && (
        <p className="rounded-[10px] bg-warn-soft px-3 py-2 text-xs text-warn">
          {stale} A limit that has changed since we checked produces an answer that will not
          paste.
        </p>
      )}

      <ul className="space-y-3">
        {sheet.answers.map((a, i) => (
          <AnswerCard key={a.question_id} answer={a} index={i} />
        ))}
      </ul>

      <p className="text-xs text-ink-faint">
        Nothing here is submitted for you. Copy each answer into the funder&apos;s own form when
        you are happy with it.
      </p>
    </div>
  );
}
