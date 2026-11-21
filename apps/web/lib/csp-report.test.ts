import { describe, expect, it } from "vitest";
import { summarise } from "./csp-report";

describe("CSP violation reports", () => {
  it("reads the report-uri shape and strips query strings", () => {
    const [r] = summarise({
      "csp-report": {
        "document-uri": "https://www.flowgridos.co.uk/app?c=abc",
        "effective-directive": "connect-src",
        "blocked-uri": "https://acct.r2.cloudflarestorage.com/b/k?X-Amz-Signature=secret",
        disposition: "report",
      },
    });
    expect(r).toMatchObject({
      directive: "connect-src",
      page: "https://www.flowgridos.co.uk/app",
      blocked: "https://acct.r2.cloudflarestorage.com/b/k",
      disposition: "report",
    });
    expect(JSON.stringify(r)).not.toContain("secret");
  });

  it("reads the Reporting API shape and caps the count", () => {
    const one = { type: "csp-violation", body: { effectiveDirective: "script-src-elem", blockedURL: "inline" } };
    const out = summarise(Array.from({ length: 20 }, () => one));
    expect(out).toHaveLength(5);
    expect(out[0]).toMatchObject({ directive: "script-src-elem", blocked: "inline" });
  });

  it("ignores anything else and clips long values", () => {
    expect(summarise("nope")).toEqual([]);
    expect(summarise({ other: 1 })).toEqual([]);
    const [r] = summarise({ "csp-report": { "script-sample": "x".repeat(500) } });
    expect(r.sample).toHaveLength(80);
  });
});
