"use client";

// Transcribing a funder's form: paste their published questions, correct what
// came back, save.
//
// The discipline the whole screen enforces is about limits. The model is told
// never to invent one, so every limit it could not find in the text comes back
// blank — and a blank limit is the only thing here that cannot be fixed later
// by reading the answer, because it is discovered at the portal after the
// writing is done. So blanks are counted, coloured, and in the way.

import { useState } from "react";
import { Spinner } from "@/components/activity";
import {
  Question,
  QuestionSet,
  createQuestionSet,
  suggestKey,
  transcribeQuestions,
} from "@/lib/questions";

const input = "w-full rounded-[10px] border border-line bg-surface px-3 py-2 text-sm";
const btn =
  "rounded-[10px] bg-accent px-4 py-2 text-sm font-medium text-accent-ink hover:bg-accent-deep disabled:opacity-50";
const btnGhost = "text-xs text-ink-muted underline hover:text-ink";

function QuestionRow({
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
              <span className="text-warn">
                no limit found — check the funder&apos;s form
              </span>
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

export function TranscribePanel({
  onSaved,
  onCancel,
}: {
  onSaved: (set: QuestionSet) => void;
  onCancel: () => void;
}) {
  const [source, setSource] = useState("");
  const [questions, setQuestions] = useState<Question[] | null>(null);
  const [hint, setHint] = useState<{ missing: number; inSource: number } | null>(null);
  const [funder, setFunder] = useState("");
  const [name, setName] = useState("");
  const [stage, setStage] = useState<QuestionSet["stage"]>("full");
  const [sourceUrl, setSourceUrl] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function read() {
    setBusy(true);
    setError(null);
    try {
      const proposal = await transcribeQuestions(source);
      setQuestions(proposal.questions);
      setHint({ missing: proposal.limits_missing, inSource: proposal.limits_in_source });
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  async function save() {
    if (!questions) return;
    setBusy(true);
    setError(null);
    try {
      onSaved(
        await createQuestionSet({
          key: suggestKey(funder, name),
          name,
          funder,
          stage,
          source_url: sourceUrl,
          questions: questions.map((q, i) => ({ ...q, order: i + 1 })),
        })
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  const missing = questions?.filter((q) => q.limit === null).length ?? 0;
  const ready = Boolean(questions?.length && funder.trim() && name.trim() && sourceUrl.trim());

  return (
    <div className="space-y-4">
      {questions === null ? (
        <>
          <div>
            <label className="text-sm font-medium" htmlFor="source">
              Paste the funder&apos;s questions
            </label>
            <p className="mt-0.5 mb-2 text-xs text-ink-faint">
              From their published guidance — the &ldquo;how to apply&rdquo; page, a questions
              and word-counts sheet, or the form itself. Include the character limits if they
              are stated; nothing here is invented for you.
            </p>
            <textarea
              id="source"
              value={source}
              onChange={(e) => setSource(e.target.value)}
              rows={14}
              maxLength={24000}
              className={`${input} font-mono text-xs`}
            />
            <p className="mt-1 text-xs text-ink-faint">
              {source.length.toLocaleString("en-GB")} / 24,000 characters
            </p>
          </div>
          {error && (
            <p className="rounded-[10px] bg-danger-soft px-3 py-2 text-sm text-danger">{error}</p>
          )}
          <div className="flex items-center gap-3">
            <button onClick={read} disabled={busy || source.trim().length < 20} className={btn}>
              {busy ? (
                <>
                  <Spinner className="mr-1.5" /> Reading…
                </>
              ) : (
                "Read the questions"
              )}
            </button>
            <button onClick={onCancel} className={btnGhost}>
              Cancel
            </button>
          </div>
        </>
      ) : (
        <>
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="text-sm">
              Funder
              <input
                value={funder}
                onChange={(e) => setFunder(e.target.value)}
                placeholder="Architectural Heritage Fund"
                className={`${input} mt-1`}
              />
            </label>
            <label className="text-sm">
              Form
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Expression of interest"
                className={`${input} mt-1`}
              />
            </label>
            <label className="text-sm">
              Stage
              <select
                value={stage}
                onChange={(e) => setStage(e.target.value as QuestionSet["stage"])}
                className={`${input} mt-1`}
              >
                <option value="eoi">Expression of interest</option>
                <option value="full">Full application</option>
                <option value="monitoring">Monitoring return</option>
              </select>
            </label>
            <label className="text-sm">
              Where these came from
              <input
                value={sourceUrl}
                onChange={(e) => setSourceUrl(e.target.value)}
                placeholder="https://…"
                className={`${input} mt-1`}
              />
              <span className="mt-0.5 block text-xs text-ink-faint">
                Required — a form nobody can re-check is one that quietly goes out of date.
              </span>
            </label>
          </div>

          {missing > 0 && (
            <p className="rounded-[10px] bg-warn-soft px-3 py-2 text-sm text-warn">
              {missing} of {questions.length} questions have no limit.
              {hint && hint.inSource > 0 && ` The text you pasted mentions ${hint.inSource}.`} A
              limit that is wrong is only discovered when an answer will not paste, so it is
              worth opening the funder&apos;s form and checking.
            </p>
          )}

          <ul className="space-y-2">
            {questions.map((q, i) => (
              <QuestionRow
                key={q.id}
                q={{ ...q, order: i + 1 }}
                onChange={(next) =>
                  setQuestions(questions.map((old, j) => (j === i ? next : old)))
                }
                onRemove={() => setQuestions(questions.filter((_, j) => j !== i))}
              />
            ))}
          </ul>

          {error && (
            <p className="rounded-[10px] bg-danger-soft px-3 py-2 text-sm text-danger">{error}</p>
          )}
          <div className="flex items-center gap-3">
            <button onClick={save} disabled={busy || !ready} className={btn}>
              {busy ? (
                <>
                  <Spinner className="mr-1.5" /> Saving…
                </>
              ) : (
                "Save this form"
              )}
            </button>
            <button onClick={() => setQuestions(null)} className={btnGhost}>
              Back to the text
            </button>
            <button onClick={onCancel} className={btnGhost}>
              Cancel
            </button>
          </div>
          <p className="text-xs text-ink-faint">
            Saved forms start unverified and say so on every draft written against them, until
            somebody checks them against the funder&apos;s live form.
          </p>
        </>
      )}
    </div>
  );
}
