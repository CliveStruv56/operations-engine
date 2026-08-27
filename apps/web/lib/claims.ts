// The claims register: what this workspace asserts about itself.
//
// Unflagged core, like funder forms and unlike the drafting modules that read
// from it. Every vertical needs these facts, so the types and fetchers live
// here rather than inside any one module's lib.
import { api } from "@/lib/api";
import { tenantId } from "@/lib/groundwork";

const cl = <T,>(path: string, init: RequestInit = {}) =>
  api<T>(path, init, tenantId() ?? undefined);

export type ClaimKind = {
  key: string;
  label: string;
  category: "identity" | "governance" | "finance" | "people" | "assurance" | "delivery" | "community";
  value_kind: "text" | "number" | "money" | "date" | "list" | "boolean";
  unit: string | null;
  cardinality: "single" | "multi";
  periodic: boolean;
  review_days: number | null;
  statement_template: string;
  question_hints: string[];
  register_key: string | null;
  notes: string | null;
};

export type ClaimStatus = "proposed" | "confirmed" | "rejected" | "superseded";

export type Claim = {
  id: string;
  kind: string;
  label: string;
  category: ClaimKind["category"];
  /** Which instance of a multi-valued kind — a trustee's name, a policy. */
  subject: string | null;
  /** Which slice of a series — "2024/25". Null for the current standing fact. */
  period: string | null;
  statement: string;
  value: unknown;
  unit: string | null;
  as_of: string | null;
  expires_on: string | null;
  status: ClaimStatus;
  source: "register" | "document" | "draft" | "typed" | "module";
  /** Public register page, for a register-sourced claim. */
  source_ref: string | null;
  source_document_id: string | null;
  source_document_title: string | null;
  source_chunk_id: string | null;
  owner_membership_id: string | null;
  last_verified: string | null;
  next_review: string | null;
  notes: string | null;
  /** Derived, never stored — past its review date. */
  stale: boolean;
  /** Derived — the certificate behind it has lapsed. */
  expired: boolean;
};

export type RegisterImport = {
  register_key: "companies_house" | "charity_commission" | "oscr" | "ccni";
  source_url: string;
  registration_status: string;
  /** The register's record is not live. The UI must lead with this. */
  inactive: boolean;
  proposed: Claim[];
  unchanged: number;
  skipped_unknown_kinds: string[];
};

export type ClaimBody = {
  kind: string;
  subject?: string | null;
  period?: string | null;
  statement: string;
  value?: unknown;
  unit?: string | null;
  as_of?: string | null;
  expires_on?: string | null;
  notes?: string | null;
  source_document_id?: string | null;
};

/**
 * The register in four numbers, for a count shown outside the register.
 *
 * `stale` and `expired` break `needs_attention` down rather than adding to it —
 * one claim can be both, so they may sum to more than it does.
 */
export type ClaimSummary = {
  needs_attention: number;
  stale: number;
  expired: number;
  proposals: number;
};

export const listClaims = () => cl<Claim[]>("/claims");

export const getClaimSummary = () => cl<ClaimSummary>("/claims/summary");

/** How many facts about the organisation are waiting for a person. */
export const claimsWaiting = (s: ClaimSummary) => s.needs_attention + s.proposals;

/**
 * What that number means, in words — a bare badge tells nobody which of three
 * different jobs they have, and lapsed cover is not the same job as an unread
 * proposal. Ordered worst first, and null when there is nothing to say.
 */
export function claimsWaitingLabel(s: ClaimSummary): string | null {
  const parts: string[] = [];
  if (s.expired > 0) parts.push(`${s.expired} lapsed`);
  // Every lapsed fact is past review too; say the worse thing once.
  const overdue = Math.max(0, s.stale - s.expired);
  if (overdue > 0) parts.push(`${overdue} past review`);
  if (s.proposals > 0) parts.push(`${s.proposals} to check`);
  return parts.length > 0 ? parts.join(", ") : null;
}

export const listClaimKinds = () => cl<ClaimKind[]>("/claims/kinds");

export const createClaim = (body: ClaimBody) =>
  cl<Claim>("/claims", { method: "POST", body: JSON.stringify(body) });

export const updateClaim = (
  id: string,
  body: Partial<ClaimBody> & {
    status?: "confirmed" | "rejected";
    verified?: boolean;
    /** Who keeps this true. The one field where sending null means "clear it"
     *  rather than "leave it alone" — omit it to leave the owner untouched. */
    owner_membership_id?: string | null;
  },
) => cl<Claim>(`/claims/${id}`, { method: "PATCH", body: JSON.stringify(body) });

export const deleteClaim = (id: string) => cl<void>(`/claims/${id}`, { method: "DELETE" });

/** The four registers a workspace can seed itself from, and who each is for. */
export const REGISTERS = [
  {
    route: "companies-house",
    label: "Companies House",
    hint: "Any UK company — England, Wales, Scotland or Northern Ireland.",
    placeholder: "07123456",
  },
  {
    route: "charity-commission",
    label: "Charity Commission",
    hint: "Charities registered in England and Wales.",
    placeholder: "1234567",
  },
  {
    route: "oscr",
    label: "OSCR",
    hint: "Charities registered in Scotland.",
    placeholder: "SC012345",
  },
  {
    route: "ccni",
    label: "CCNI",
    hint:
      "Charities registered in Northern Ireland — read from a snapshot of the register, " +
      "so a very recent change may not show yet.",
    placeholder: "NIC100012",
  },
] as const;

export const importFromRegister = (route: string, number: string, allowInactive = false) =>
  cl<RegisterImport>(`/claims/import/${route}`, {
    method: "POST",
    body: JSON.stringify({ number, allow_inactive: allowInactive }),
  });

/**
 * The caveat to show against a claim, or null when there is nothing to say.
 *
 * Expiry and staleness are different problems and saying the wrong one is
 * worse than saying nothing: lapsed cover is a fact that is now false, while
 * an overdue review is a fact nobody has checked lately.
 */
export function claimNote(claim: Claim): string | null {
  if (claim.expired)
    return `This lapsed on ${fmtClaimDate(claim.expires_on)}. It should not be relied on in anything you send out.`;
  if (claim.status === "proposed") return null; // the row already reads as a question
  if (claim.stale)
    return claim.last_verified
      ? `Last checked ${fmtClaimDate(claim.last_verified)}, and now past review.`
      : "Nobody has checked this yet.";
  if (!claim.last_verified) return "Nobody has checked this yet.";
  return null;
}

/** Where a claim came from, in words a non-technical reader can act on. */
export function sourceLabel(claim: Claim): string {
  switch (claim.source) {
    case "register":
      return "from the public register";
    case "document":
      return claim.source_document_title
        ? `read from ${claim.source_document_title}`
        : "read from a document";
    case "draft":
      return "found in a document you produced";
    case "module":
      return "kept up to date in the community profile";
    default:
      return "entered here";
  }
}

/** Group claims for display. A register is a list, not a dashboard. */
export const CATEGORY_ORDER: ClaimKind["category"][] = [
  "identity",
  "governance",
  "finance",
  "people",
  "assurance",
  "delivery",
  "community",
];

export const CATEGORY_LABELS: Record<ClaimKind["category"], string> = {
  identity: "Who you are",
  governance: "Governance",
  finance: "Finances",
  people: "People",
  assurance: "Policies and cover",
  delivery: "What you do",
  community: "Your community",
};

/** Turn a typed field into the value the API stores. */
export function parseClaimValue(kind: ClaimKind, raw: string): unknown {
  const trimmed = raw.trim();
  if (!trimmed) return null;
  if (kind.value_kind === "number" || kind.value_kind === "money") {
    const n = Number(trimmed.replace(/,/g, ""));
    return Number.isFinite(n) ? n : trimmed;
  }
  if (kind.value_kind === "boolean") return trimmed === "true" || trimmed === "yes";
  return trimmed;
}

/** The sentence a prompt and a list row read, matching the API renderer. */
export function fillStatement(kind: ClaimKind, subject: string | null, value: unknown): string {
  const rendered = formatClaimValue(kind, value);
  try {
    return kind.statement_template
      .replaceAll("{value}", rendered)
      .replaceAll("{subject}", subject || kind.label)
      .trim();
  } catch {
    return rendered ? `${kind.label}: ${rendered}` : kind.label;
  }
}

function formatClaimValue(kind: ClaimKind, value: unknown): string {
  if (value == null || value === "") return "";
  if (Array.isArray(value)) return value.map(String).join(", ");
  if (typeof value === "object") return "";
  if (kind.value_kind === "money") {
    const n = typeof value === "string" ? Number(value) : value;
    if (typeof n === "number" && !Number.isNaN(n)) {
      return `£${n.toLocaleString("en-GB", { maximumFractionDigits: 0 })}`;
    }
  }
  if (kind.value_kind === "date" && typeof value === "string") {
    const worded = dateInWords(value);
    if (worded) return worded;
  }
  return String(value);
}

/** "15 September 2026", or null when the string is not an ISO date. Must match
 *  the API and worker statement renderers (`format_value` / `render_statement`). */
function dateInWords(iso: string): string | null {
  if (!/^\d{4}-\d{2}-\d{2}/.test(iso.trim())) return null;
  const d = new Date(iso.trim().slice(0, 10) + "T00:00:00");
  if (Number.isNaN(d.getTime())) return null;
  return d.toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric" });
}

/** Claims dates for row copy and notes — "15 Sep 2026". */
export const fmtClaimDate = (iso: string | null | undefined) =>
  iso
    ? new Date(iso).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" })
    : "—";
