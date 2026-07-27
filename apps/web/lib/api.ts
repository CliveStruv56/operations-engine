import { createClient } from "@/lib/supabase/client";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public payload?: unknown
  ) {
    super(message);
  }
}

export async function api<T>(
  path: string,
  init: RequestInit = {},
  tenantId?: string
): Promise<T> {
  const supabase = createClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();
  const headers = new Headers(init.headers);
  if (session) headers.set("Authorization", `Bearer ${session.access_token}`);
  if (tenantId) headers.set("X-Tenant-Id", tenantId);
  if (init.body) headers.set("Content-Type", "application/json");

  const resp = await fetch(`${API_URL}/api/v1${path}`, { ...init, headers });
  if (resp.status === 204) return undefined as T;
  const body = await resp.json();
  if (!resp.ok) {
    const err = body?.error ?? {};
    throw new ApiError(resp.status, err.code ?? "unknown", err.message ?? "Request failed", err);
  }
  return body as T;
}
