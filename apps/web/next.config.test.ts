import { describe, expect, it } from "vitest";
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

  // F3: pages get their CSP from proxy.ts only. A CSP header from here on a
  // page would reach the renderer as the request's CSP and drop the nonce.
  it("leave pages' CSP to the proxy and give API routes the baseline", async () => {
    const rules = await nextConfig.headers!();
    const csp = rules.filter((r) => r.headers.some((h) => h.key === "Content-Security-Policy"));
    expect(csp.map((r) => r.source)).toEqual(["/api/:path*"]);
    expect(csp[0].headers).toEqual([{ key: "Content-Security-Policy", value: BASELINE_POLICY }]);
    expect(BASELINE_POLICY).toContain("frame-ancestors 'none'");
  });

  it("does not advertise the framework", () => {
    expect(nextConfig.poweredByHeader).toBe(false);
  });
});
