"use client";

// Funder forms: what each funder actually asks, and the limits on their
// fields. Drafting reads from here, so this page is where a form's questions
// get transcribed, corrected and confirmed.
//
// Two kinds of row, and the difference is on the face of it: forms we curate
// centrally, and forms this workspace transcribed itself. Only the second can
// be edited here, and only the second carries "not one we have checked" into
// every draft until somebody confirms it.

import { useCallback, useEffect, useState } from "react";
import { Spinner } from "@/components/activity";
import {
  QuestionSet,
  deleteQuestionSet,
  listQuestionSets,
  staleNote,
  updateQuestionSet,
} from "@/lib/questions";
import { TranscribePanel } from "./transcribe-panel";
import { EditFormPanel } from "./edit-panel";
import { QuestionDisplay } from "./question-row";

import {
  btnPrimary as btn,
  btnQuiet as btnGhost,
  cardPadded as card,
} from "@/components/ui/styles";

function StageLabel({ stage }: { stage: QuestionSet["stage"] }) {
  const label =
    stage === "eoi" ? "Expression of interest" : stage === "monitoring" ? "Monitoring" : "Full";
  return <span className="stamp text-ink-faint">{label}</span>;
}

function FormRow({ set, onChanged }: { set: QuestionSet; onChanged: () => void }) {
  const [busy, setBusy] = useState(false);
  const [editing, setEditing] = useState(false);
  // Catalogue sets are non-editable but never non-inspectable: every card
  // opens read-only so the questions and limits can be seen before drafting.
  const [open, setOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const note = staleNote(set);
  const missing = set.questions.filter((q) => q.limit === null).length;

  async function act(fn: () => Promise<unknown>) {
    setBusy(true);
    setError(null);
    try {
      await fn();
      onChanged();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <li className={card}>
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <div className="min-w-0">
          <button
            onClick={() => setOpen((o) => !o)}
            aria-expanded={open}
            className="flex items-center gap-1.5 text-left font-medium hover:text-electric-blue"
          >
            <span aria-hidden="true" className="text-xs text-ink-faint">
              {open ? "▾" : "▸"}
            </span>
            {set.funder} — {set.name}
          </button>
          <p className="mt-0.5 flex flex-wrap items-center gap-2 text-xs text-ink-faint">
            <StageLabel stage={set.stage} />
            <span>{set.questions.length} questions</span>
            {missing > 0 && <span className="text-warn">{missing} with no limit</span>}
            <span>
              {set.source === "platform" ? "from the catalogue" : "transcribed here"}
            </span>
            {set.source_url && (
              <a
                href={set.source_url}
                target="_blank"
                rel="noopener noreferrer"
                className="underline"
              >
                source
              </a>
            )}
          </p>
        </div>
        {set.source === "tenant" && (
          <div className="flex items-center gap-3">
            {(set.stale || set.status !== "open") && (
              <button
                onClick={() =>
                  act(() => updateQuestionSet(set.key, { verified: true }))
                }
                disabled={busy}
                className={btnGhost}
              >
                I have checked this against the funder&apos;s form
              </button>
            )}
            <button
              onClick={() => setEditing((open) => !open)}
              disabled={busy}
              className={btnGhost}
            >
              {editing ? "Close" : "Edit"}
            </button>
            <button
              onClick={() => act(() => deleteQuestionSet(set.key))}
              disabled={busy}
              className={btnGhost}
            >
              Delete
            </button>
          </div>
        )}
      </div>

      {note && (
        <p className="mt-2 rounded-[10px] bg-warn-soft px-3 py-2 text-xs text-warn">{note}</p>
      )}
      {error && (
        <p className="mt-2 rounded-[10px] bg-danger-soft px-3 py-2 text-xs text-danger">{error}</p>
      )}
      {editing && (
        <EditFormPanel
          set={set}
          onCancel={() => setEditing(false)}
          onSaved={() => {
            setEditing(false);
            onChanged();
          }}
        />
      )}
      {open && !editing && (
        <ul className="mt-3 space-y-2">
          {set.questions.map((q) => (
            <QuestionDisplay key={q.order} q={q} />
          ))}
        </ul>
      )}
    </li>
  );
}

export default function FormsPage() {
  const [sets, setSets] = useState<QuestionSet[] | null>(null);
  const [adding, setAdding] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(() => {
    listQuestionSets()
      .then(setSets)
      .catch((e) => setError(e instanceof Error ? e.message : String(e)));
  }, []);

  useEffect(refresh, [refresh]);

  return (
    <main className="min-h-0 flex-1 overflow-y-auto">
      <div className="mx-auto max-w-4xl space-y-4 p-6">
      <header className="flex flex-wrap items-baseline justify-between gap-2">
        <div>
          <h1 className="text-xl font-medium">Funder forms</h1>
          <p className="mt-1 text-sm text-ink-muted">
            The questions a funder asks and the limits on their fields. Drafting writes answers
            sized to fit them — nothing is ever submitted for you.
          </p>
        </div>
        {!adding && (
          <button onClick={() => setAdding(true)} className={btn}>
            Add a form
          </button>
        )}
      </header>

      {adding && (
        <section className={card}>
          <h2 className="mb-3 font-medium">Transcribe a funder&apos;s form</h2>
          <TranscribePanel
            onCancel={() => setAdding(false)}
            onSaved={() => {
              setAdding(false);
              refresh();
            }}
          />
        </section>
      )}

      {error && (
        <p className="rounded-[10px] bg-danger-soft px-3 py-2 text-sm text-danger">{error}</p>
      )}

      {sets === null ? (
        <p className="flex items-center gap-2 text-sm text-ink-muted">
          <Spinner /> Loading…
        </p>
      ) : sets.length === 0 ? (
        <p className="text-sm text-ink-muted">
          No forms yet. Add one by pasting a funder&apos;s published questions.
        </p>
      ) : (
        <ul className="space-y-3">
          {sets.map((s) => (
            <FormRow key={s.key} set={s} onChanged={refresh} />
          ))}
        </ul>
      )}
      </div>
    </main>
  );
}
