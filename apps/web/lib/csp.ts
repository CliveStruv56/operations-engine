/** Content-Security-Policy for every page (code review item 13 / WEB-1, plan
 * item F3).
 *
 * Scripts: a fresh nonce per request plus 'strict-dynamic'. proxy.ts puts
 * the policy on the request, Next reads the nonce from it and stamps it on
 * its own bootstrap and chunk scripts; everything those scripts load is
 * trusted through 'strict-dynamic'. No 'unsafe-inline' for scripts. 'self'
 * is only a fallback for browsers that predate 'strict-dynamic'.
 *
 * Connections: this site, the API (chat streams over fetch), Supabase auth,
 * and the storage host the browser PUTs uploads to (presigned R2 URLs are
 * path-style, so they share the endpoint's origin). Images add the storage
 * host for the presigned tenant logo.
 *
 * A nonce needs a server render per request, so the root layout opts every
 * page into dynamic rendering (app/layout.tsx). A prerendered page would
 * carry no nonce and every script on it would be refused. */

/** The directives that shipped on 12 Oct. They stay enforced on every
 * route: next.config.ts sends them, on pages too while the full policy is
 * report-only, and the full policy repeats them. */
export const BASELINE_DIRECTIVES = [
  "frame-ancestors 'none'",
  "base-uri 'self'",
  "object-src 'none'",
  "form-action 'self'",
];

export const BASELINE_POLICY = BASELINE_DIRECTIVES.join("; ");

/** Where violation reports go (app/api/csp-report/route.ts). */
export const CSP_REPORT_PATH = "/api/csp-report";

export type CspOrigins = {
  api?: string;
  supabase?: string;
  storage?: string;
};

function originOf(value: string | undefined): string | null {
  if (!value) return null;
  try {
    const { origin, protocol } = new URL(value);
    return protocol === "https:" || protocol === "http:" ? origin : null;
  } catch {
    return null;
  }
}

/** Origins from the NEXT_PUBLIC_* values the browser code already uses.
 * Each is read as a literal `process.env.NAME` so the build inlines the same
 * value the browser bundle got. */
export function originsFromEnv(): CspOrigins {
  return {
    api: process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000",
    supabase: process.env.NEXT_PUBLIC_SUPABASE_URL,
    storage: process.env.NEXT_PUBLIC_STORAGE_ORIGIN,
  };
}

/** A base64 nonce from 16 random bytes. */
export function makeNonce(): string {
  const bytes = new Uint8Array(16);
  crypto.getRandomValues(bytes);
  return btoa(String.fromCharCode(...bytes));
}

export function buildCsp(
  nonce: string,
  origins: CspOrigins,
  { dev = false }: { dev?: boolean } = {}
): string {
  const api = originOf(origins.api);
  const supabase = originOf(origins.supabase);
  const storage = originOf(origins.storage);
  const list = (...xs: (string | null | false)[]) =>
    [...new Set(xs.filter((x): x is string => Boolean(x)))].join(" ");

  const directives = [
    "default-src 'self'",
    // Dev only: React rebuilds server error stacks with eval.
    `script-src ${list("'self'", `'nonce-${nonce}'`, "'strict-dynamic'", dev && "'unsafe-eval'")}`,
    // Style attributes (React style props, server-rendered) cannot carry a
    // nonce, and a nonce here would switch 'unsafe-inline' off.
    "style-src 'self' 'unsafe-inline'",
    `img-src ${list("'self'", "data:", "blob:", storage)}`,
    "font-src 'self'",
    // Dev only: the hot-reload socket.
    `connect-src ${list("'self'", api, supabase, storage, dev && "ws:")}`,
    "frame-src 'none'",
    "worker-src 'self' blob:",
    "manifest-src 'self'",
    ...BASELINE_DIRECTIVES,
    `report-uri ${CSP_REPORT_PATH}`,
  ];
  return directives.join("; ");
}

/** Enforce only when CSP_ENFORCE=1; otherwise the full policy is sent as
 * Content-Security-Policy-Report-Only. Read at build time by next.config.ts
 * and at request time by proxy.ts, so changing it needs a redeploy. */
export function cspEnforced(env: Record<string, string | undefined> = process.env): boolean {
  return env.CSP_ENFORCE === "1";
}

/** The response header proxy.ts sets on a page.
 *
 * Never an enforced baseline beside a report-only policy: Next copies every
 * header the proxy sets onto the request too, and reads the nonce from the
 * request's Content-Security-Policy first — a nonce-less baseline there
 * would leave every script without its nonce. While report-only, the
 * baseline comes from next.config.ts instead, which touches responses only. */
export function cspResponseHeader(policy: string, enforce: boolean): [string, string] {
  return [enforce ? "Content-Security-Policy" : "Content-Security-Policy-Report-Only", policy];
}
