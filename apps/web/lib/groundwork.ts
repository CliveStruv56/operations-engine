// Shared types + helpers for the Development Projects (Groundwork) module.
import { api } from "@/lib/api";

export function tenantId(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("tenantId");
}

export const gw = <T,>(path: string, init: RequestInit = {}) =>
  api<T>(path, init, tenantId() ?? undefined);

// Presigned URLs come back from the API; only open ones that are https/http
// and, when NEXT_PUBLIC_STORAGE_ORIGIN is set, point at our storage host.
export function openPresigned(url: string): void {
  let parsed: URL;
  try {
    parsed = new URL(url);
  } catch {
    return;
  }
  if (parsed.protocol !== "https:" && parsed.protocol !== "http:") return;
  const allowed = process.env.NEXT_PUBLIC_STORAGE_ORIGIN;
  if (allowed && parsed.origin !== new URL(allowed).origin) return;
  window.open(url, "_blank", "noopener,noreferrer");
}

export type Rag = { programme: string; cost: string; risk: string };
export type PortfolioRow = {
  id: string;
  name: string;
  client_org: string | null;
  status: string;
  dormancy_reason: string | null;
  stage_current: string;
  homes_planned: number | null;
  target_completion: string | null;
  rag: Rag;
  next_milestone: { title: string; due_date: string } | null;
  open_risks: number;
  outstanding_pre_commencement: number;
  overdue_tasks: number;
  updated_at: string;
};

export type Detail = PortfolioRow & {
  project_type: string;
  delivery_route: string | null;
  site_address: string | null;
  start_date: string | null;
  applicability: Record<string, boolean>;
  contract_facts: Record<string, unknown>;
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
  riba_ref: string | null;
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
  current_file_key: string | null;
  versions: { version: number; note?: string | null; created_at: string }[];
  updated_at: string;
};
export type BudgetLine = {
  category: string;
  label: string;
  budget: number;
  forecast: number;
  actual: number;
  note?: string | null;
};
export type Funding = {
  id: string;
  programme_key: string | null;
  name: string;
  funder: string | null;
  kind: string;
  amount_sought: number | null;
  amount_secured: number | null;
  status: string;
  drawdown_schedule: { label: string; due_date?: string; amount?: number; status?: string }[];
};
export type Programme = {
  key: string;
  name: string;
  funder: string;
  nations: string[];
  kind: string;
  stage_fit: string[];
  amount_note: string | null;
  eligibility: string;
  status: string;
  docs_required: string[];
  last_verified: string;
  stale: boolean;
};
export type Risk = {
  id: string;
  category: string;
  description: string;
  likelihood: number;
  impact: number;
  owner_name: string | null;
  mitigation: string | null;
  status: string;
};
export type Condition = {
  id: string;
  application_ref: string | null;
  number: string;
  description: string;
  pre_commencement: boolean;
  status: string;
};
export type ActivityEntry = { action: string; created_at: string };
export type UploadTicket = { upload_url: string; file_key: string };
export type DownloadTicket = { download_url: string };
export type Budget = { lines: BudgetLine[] };
export type Stakeholder = {
  id: string;
  name: string;
  org: string | null;
  role: string;
  email: string | null;
  phone: string | null;
  last_contact: string | null;
};

export type DraftKind =
  | "monthly_report"
  | "feasibility_study"
  | "funding_bid"
  | "application_form";
export type DraftJob = {
  id: string;
  project_id: string;
  kind: DraftKind;
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

export const submitDraft = (
  projectId: string,
  body: {
    kind: DraftKind;
    month?: string;
    funding_source_id?: string;
    question_set_key?: string;
    instructions?: string;
  }
) => gw<DraftJob>(`/projects/${projectId}/drafts`, { method: "POST", body: JSON.stringify(body) });

export const getDraftJob = (jobId: string) => gw<DraftJob>(`/projects/drafts/${jobId}`);

export const listActiveDraftJobs = (projectId: string) =>
  gw<DraftJob[]>(`/projects/${projectId}/drafts`);

export const submitHealthCard = (projectId: string) =>
  gw<DraftJob>(`/projects/${projectId}/health-card`, { method: "POST" });

export const STAGES = ["group", "site", "plan", "build", "live"] as const;
export const STAGE_LABEL: Record<string, string> = {
  group: "Group",
  site: "Site",
  plan: "Plan",
  build: "Build",
  live: "Live",
};
export const RAG_DOT: Record<string, string> = {
  // --ok, not --grounded: RAG health is a status, and the trust green must
  // not become a general-purpose green.
  green: "bg-ok",
  amber: "bg-warn",
  red: "bg-danger",
};
export const fmtDate = (d: string | null | undefined) =>
  d ? new Date(d).toLocaleDateString("en-GB") : "—";
// Decimal fields arrive as JSON strings (Pydantic v2 default), so coerce first.
export const fmtMoney = (n: number | string | null | undefined) => {
  const v = typeof n === "string" ? Number(n) : n;
  return v == null || Number.isNaN(v)
    ? "—"
    : "£" + v.toLocaleString("en-GB", { maximumFractionDigits: 0 });
};
