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

async function buildHeaders(init: RequestInit, tenantId?: string): Promise<Headers> {
  const supabase = createClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();
  const headers = new Headers(init.headers);
  if (session) headers.set("Authorization", `Bearer ${session.access_token}`);
  if (tenantId) headers.set("X-Tenant-Id", tenantId);
  if (init.body) headers.set("Content-Type", "application/json");
  return headers;
}

export async function api<T>(
  path: string,
  init: RequestInit = {},
  tenantId?: string
): Promise<T> {
  const headers = await buildHeaders(init, tenantId);
  const resp = await fetch(`${API_URL}/api/v1${path}`, { ...init, headers });
  if (resp.status === 204) return undefined as T;
  const body = await resp.json();
  if (!resp.ok) {
    const err = body?.error ?? {};
    throw new ApiError(resp.status, err.code ?? "unknown", err.message ?? "Request failed", err);
  }
  return body as T;
}

export type SseHandlers = {
  onDelta: (content: string) => void;
  onDone: (message: Record<string, unknown>) => void;
  onError: (code: string, message: string) => void;
  /** Called when the caller aborts the stream (Stop button). */
  onAbort?: () => void;
};

/** POST that consumes the API's SSE chat stream (delta / done / error events). */
export async function apiStream(
  path: string,
  body: unknown,
  tenantId: string,
  handlers: SseHandlers,
  signal?: AbortSignal
): Promise<void> {
  const init: RequestInit = { method: "POST", body: JSON.stringify(body) };
  const headers = await buildHeaders(init, tenantId);
  try {
    const resp = await fetch(`${API_URL}/api/v1${path}`, { ...init, headers, signal });
    if (!resp.ok || !resp.body) {
      const err = (await resp.json().catch(() => null))?.error ?? {};
      handlers.onError(err.code ?? "unknown", err.message ?? "Request failed");
      return;
    }
    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      let sep;
      while ((sep = buffer.indexOf("\n\n")) !== -1) {
        const frame = buffer.slice(0, sep);
        buffer = buffer.slice(sep + 2);
        const event = frame.match(/^event: (.+)$/m)?.[1];
        const data = frame.match(/^data: (.+)$/m)?.[1];
        if (!event || !data) continue;
        const payload = JSON.parse(data);
        if (event === "delta") handlers.onDelta(payload.content);
        else if (event === "done") handlers.onDone(payload);
        else if (event === "error")
          handlers.onError(payload.error?.code ?? "unknown", payload.error?.message ?? "Stream failed");
      }
    }
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") {
      handlers.onAbort?.();
      return;
    }
    throw err;
  }
}
