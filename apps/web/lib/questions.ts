// Funder question sets and the answer sheet a draft produces from one.
//
// Shared by Groundwork and Grantwork: a funder's form is the same object
// whether a development consultancy or a charity is filling it in, so the
// types and the fetchers live here rather than in either module's lib.
import { api } from "@/lib/api";
import { tenantId } from "@/lib/groundwork";

const qs = <T,>(path: string, init: RequestInit = {}) =>
  api<T>(path, init, tenantId() ?? undefined);

export type Question = {
  id: string;
  order: number;
  text: string;
  guidance: string;
  limit_kind: "characters" | "words";
  limit: number | null;
  required: boolean;
  uses_vault: boolean;
};

export type QuestionSet = {
  key: string;
  name: string;
  funder: string;
  stage: "eoi" | "full" | "monitoring";
  source_url: string | null;
  status: string;
  questions: Question[];
  last_verified: string;
  next_review: string;
  stale: boolean;
  /** Which table it came from. A tenant's own set is not one we have checked. */
  source: "platform" | "tenant";
};

export type Citation = { n: number; title: string; pages: string | null };

export type Answer = {
  question_id: string;
  question: string;
  guidance: string;
  /** Ready to paste: no citation markers, [TO CONFIRM] deliberately left in. */
  text: string;
  limit: number | null;
  limit_kind: "characters" | "words";
  length: number;
  over_by: number;
  to_confirm: number;
  citations: Citation[];
};

export type AnswerSheet = {
  job_id: string;
  question_set_key: string | null;
  answers: Answer[];
  over_limit: number;
  to_confirm: number;
};

export const listQuestionSets = () => qs<QuestionSet[]>("/question-sets");

export const getProjectAnswers = (jobId: string) =>
  qs<AnswerSheet>(`/projects/drafts/${jobId}/answers`);

export const getGrantAnswers = (jobId: string) => qs<AnswerSheet>(`/grants/drafts/${jobId}/answers`);

/**
 * The caveat to show above a sheet, or null when there is nothing to say.
 *
 * Mirrors the worker's `warning_for`, deliberately: the sentence on screen and
 * the one on the draft's first page should not disagree about how much this
 * form can be trusted.
 */
export function staleNote(set: QuestionSet | null | undefined): string | null {
  if (!set) return null;
  if (set.source === "tenant")
    return `These questions and limits are your workspace's own copy of “${set.name}”, not one we have checked against the funder's current form.`;
  // Two different problems, and saying the wrong one is worse than saying
  // nothing: a set can be unverified but in date, or verified but overdue.
  if (set.status !== "open" && set.stale)
    return `The questions and limits for “${set.name}” have never been verified against the funder's own form, and are past review.`;
  if (set.status !== "open")
    return `The questions and limits for “${set.name}” have not been verified against the funder's own form.`;
  if (set.stale)
    return `The questions and limits for “${set.name}” were last verified ${set.last_verified} and are past review.`;
  return null;
}

/** "1,240 / 2,000 characters" — the funder counts every space, so we do too. */
export function countLabel(answer: Answer): string {
  const unit = answer.limit_kind === "words" ? "words" : "characters";
  const length = answer.length.toLocaleString("en-GB");
  if (answer.limit === null) return `${length} ${unit}`;
  return `${length} / ${answer.limit.toLocaleString("en-GB")} ${unit}`;
}

/**
 * Tone for the counter.
 *
 * `grounded` green is reserved for trust states, so a comfortable answer gets
 * no colour at all rather than a reassuring tick — the counter should only
 * speak up when it has something to say.
 */
export function countTone(answer: Answer): string {
  if (answer.over_by > 0) return "text-danger font-medium";
  if (answer.limit !== null && answer.length >= answer.limit * 0.9) return "text-warn";
  return "text-ink-faint";
}
