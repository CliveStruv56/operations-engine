// Shared types + helpers for the Grant funding (Grantwork) module.
import { api } from "@/lib/api";
import { tenantId } from "@/lib/groundwork";

export const gr = <T,>(path: string, init: RequestInit = {}) =>
  api<T>(path, init, tenantId() ?? undefined);

export type ApplicationStatus =
  | "pipeline"
  | "drafting"
  | "submitted"
  | "awarded"
  | "declined"
  | "withdrawn"
  | "complete";

export type PortfolioRow = {
  id: string;
  title: string;
  funder_id: string | null;
  funder_name: string | null;
  status: ApplicationStatus;
  stage_current: string;
  amount_requested: number | null;
  amount_awarded: number | null;
  restricted: boolean;
  deadline: string | null;
  updated_at: string;
  weighted_value: number;
  open_conditions: number;
  overdue_returns: number;
  next_return_due: string | null;
};

export type Application = {
  id: string;
  title: string;
  funder_id: string | null;
  funder_name: string | null;
  project_id: string | null;
  project_name: string | null;
  reference: string | null;
  application_type: string;
  programme_key: string | null;
  stage_current: string;
  status: ApplicationStatus;
  amount_requested: number | null;
  amount_awarded: number | null;
  restricted: boolean;
  deadline: string | null;
  submitted_at: string | null;
  decision_at: string | null;
  start_date: string | null;
  end_date: string | null;
  reporting_note: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
};

export type Funder = {
  id: string;
  ref_key: string | null;
  name: string;
  kind: string;
  website: string | null;
  contact_name: string | null;
  contact_email: string | null;
  relationship: string;
  notes: string | null;
  application_count: number;
};

export type CatalogueRow = {
  key: string;
  name: string;
  funder: string;
  funder_type: string;
  nations: string[];
  kind: string;
  amount_note: string | null;
  typical_award: string | null;
  match_note: string | null;
  eligibility: string;
  status: string;
  deadlines: string | null;
  route_url: string | null;
  docs_required: string[];
  reporting_note: string | null;
  last_verified: string;
  next_review: string;
  notes: string | null;
  stale: boolean;
};

export type GateItem = {
  id: string;
  criterion: string;
  kind: "manual" | "doc";
  ref?: string | null;
  done: boolean;
};

export type Stage = {
  id: string;
  stage_key: string;
  label: string;
  position: number;
  status: string;
  planned_start: string | null;
  planned_end: string | null;
  forecast_start: string | null;
  forecast_end: string | null;
  actual_start: string | null;
  actual_end: string | null;
  gate: GateItem[];
  gate_signed_off_at: string | null;
  gate_exceptions: string | null;
};

export type Task = {
  id: string;
  stage_key: string;
  title: string;
  details: string | null;
  owner_name: string | null;
  due_date: string | null;
  is_milestone: boolean;
  tags: string[];
  status: string;
  source: string;
};

export type RegistryDoc = {
  id: string;
  doc_type_key: string;
  title: string;
  stage_key: string;
  status: string;
  ai_draftable: boolean;
  reporting_period_id: string | null;
  current_file_key: string | null;
  versions: { version: number; note?: string | null; created_at: string }[];
  notes: string | null;
  updated_at: string;
};

export type Condition = {
  id: string;
  number: string;
  description: string;
  pre_drawdown: boolean;
  status: string;
  due_date: string | null;
  submitted_at: string | null;
  discharged_at: string | null;
  notes: string | null;
};

export type ReportingPeriod = {
  id: string;
  application_id: string;
  label: string;
  period_start: string;
  period_end: string;
  due_date: string | null;
  status: string;
  submitted_at: string | null;
  accepted_at: string | null;
  notes: string | null;
  overdue: boolean;
};

export type CalendarRow = ReportingPeriod & {
  application_title: string;
  funder_name: string | null;
  rag: "green" | "amber" | "red";
};

export type Measure = {
  id: string;
  name: string;
  definition: string | null;
  unit: string;
  baseline: number | null;
  target: number | null;
  position: number;
  notes: string | null;
};

export type Outcome = {
  id: string;
  measure_id: string;
  measure_name: string;
  unit: string;
  target: number | null;
  reporting_period_id: string;
  value: number | null;
  narrative: string | null;
  evidence_notes: string | null;
  recorded_at: string;
};

export type DraftKind =
  | "case_for_support"
  | "funding_application"
  | "monitoring_report"
  | "impact_evaluation"
  | "application_form";

export type DraftJob = {
  id: string;
  application_id: string;
  kind: DraftKind | "impact_card";
  status: "queued" | "running" | "succeeded" | "failed";
  error: string | null;
  document_id: string | null;
  download_url: string | null;
  to_confirm_count: number;
  llm_calls: number;
  cost_usd: number;
  created_at: string;
  updated_at: string;
};

export type UploadTicket = { upload_url: string; file_key: string };
export type DownloadTicket = { download_url: string };

// -- calls -------------------------------------------------------------------

export const submitDraft = (
  applicationId: string,
  body: {
    kind: DraftKind;
    reporting_period_id?: string;
    question_set_key?: string;
    instructions?: string;
  }
) =>
  gr<DraftJob>(`/grants/applications/${applicationId}/drafts`, {
    method: "POST",
    body: JSON.stringify(body),
  });

export const submitImpactCard = (applicationId: string) =>
  gr<DraftJob>(`/grants/applications/${applicationId}/impact-card`, { method: "POST" });

export const getDraftJob = (jobId: string) => gr<DraftJob>(`/grants/drafts/${jobId}`);

export const listActiveDraftJobs = (applicationId: string) =>
  gr<DraftJob[]>(`/grants/applications/${applicationId}/drafts`);

// -- display -----------------------------------------------------------------

export const STAGES = [
  "case",
  "prospect",
  "apply",
  "decision",
  "deliver",
  "monitor",
  "evaluate",
] as const;

export const STAGE_LABEL: Record<string, string> = {
  case: "Case",
  prospect: "Prospect",
  apply: "Apply",
  decision: "Decision",
  deliver: "Deliver",
  monitor: "Monitor",
  evaluate: "Evaluate",
};

export const STATUS_LABEL: Record<ApplicationStatus, string> = {
  pipeline: "In pipeline",
  drafting: "Drafting",
  submitted: "Submitted",
  awarded: "Awarded",
  declined: "Declined",
  withdrawn: "Withdrawn",
  complete: "Complete",
};

export const DRAFT_LABEL: Record<string, string> = {
  case_for_support: "Case for support",
  funding_application: "Funding application",
  monitoring_report: "Monitoring return",
  impact_evaluation: "End-of-grant evaluation",
  impact_card: "Impact card",
  application_form: "Funder's application form",
};

export const RAG_DOT: Record<string, string> = {
  green: "bg-accent",
  amber: "bg-warn",
  red: "bg-danger",
};

export const fmtDate = (d: string | null | undefined) =>
  d ? new Date(d).toLocaleDateString("en-GB") : "—";

export const fmtMoney = (n: number | null | undefined) =>
  n == null ? "—" : "£" + n.toLocaleString("en-GB", { maximumFractionDigits: 0 });

/** Percentage of target achieved, or null when there is nothing to compare. */
export function achievedShare(value: number | null, target: number | null): number | null {
  if (value == null || target == null || target === 0) return null;
  return value / target;
}

/**
 * A catalogue row nobody has verified must never look authoritative.
 *
 * Seeded rows ship `status: "unverified"` and past their review date, and the
 * drafting engine puts a matching warning on page one of any bid built from
 * one — so the badge here is the same fact, shown earlier.
 */
export function catalogueWarning(row: CatalogueRow): string | null {
  if (row.status !== "open") return `${row.status} — confirm with the funder before relying on it`;
  if (row.stale) return "past its review date — confirm with the funder";
  return null;
}
