import { afterEach, describe, expect, it, vi } from "vitest";
import nextConfig from "./next.config";
import { BASELINE_POLICY } from "./lib/csp";

// WEB-1: every route carries the headers that stop framing and sniffing.
describe("security headers", () => {
  it("apply to every path", async () => {
    const rules = await nextConfig.headers!();
    const all = rules.find((r) => r.source === "/:path*");
    expect(all).toBeDefined();
    const byKey = Object.fromEntries(all!.headers.map((h) => [h.key, h.value]));
    expect(byKey["X-Frame-Options"]).toBe("DENY");
    expect(byKey["X-Content-Type-Options"]).toBe("nosniff");
    expect(byKey["Referrer-Policy"]).toBe("strict-origin-when-cross-origin");
  });

  // F3: exactly one enforced CSP header per response. Report-only (the
  // default): the baseline on every route, the proxy adds the report-only
  // policy. Enforced: the proxy's policy on pages, the baseline on API routes.
  afterEach(() => vi.unstubAllEnvs());

  it("enforce the baseline everywhere while the full policy is report-only", async () => {
    vi.stubEnv("CSP_ENFORCE", "");
    const rules = await nextConfig.headers!();
    const csp = rules.filter((r) => r.headers.some((h) => h.key === "Content-Security-Policy"));
    expect(csp.map((r) => r.source)).toEqual(["/:path*"]);
    expect(csp[0].headers).toEqual([{ key: "Content-Security-Policy", value: BASELINE_POLICY }]);
    expect(BASELINE_POLICY).toContain("frame-ancestors 'none'");
  });

  it("leave pages to the proxy once CSP_ENFORCE=1", async () => {
    vi.stubEnv("CSP_ENFORCE", "1");
    const rules = await nextConfig.headers!();
    const csp = rules.filter((r) => r.headers.some((h) => h.key === "Content-Security-Policy"));
    expect(csp.map((r) => r.source)).toEqual(["/api/:path*"]);
  });

  it("does not advertise the framework", () => {
    expect(nextConfig.poweredByHeader).toBe(false);
  });
});
