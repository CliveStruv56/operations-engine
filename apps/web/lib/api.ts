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

const NETWORK_MESSAGE = "Could not reach the server — check your connection and try again.";

/** A response body parsed as JSON, or NOT_JSON when it is not — a proxy's
 * 502 page is HTML, and `resp.json()` on it surfaced to users as
 * "Unexpected token '<'" (code review WEB-3). An empty body reads as null. */
const NOT_JSON = Symbol("not-json");
async function readJson(resp: Response): Promise<unknown> {
  const text = await resp.text().catch(() => "");
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch {
    return NOT_JSON;
  }
}

type ErrorBody = { error?: { code?: string; message?: string } } | null;
const errorOf = (body: unknown) =>
  (body !== NOT_JSON ? (body as ErrorBody)?.error : undefined) ?? {};

export async function api<T>(
  path: string,
  init: RequestInit = {},
  tenantId?: string
): Promise<T> {
  const headers = await buildHeaders(init, tenantId);
  let resp: Response;
  try {
    resp = await fetch(`${API_URL}/api/v1${path}`, { ...init, headers });
  } catch (err) {
    // Callers that pass their own AbortSignal expect to see the abort.
    if (err instanceof DOMException && err.name === "AbortError") throw err;
    throw new ApiError(0, "network", NETWORK_MESSAGE);
  }
  if (resp.status === 204) return undefined as T;
  const body = await readJson(resp);
  if (!resp.ok) {
    const err = errorOf(body);
    throw new ApiError(
      resp.status,
      err.code ?? "unknown",
      err.message ?? `Request failed (${resp.status}) — try again.`,
      err
    );
  }
  if (body === NOT_JSON) {
    throw new ApiError(resp.status, "bad_response", "The server sent an unexpected response — try again.");
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

/** POST that consumes the API's SSE chat stream (delta / done / error events).
 *
 * Exactly one of onDone / onError / onAbort is called, whatever happens: a
 * stream that ends without a `done` event (proxy idle timeout, API restart
 * mid-answer) or a network failure reports through onError rather than
 * leaving the caller waiting — the composer stays locked until one of the
 * three fires (code review WEB-2). It never throws. */
export async function apiStream(
  path: string,
  body: unknown,
  tenantId: string,
  handlers: SseHandlers,
  signal?: AbortSignal
): Promise<void> {
  let finished = false;
  const succeed = (message: Record<string, unknown>) => {
    finished = true;
    handlers.onDone(message);
  };
  const fail = (code: string, message: string) => {
    if (finished) return;
    finished = true;
    handlers.onError(code, message);
  };
  try {
    const init: RequestInit = { method: "POST", body: JSON.stringify(body) };
    const headers = await buildHeaders(init, tenantId);
    const resp = await fetch(`${API_URL}/api/v1${path}`, { ...init, headers, signal });
    if (!resp.ok || !resp.body) {
      const err = errorOf(await readJson(resp));
      fail(err.code ?? "unknown", err.message ?? `Request failed (${resp.status}) — try again.`);
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
        else if (event === "done") succeed(payload);
        else if (event === "error")
          fail(payload.error?.code ?? "unknown", payload.error?.message ?? "Stream failed");
      }
    }
    fail("stream_ended", "The answer was cut off before it finished — try again.");
  } catch (err) {
    if (finished) return;
    if (err instanceof DOMException && err.name === "AbortError") {
      finished = true;
      handlers.onAbort?.();
      return;
    }
    fail("network", NETWORK_MESSAGE);
  }
}
