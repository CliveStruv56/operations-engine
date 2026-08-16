"use client";

// Correct a saved transcription without deleting it. Limits are the point:
// a wrong character count is only discovered when an answer will not paste.

import { useState } from "react";
import { Spinner } from "@/components/activity";
import { Question, QuestionSet, updateQuestionSet } from "@/lib/questions";
import { QuestionRow } from "./question-row";

import { btnPrimary as btn, btnQuiet as btnGhost, input } from "@/components/ui/styles";

export function EditFormPanel({
  set,
  onSaved,
  onCancel,
}: {
  set: QuestionSet;
  onSaved: () => void;
  onCancel: () => void;
}) {
  const [funder, setFunder] = useState(set.funder);
  const [name, setName] = useState(set.name);
  const [stage, setStage] = useState(set.stage);
  const [sourceUrl, setSourceUrl] = useState(set.source_url ?? "");
  const [questions, setQuestions] = useState<Question[]>(set.questions);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const missing = questions.filter((q) => q.limit === null).length;
  const ready = Boolean(questions.length && funder.trim() && name.trim() && sourceUrl.trim());

  async function save() {
    setBusy(true);
    setError(null);
    try {
      await updateQuestionSet(set.key, {
        name: name.trim(),
        funder: funder.trim(),
        stage,
        source_url: sourceUrl.trim(),
        questions: questions.map((q, i) => ({ ...q, order: i + 1 })),
      });
      onSaved();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mt-4 space-y-3">
      <div className="grid gap-3 sm:grid-cols-2">
        <label className="text-sm">
          Funder
          <input
            value={funder}
            onChange={(e) => setFunder(e.target.value)}
            className={`${input} mt-1`}
          />
        </label>
        <label className="text-sm">
          Form
          <input value={name} onChange={(e) => setName(e.target.value)} className={`${input} mt-1`} />
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
            className={`${input} mt-1`}
          />
        </label>
      </div>

      {missing > 0 && (
        <p className="rounded-card bg-warn-soft px-3 py-2 text-sm text-warn">
          {missing} of {questions.length} questions have no limit. A limit that is wrong is only
          discovered when an answer will not paste.
        </p>
      )}

      <ul className="space-y-2">
        {questions.map((q, i) => (
          <QuestionRow
            key={q.id}
            q={{ ...q, order: i + 1 }}
            onChange={(next) => setQuestions(questions.map((old, j) => (j === i ? next : old)))}
            onRemove={() => setQuestions(questions.filter((_, j) => j !== i))}
          />
        ))}
      </ul>

      {error && (
        <p className="rounded-card bg-danger-soft px-3 py-2 text-sm text-danger">{error}</p>
      )}
      <div className="flex items-center gap-3">
        <button onClick={save} disabled={busy || !ready} className={btn}>
          {busy ? (
            <>
              <Spinner className="mr-1.5" /> Saving…
            </>
          ) : (
            "Save changes"
          )}
        </button>
        <button onClick={onCancel} className={btnGhost}>
          Cancel
        </button>
      </div>
      <p className="text-xs text-ink-faint">
        Changing the questions marks this copy unverified again, until somebody checks it against
        the funder&apos;s live form.
      </p>
    </div>
  );
}
