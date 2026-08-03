// Operator console (platform admin) — types + fetch helper. Admin endpoints
// carry no tenant context, so no X-Tenant-Id header.
import { api } from "@/lib/api";

export const admin = <T,>(path: string, init: RequestInit = {}) => api<T>(path, init);

export type AdminTenantRow = {
  id: string;
  name: string;
  plan: string;
  seats: number;
  trial_ends_at: string | null;
  created_at: string;
  features: Record<string, boolean>;
  brand: Record<string, unknown>;
  suspended_at: string | null;
  suspended_reason: string | null;
  member_count: number;
  pending_invites: number;
  month_cost_usd: number;
  month_requests: number;
};

export type AdminTenantPatch = {
  name?: string;
  seats?: number;
  trial_ends_at?: string | null;
  plan?: string;
  brand_accent?: string;
};

export const PLANS = ["trial", "core", "pro", "managed"] as const;

/** Partial: send only what changed, so concurrent edits to different fields
 *  cannot clobber one another. */
export const updateTenant = (tenantId: string, patch: AdminTenantPatch) =>
  admin<AdminTenant>(`/admin/tenants/${tenantId}`, {
    method: "PATCH",
    body: JSON.stringify(patch),
  });

export const suspendTenant = (tenantId: string, reason: string) =>
  admin<AdminTenant>(`/admin/tenants/${tenantId}/suspend`, {
    method: "POST",
    body: JSON.stringify({ reason }),
  });

export const resumeTenant = (tenantId: string) =>
  admin<AdminTenant>(`/admin/tenants/${tenantId}/resume`, { method: "POST" });

export type AdminTenant = {
  id: string;
  name: string;
  plan: string;
  seats: number;
  trial_ends_at: string | null;
  features: Record<string, boolean>;
  brand: Record<string, unknown>;
  suspended_at: string | null;
  suspended_reason: string | null;
};

export type AdminInvite = {
  token: string;
  email: string;
  role: string;
  expires_at: string;
};

export type AdminTenantCreated = {
  id: string;
  name: string;
  seats: number;
  trial_ends_at: string | null;
  features: Record<string, boolean>;
  brand: Record<string, unknown>;
  invite: AdminInvite;
};

/** Mirrors the API's module manifest (apps/api/app/modules.py). Keys the API
 *  does not know are rejected with a 422, so the two lists cannot silently
 *  drift into a flag that looks enabled here and 404s in the app. */
export const FEATURE_FLAGS = [
  { key: "projects", label: "Development projects" },
  { key: "grants", label: "Grant funding" },
  { key: "contacts", label: "Contacts (CRM)" },
  { key: "web_search", label: "Web search" },
] as const;

export type AdminFeatures = { id: string; features: Record<string, boolean> };

/** Merge semantics: send only the flags that change. */
export const updateFeatures = (tenantId: string, features: Record<string, boolean>) =>
  admin<AdminFeatures>(`/admin/tenants/${tenantId}/features`, {
    method: "PATCH",
    body: JSON.stringify({ features }),
  });

export function inviteUrl(token: string): string {
  return `${window.location.origin}/invite/${token}`;
}
