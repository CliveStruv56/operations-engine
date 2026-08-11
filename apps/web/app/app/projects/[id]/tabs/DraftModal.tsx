"use client";

// "Draft with AI" (PRD §5): kind-specific inputs, submit, 3s job polling,
// then a success panel with the download link and the "N items to confirm"
// count. Drafts always land at status "drafting" — review is the human's job.

import { useEffect, useState } from "react";
import {
  DraftJob,
  DraftKind,
  Funding,
  getDraftJob,
  gw,
  listActiveDraftJobs,
  openPresigned,
  submitDraft,
} from "@/lib/groundwork";
import { Spinner } from "@/components/activity";
import { AnswerSheetView } from "@/components/answer-sheet";
import {
  AnswerSheet,
  QuestionSet,
  getProjectAnswers,
  listQuestionSets,
  staleNote,
} from "@/lib/questions";
import { btn, btnGhost, input } from "./ui";

const KIND_LABEL: Record<DraftKind, string> = {
  monthly_report: "Monthly client report",
  feasibility_study: "Feasibility study",
  funding_bid: "Funding application",
  application_form: "Funder's application form",
};

const POLL_MS = 3000;

export function DraftModal({
  projectId,
  kind,
  onClose,
  onRegistered,
}: {
  projectId: string;
  kind: DraftKind;
  onClose: () => void;
  onRegistered: () => void;
}) {
  const [month, setMonth] = useState(() => new Date().toISOString().slice(0, 7));
  const [instructions, setInstructions] = useState("");
  const [sources, setSources] = useState<Funding[]>([]);
  const [sourceId, setSourceId] = useState("");
  const [sets, setSets] = useState<QuestionSet[]>([]);
  const [setKey, setSetKey] = useState("");
  const [sheet, setSheet] = useState<AnswerSheet | null>(null);
  const [job, setJob] = useState<DraftJob | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const chosenSet = sets.find((s) => s.key === setKey) ?? null;

  // A draft may already be running (the modal invites closing mid-draft) —
  // resume polling it instead of offering a duplicate submit; the API also
  // 409s duplicates as the authoritative guard.
  useEffect(() => {
    listActiveDraftJobs(projectId)
      .then((jobs) => {
        const active = jobs.find((j) => j.kind === kind);
        if (active) setJob((current) => current ?? active);
      })
      .catch(() => {});
  }, [projectId, kind]);

  useEffect(() => {
    if (kind !== "funding_bid") return;
    gw<Funding[]>(`/projects/${projectId}/funding`)
      .then((rows) => {
        setSources(rows);
        if (rows.length) setSourceId(rows[0].id);
      })
      .catch((e) => setError(e instanceof Error ? e.message : String(e)));
  }, [kind, projectId]);

  useEffect(() => {
    if (kind !== "application_form") return;
    listQuestionSets()
      .then((rows) => {
        setSets(rows);
        if (rows.length) setSetKey(rows[0].key);
      })
      .catch((e) => setError(e instanceof Error ? e.message : String(e)));
  }, [kind]);

  const running = job !== null && (job.status === "queued" || job.status === "running");
  useEffect(() => {
    if (!running || !job) return;
    const timer = setInterval(() => {
      getDraftJob(job.id)
        .then((next) => {
          setJob(next);
          if (next.status === "succeeded") onRegistered();
        })
        .catch(() => {});
    }, POLL_MS);
    return () => clearInterval(timer);
  }, [running, job, onRegistered]);

  // The sheet is the point of an application-form draft, so fetch it as soon
  // as the job lands rather than making someone click through to it.
  useEffect(() => {
    if (job?.status !== "succeeded" || job.kind !== "application_form" || sheet) return;
    getProjectAnswers(job.id)
      .then(setSheet)
      .catch((e) => setError(e instanceof Error ? e.message : String(e)));
  }, [job, sheet]);

  async function submit() {
    setError(null);
    setSubmitting(true);
    try {
      const body: Parameters<typeof submitDraft>[1] = { kind };
      if (kind === "monthly_report") body.month = month;
      if (kind === "funding_bid") body.funding_source_id = sourceId;
      if (kind === "application_form") body.question_set_key = setKey;
      if (kind === "feasibility_study" && instructions.trim())
        body.instructions = instructions.trim();
      setJob(await submitDraft(projectId, body));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/40 p-4">
      {/* The sheet is a working surface, not a confirmation — twenty answers
          at a readable measure need the room, and the body scrolls so the
          header and its counts stay put. */}
      <div
        className={`flex max-h-[90vh] w-full flex-col overflow-hidden rounded-card border border-edge bg-surface p-5 shadow-lg ${
          sheet ? "max-w-3xl" : "max-w-md"
        }`}
      >
        <div className="mb-3 flex items-center justify-between">
          <h2 className="font-medium">Draft with AI — {KIND_LABEL[kind]}</h2>
          <button onClick={onClose} className={btnGhost}>
            Close
          </button>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto">
        {job === null && (
          <div className="space-y-3">
            {kind === "monthly_report" && (
              <label className="block text-sm">
                Reporting month
                <input
                  type="month"
                  value={month}
                  onChange={(e) => setMonth(e.target.value)}
                  className={`${input} mt-1 block w-full`}
                />
              </label>
            )}
            {kind === "funding_bid" &&
              (sources.length ? (
                <label className="block text-sm">
                  Funding source to bid for
                  <select
                    value={sourceId}
                    onChange={(e) => setSourceId(e.target.value)}
                    className={`${input} mt-1 block w-full`}
                  >
                    {sources.map((s) => (
                      <option key={s.id} value={s.id}>
                        {s.name} ({s.status})
                      </option>
                    ))}
                  </select>
                </label>
              ) : (
                <p className="text-sm text-ink-muted">
                  Add a funding source on the Funding tab first — the bid is written against it.
                </p>
              ))}
            {kind === "application_form" &&
              (sets.length ? (
                <label className="block text-sm">
                  Which funder&apos;s form?
                  <select
                    value={setKey}
                    onChange={(e) => setSetKey(e.target.value)}
                    className={`${input} mt-1 block w-full`}
                  >
                    {sets.map((s) => (
                      <option key={s.key} value={s.key}>
                        {s.funder} — {s.name} ({s.questions.length} questions)
                      </option>
                    ))}
                  </select>
                </label>
              ) : (
                <p className="text-sm text-ink-muted">
                  No funder forms are set up yet. Each one holds a funder&apos;s own questions and
                  their character limits, so answers come out the right length to paste.
                </p>
              ))}
            {kind === "application_form" && staleNote(chosenSet) && (
              <p className="rounded-[10px] bg-warn-soft px-3 py-2 text-xs text-warn">
                {staleNote(chosenSet)}
              </p>
            )}
            {kind === "feasibility_study" && (
              <label className="block text-sm">
                Instructions (optional)
                <textarea
                  value={instructions}
                  onChange={(e) => setInstructions(e.target.value)}
                  rows={3}
                  maxLength={2000}
                  placeholder="Anything the study should focus on"
                  className={`${input} mt-1 block w-full`}
                />
              </label>
            )}
            <p className="text-xs text-ink-faint">
              The draft is assembled from this project&apos;s records
              {kind !== "monthly_report" && " and cited vault documents"}. Anything the data
              doesn&apos;t cover is marked [TO CONFIRM] — nothing is sent anywhere without you.
            </p>
            {error && (
              <p className="rounded-[10px] bg-danger-soft px-3 py-2 text-sm text-danger">{error}</p>
            )}
            <button
              onClick={submit}
              disabled={
                submitting ||
                (kind === "funding_bid" && !sourceId) ||
                (kind === "application_form" && !setKey)
              }
              className={btn}
            >
              {submitting ? (
                <>
                  <Spinner className="mr-1.5" /> Submitting…
                </>
              ) : (
                "Generate draft"
              )}
            </button>
          </div>
        )}

        {running && (
          <div className="space-y-2 text-sm">
            <p className="flex items-center gap-2">
              <Spinner className="text-accent" />
              <span>
                Drafting — this usually takes a minute or two.{" "}
                <span className="data text-ink-muted uppercase">{job.status}</span>
              </span>
            </p>
            <p className="text-xs text-ink-faint">
              You can close this window; the draft lands in the document registry when done.
            </p>
          </div>
        )}

        {job?.status === "succeeded" && (
          <div className="space-y-3 text-sm">
            {sheet ? (
              <AnswerSheetView
                sheet={sheet}
                setName={chosenSet?.name}
                stale={staleNote(chosenSet)}
              />
            ) : (
              <p className="rounded-[10px] bg-accent-soft px-3 py-2">
                Draft ready — {job.to_confirm_count}{" "}
                {job.to_confirm_count === 1 ? "item" : "items"} to confirm before it leaves the
                building.
              </p>
            )}
            {job.download_url && (
              <button onClick={() => openPresigned(job.download_url!)} className={btn}>
                Download DOCX
              </button>
            )}
          </div>
        )}

        {job?.status === "failed" && (
          <div className="space-y-3 text-sm">
            <p className="rounded-[10px] bg-danger-soft px-3 py-2 text-danger">
              {job.error ?? "Draft generation failed."}
            </p>
            <button onClick={() => setJob(null)} className={btn}>
              Try again
            </button>
          </div>
        )}
        </div>
      </div>
    </div>
  );
}
