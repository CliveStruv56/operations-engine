import { afterEach, describe, expect, it, vi } from "vitest";
import {
  BASELINE_POLICY,
  buildCsp,
  cspEnforced,
  cspResponseHeader,
  makeNonce,
  originsFromEnv,
} from "./csp";

const ORIGINS = {
  api: "https://api.example.co.uk/",
  supabase: "https://abc.supabase.co",
  storage: "https://acct.r2.cloudflarestorage.com",
};

const directive = (policy: string, name: string) =>
  policy.split("; ").find((d) => d.startsWith(`${name} `));

// Code review item 13 / plan F3: script-src and connect-src, nonce-based.
describe("content-security policy", () => {
  it("allows scripts only by nonce, with strict-dynamic and no unsafe-inline", () => {
    const policy = buildCsp("abc123==", ORIGINS);
    const scripts = directive(policy, "script-src")!;
    expect(scripts).toContain("'nonce-abc123=='");
    expect(scripts).toContain("'strict-dynamic'");
    expect(scripts).not.toContain("unsafe-inline");
    expect(scripts).not.toContain("unsafe-eval");
  });

  it("only allows eval in development", () => {
    expect(directive(buildCsp("n", ORIGINS, { dev: true }), "script-src")).toContain(
      "'unsafe-eval'"
    );
  });

  it("connects only to this site, the API, Supabase and storage", () => {
    expect(directive(buildCsp("n", ORIGINS), "connect-src")).toBe(
      "connect-src 'self' https://api.example.co.uk https://abc.supabase.co https://acct.r2.cloudflarestorage.com"
    );
  });

  it("drops origins that are missing or not http(s)", () => {
    const policy = buildCsp("n", { api: "javascript:alert(1)", supabase: "not a url" });
    expect(directive(policy, "connect-src")).toBe("connect-src 'self'");
    expect(directive(policy, "img-src")).toBe("img-src 'self' data: blob:");
  });

  it("allows the presigned logo from storage", () => {
    expect(directive(buildCsp("n", ORIGINS), "img-src")).toContain(
      "https://acct.r2.cloudflarestorage.com"
    );
  });

  it("keeps every baseline directive and reports violations", () => {
    const policy = buildCsp("n", ORIGINS);
    for (const d of BASELINE_POLICY.split("; ")) expect(policy).toContain(d);
    expect(policy).toContain("report-uri /api/csp-report");
  });

  afterEach(() => vi.unstubAllEnvs());

  it("reads origins from the public env, defaulting the API like lib/api.ts", () => {
    vi.stubEnv("NEXT_PUBLIC_API_URL", undefined);
    vi.stubEnv("NEXT_PUBLIC_STORAGE_ORIGIN", "https://s.example");
    expect(originsFromEnv().api).toBe("http://localhost:8000");
    expect(originsFromEnv().storage).toBe("https://s.example");
  });

  it("makes a fresh base64 nonce every time", () => {
    const a = makeNonce();
    expect(a).toMatch(/^[A-Za-z0-9+/]{22}==$/);
    expect(makeNonce()).not.toBe(a);
  });

  it("is report-only unless CSP_ENFORCE=1", () => {
    expect(cspEnforced({})).toBe(false);
    expect(cspEnforced({ CSP_ENFORCE: "true" })).toBe(false);
    expect(cspEnforced({ CSP_ENFORCE: "1" })).toBe(true);
    expect(cspResponseHeader("P", false)).toEqual(["Content-Security-Policy-Report-Only", "P"]);
    expect(cspResponseHeader("P", true)).toEqual(["Content-Security-Policy", "P"]);
  });
});
