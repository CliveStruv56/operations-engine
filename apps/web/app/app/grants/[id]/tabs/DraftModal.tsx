"use client";

// "Draft with AI": kind-specific inputs, submit, job polling, then a success
// panel with the download link and the "N items to confirm" count. Drafts
// always land at status "drafting" — review is the human's job, and nothing
// is ever sent to a funder automatically.

import { useEffect, useState } from "react";
import { Spinner } from "@/components/activity";
import {
  DRAFT_LABEL,
  DraftJob,
  DraftKind,
  ReportingPeriod,
  getDraftJob,
  gr,
  listActiveDraftJobs,
  submitDraft,
} from "@/lib/grants";
import { openPresigned } from "@/lib/groundwork";
import { btn, btnGhost, input } from "../../ui";

const POLL_MS = 3000;

export function DraftModal({
  applicationId,
  kind,
  onClose,
  onRegistered,
}: {
  applicationId: string;
  kind: DraftKind;
  onClose: () => void;
  onRegistered: () => void;
}) {
  const [periods, setPeriods] = useState<ReportingPeriod[]>([]);
  const [periodId, setPeriodId] = useState("");
  const [instructions, setInstructions] = useState("");
  const [job, setJob] = useState<DraftJob | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  // A draft may already be running (this modal invites closing mid-draft) —
  // resume polling it rather than offering a duplicate submit. The API's 409
  // is the authoritative guard.
  useEffect(() => {
    listActiveDraftJobs(applicationId)
      .then((jobs) => {
        const active = jobs.find((j) => j.kind === kind);
        if (active) setJob((current) => current ?? active);
      })
      .catch(() => {});
  }, [applicationId, kind]);

  useEffect(() => {
    if (kind !== "monitoring_report") return;
    gr<ReportingPeriod[]>(`/grants/applications/${applicationId}/reporting-periods`)
      .then((rows) => {
        setPeriods(rows);
        const next = rows.find((r) => r.status !== "accepted") ?? rows[0];
        if (next) setPeriodId(next.id);
      })
      .catch((e) => setError(e instanceof Error ? e.message : String(e)));
  }, [kind, applicationId]);

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

  async function submit() {
    setError(null);
    setSubmitting(true);
    try {
      const body: Parameters<typeof submitDraft>[1] = { kind };
      if (kind === "monitoring_report") body.reporting_period_id = periodId;
      if (instructions.trim()) body.instructions = instructions.trim();
      setJob(await submitDraft(applicationId, body));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/40 p-4">
      <div className="w-full max-w-md rounded-card border border-edge bg-surface p-5 shadow-lg">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="font-medium">Draft with AI — {DRAFT_LABEL[kind]}</h2>
          <button onClick={onClose} className={btnGhost}>
            Close
          </button>
        </div>

        {job === null && (
          <div className="space-y-3">
            {kind === "monitoring_report" &&
              (periods.length ? (
                <label className="block text-sm">
                  Reporting period this return covers
                  <select
                    value={periodId}
                    onChange={(e) => setPeriodId(e.target.value)}
                    className={`${input} mt-1 block w-full`}
                  >
                    {periods.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.label} ({p.status})
                      </option>
                    ))}
                  </select>
                </label>
              ) : (
                <p className="text-sm text-ink-muted">
                  Add a reporting period on the Reporting tab first — the return is written against
                  one, and its figures come from the outcomes recorded there.
                </p>
              ))}

            <label className="block text-sm">
              Instructions (optional)
              <textarea
                value={instructions}
                onChange={(e) => setInstructions(e.target.value)}
                rows={3}
                maxLength={2000}
                placeholder="Anything this document should emphasise"
                className={`${input} mt-1 block w-full`}
              />
            </label>

            <p className="text-xs text-ink-faint">
              {kind === "monitoring_report"
                ? "Assembled from this application's records. Outcome figures come from the values you recorded — never from the model."
                : "Assembled from this application's records and cited vault documents."}{" "}
              Anything the data doesn&apos;t cover is marked [TO CONFIRM]. Nothing is sent to a
              funder without you.
            </p>

            {error && (
              <p className="rounded-[10px] bg-danger-soft px-3 py-2 text-sm text-danger">{error}</p>
            )}
            <button
              onClick={submit}
              disabled={submitting || (kind === "monitoring_report" && !periodId)}
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
              You can close this window; the draft lands in the bid pack when done.
            </p>
          </div>
        )}

        {job?.status === "succeeded" && (
          <div className="space-y-3 text-sm">
            <p className="rounded-[10px] bg-accent-soft px-3 py-2">
              Draft ready — {job.to_confirm_count}{" "}
              {job.to_confirm_count === 1 ? "item" : "items"} marked [TO CONFIRM]. It is filed as a
              draft; read it before anything goes to the funder.
            </p>
            {job.download_url && (
              <button onClick={() => openPresigned(job.download_url!)} className={btn}>
                Download the draft
              </button>
            )}
          </div>
        )}

        {job?.status === "failed" && (
          <p className="rounded-[10px] bg-danger-soft px-3 py-2 text-sm text-danger">
            {job.error ?? "The draft failed."}
          </p>
        )}
      </div>
    </div>
  );
}
