"use client";

// The curated funder-form catalogue: what every workspace drafts against.
//
// Forms are transcribed inside a workspace and published from here. That
// asymmetry is the point — a workspace's own copy carries "we have not
// checked this" onto every draft, and publishing is what takes it off, so
// publishing has to be a deliberate act with the bar set higher than
// transcribing.

import { useCallback, useEffect, useState } from "react";
import { Spinner } from "@/components/activity";
import {
  PromoteCandidate,
  blockedReason,
  listCatalogue,
  listPromoteCandidates,
  promoteQuestionSet,
  withdrawQuestionSet,
} from "@/lib/admin";
import { fmtDate } from "@/lib/groundwork";
import type { QuestionSet } from "@/lib/questions";

const btn =
  "rounded-[10px] bg-accent px-3 py-1.5 text-sm font-medium text-accent-ink hover:bg-accent-deep disabled:opacity-50";
const btnGhost = "text-xs text-ink-muted underline hover:text-ink";

function Candidate({
  c,
  onPublished,
}: {
  c: PromoteCandidate;
  onPublished: () => void;
}) {
  const [confirmed, setConfirmed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const blocked = blockedReason(c);

  async function publish() {
    setBusy(true);
    setError(null);
    try {
      await promoteQuestionSet({
        tenant_id: c.tenant_id,
        key: c.key,
        confirmed_against_source: confirmed,
        replace: c.in_catalogue,
      });
      onPublished();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <li className="rounded-card border border-edge bg-surface p-3">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <div className="min-w-0">
          <p className="text-sm font-medium">
            {c.funder} — {c.name}
          </p>
          <p className="mt-0.5 flex flex-wrap items-center gap-2 text-xs text-ink-faint">
            <span>{c.tenant_name}</span>
            <span className="data">{c.key}</span>
            <span>{c.question_count} questions</span>
            {c.in_catalogue && <span className="stamp">already published</span>}
            {c.source_url && (
              <a href={c.source_url} target="_blank" rel="noopener noreferrer" className="underline">
                source
              </a>
            )}
          </p>
        </div>
      </div>

      {blocked ? (
        <p className="mt-2 rounded-[10px] bg-warn-soft px-3 py-2 text-xs text-warn">
          Not ready to publish — {blocked}.
        </p>
      ) : (
        <div className="mt-2 space-y-2">
          <label className="flex items-start gap-2 text-xs text-ink-muted">
            <input
              type="checkbox"
              checked={confirmed}
              onChange={(e) => setConfirmed(e.target.checked)}
              className="mt-0.5"
            />
            <span>
              I have opened this funder&apos;s own form and read these {c.question_count} questions
              and their limits against it. Publishing removes the &ldquo;not checked&rdquo; warning
              for every workspace.
            </span>
          </label>
          <button onClick={publish} disabled={busy || !confirmed} className={btn}>
            {busy ? (
              <>
                <Spinner className="mr-1.5" /> Publishing…
              </>
            ) : c.in_catalogue ? (
              "Republish over the catalogue copy"
            ) : (
              "Publish to the catalogue"
            )}
          </button>
        </div>
      )}
      {error && (
        <p className="mt-2 rounded-[10px] bg-danger-soft px-3 py-2 text-xs text-danger">{error}</p>
      )}
    </li>
  );
}

export function CatalogueEditor() {
  const [catalogue, setCatalogue] = useState<QuestionSet[] | null>(null);
  const [candidates, setCandidates] = useState<PromoteCandidate[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(() => {
    Promise.all([listCatalogue(), listPromoteCandidates()])
      .then(([c, p]) => {
        setCatalogue(c);
        setCandidates(p);
      })
      .catch((e) => setError(e instanceof Error ? e.message : String(e)));
  }, []);

  useEffect(refresh, [refresh]);

  async function withdraw(key: string) {
    setError(null);
    try {
      await withdrawQuestionSet(key);
      refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  return (
    <div className="space-y-4">
      {error && (
        <p className="rounded-[10px] bg-danger-soft px-3 py-2 text-sm text-danger">{error}</p>
      )}

      <section>
        <h3 className="data mb-2 text-ink-muted uppercase">
          Published — every workspace drafts against these
        </h3>
        {catalogue === null ? (
          <p className="flex items-center gap-2 text-sm text-ink-muted">
            <Spinner /> Loading…
          </p>
        ) : catalogue.length === 0 ? (
          <p className="text-sm text-ink-muted">Nothing published yet.</p>
        ) : (
          <ul className="space-y-2">
            {catalogue.map((s) => (
              <li
                key={s.key}
                className="flex flex-wrap items-baseline justify-between gap-2 rounded-card border border-edge bg-surface p-3"
              >
                <div className="min-w-0">
                  <p className="text-sm font-medium">
                    {s.funder} — {s.name}
                  </p>
                  <p className="mt-0.5 flex flex-wrap items-center gap-2 text-xs text-ink-faint">
                    <span className="data">{s.key}</span>
                    <span>{s.questions.length} questions</span>
                    <span className={s.stale ? "text-warn" : undefined}>
                      {s.stale ? "past review" : `reviewed by ${fmtDate(s.next_review)}`}
                    </span>
                  </p>
                </div>
                <button onClick={() => withdraw(s.key)} className={btnGhost}>
                  Withdraw
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section>
        <h3 className="data mb-2 text-ink-muted uppercase">
          Transcribed in workspaces — candidates to publish
        </h3>
        {candidates === null ? null : candidates.length === 0 ? (
          <p className="text-sm text-ink-muted">
            None yet. Forms are transcribed inside a workspace, on its Funder forms page.
          </p>
        ) : (
          <ul className="space-y-2">
            {candidates.map((c) => (
              <Candidate key={`${c.tenant_id}:${c.key}`} c={c} onPublished={refresh} />
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
