// The community profile: the place this workspace covers, as structured data.
//
// Feature-flagged module (`community`). Assets are facilities in one table
// with a category taxonomy and free per-category attributes; statistics are
// the numeric series, and a stat that names a claim kind feeds the claims
// register on every save.
import { api } from "@/lib/api";
import { tenantId } from "@/lib/groundwork";

const cm = <T,>(path: string, init: RequestInit = {}) =>
  api<T>(path, init, tenantId() ?? undefined);

export type AssetCategory =
  | "transport"
  | "education"
  | "health"
  | "housing"
  | "retail_services"
  | "community_spaces"
  | "energy"
  | "employment"
  | "other";

export type AssetStatus = "open" | "closed" | "seasonal" | "planned";

export type CommunityProfile = {
  id: string;
  place_name: string;
  description: string | null;
  geography_note: string | null;
  council_area: string | null;
  settlements: string[];
  census_area_codes: string[];
  data_sources_note: string | null;
  created_by: string | null;
  created_at: string;
  updated_at: string;
};

export type ProfileBody = {
  place_name: string;
  description?: string | null;
  geography_note?: string | null;
  council_area?: string | null;
  settlements?: string[];
  census_area_codes?: string[];
  data_sources_note?: string | null;
};

export type CommunityAsset = {
  id: string;
  category: AssetCategory;
  subcategory: string | null;
  name: string;
  description: string | null;
  attributes: Record<string, string | number | boolean>;
  status: AssetStatus;
  settlement: string | null;
  contact: string | null;
  url: string | null;
  notes: string | null;
  created_by: string | null;
  created_at: string;
  updated_at: string;
};

export type AssetBody = {
  category: AssetCategory;
  subcategory?: string | null;
  name: string;
  description?: string | null;
  attributes?: Record<string, string | number | boolean>;
  status?: AssetStatus;
  settlement?: string | null;
  contact?: string | null;
  url?: string | null;
  notes?: string | null;
};

export type CommunityStat = {
  id: string;
  label: string;
  value: number;
  unit: string | null;
  period: string | null;
  as_of: string | null;
  claim_kind: string | null;
  source: string | null;
  source_url: string | null;
  notes: string | null;
  /** The register claim this save asserted — set only on a write that fed it. */
  claim_id: string | null;
  created_by: string | null;
  created_at: string;
  updated_at: string;
};

export type StatBody = {
  label: string;
  value: number;
  unit?: string | null;
  period?: string | null;
  as_of?: string | null;
  claim_kind?: string | null;
  source?: string | null;
  source_url?: string | null;
  notes?: string | null;
};

export const getCommunityProfile = () => cm<CommunityProfile | null>("/community/profile");

export const putCommunityProfile = (body: ProfileBody) =>
  cm<CommunityProfile>("/community/profile", { method: "PUT", body: JSON.stringify(body) });

export const listCommunityAssets = () => cm<CommunityAsset[]>("/community/assets");

export const createCommunityAsset = (body: AssetBody) =>
  cm<CommunityAsset>("/community/assets", { method: "POST", body: JSON.stringify(body) });

export const updateCommunityAsset = (id: string, body: Partial<AssetBody>) =>
  cm<CommunityAsset>(`/community/assets/${id}`, { method: "PATCH", body: JSON.stringify(body) });

export const deleteCommunityAsset = (id: string) =>
  cm<void>(`/community/assets/${id}`, { method: "DELETE" });

export const listCommunityStats = () => cm<CommunityStat[]>("/community/statistics");

export const createCommunityStat = (body: StatBody) =>
  cm<CommunityStat>("/community/statistics", { method: "POST", body: JSON.stringify(body) });

export const updateCommunityStat = (id: string, body: Partial<StatBody>) =>
  cm<CommunityStat>(`/community/statistics/${id}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });

export const deleteCommunityStat = (id: string) =>
  cm<void>(`/community/statistics/${id}`, { method: "DELETE" });

export type CommunityExportJob = {
  id: string;
  kind: string;
  status: "queued" | "running" | "succeeded" | "failed";
  error: string | null;
  /** Presigned GET, present only once the worker has landed the file. */
  download_url: string | null;
  created_at: string;
  updated_at: string;
};

export const submitProfilePdf = () =>
  cm<CommunityExportJob>("/community/profile/pdf", { method: "POST" });

export const getCommunityExport = (id: string) =>
  cm<CommunityExportJob>(`/community/exports/${id}`);

/** Display order for the profile page — the shape of a place, roughly in the
 *  order a funder or an incomer asks about it. */
export const ASSET_CATEGORY_ORDER: AssetCategory[] = [
  "transport",
  "education",
  "health",
  "housing",
  "retail_services",
  "community_spaces",
  "energy",
  "employment",
  "other",
];

export const ASSET_CATEGORY_LABELS: Record<AssetCategory, string> = {
  transport: "Getting here and around",
  education: "Schools and learning",
  health: "Health and wellbeing",
  housing: "Housing",
  retail_services: "Shops and services",
  community_spaces: "Community spaces",
  energy: "Energy",
  employment: "Work and employers",
  other: "Everything else",
};

export const ASSET_STATUS_LABELS: Record<AssetStatus, string> = {
  open: "open",
  closed: "closed",
  seasonal: "seasonal",
  planned: "planned",
};

/** Attribute keys the form suggests per category. Suggestions, not a schema —
 *  the API accepts any short scalar, so a place with something these miss
 *  simply types its own key. */
export const SUGGESTED_ATTRIBUTES: Record<AssetCategory, string[]> = {
  transport: ["operator", "frequency", "destinations", "booking"],
  education: ["pupils", "ages", "nursery", "after_school_club"],
  health: ["opening_hours", "dispensing", "visiting_service"],
  housing: ["homes", "tenure", "provider"],
  retail_services: ["opening_hours", "services", "fuel", "post_office"],
  community_spaces: ["capacity", "bookable", "managed_by"],
  energy: ["capacity_kw", "owner", "commissioned"],
  employment: ["employees", "sector"],
  other: [],
};

/** "12 Mar 2026" for row copy; em dash when there is no date. */
export const fmtCommunityDate = (iso: string | null | undefined) =>
  iso
    ? new Date(iso).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" })
    : "—";
