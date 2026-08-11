import { describe, expect, it } from "vitest";
import { blockedReason, type PromoteCandidate } from "./admin";

const candidate = (over: Partial<PromoteCandidate> = {}): PromoteCandidate => ({
  tenant_id: "t1",
  tenant_name: "Riverside CLT",
  key: "ahf_eoi",
  name: "Expression of interest",
  funder: "Architectural Heritage Fund",
  stage: "eoi",
  status: "open",
  source_url: "https://example.invalid/apply",
  question_count: 8,
  limits_missing: 0,
  last_verified: "2026-08-11",
  next_review: "2026-11-09",
  stale: false,
  in_catalogue: false,
  ...over,
});

describe("blockedReason", () => {
  it("clears a form the workspace has confirmed with every limit recorded", () => {
    expect(blockedReason(candidate())).toBeNull();
  });

  it("blocks one the workspace has not confirmed", () => {
    expect(blockedReason(candidate({ status: "unverified" }))).toContain("not confirmed");
    expect(blockedReason(candidate({ stale: true }))).toContain("not confirmed");
  });

  it("blocks one still carrying a blank limit", () => {
    // Honest in a workspace's own copy; a silent gap in a stranger's draft.
    expect(blockedReason(candidate({ limits_missing: 1 }))).toBe(
      "1 question still has no limit"
    );
    expect(blockedReason(candidate({ limits_missing: 3 }))).toContain("3 questions");
  });

  it("blocks one that cannot be re-checked", () => {
    expect(blockedReason(candidate({ source_url: null }))).toContain("where its questions came from");
  });

  it("reports the workspace's own confirmation first", () => {
    // An unverified form with blanks should send the operator back to the
    // workspace, not to the funder's website.
    expect(blockedReason(candidate({ status: "unverified", limits_missing: 2 }))).toContain(
      "not confirmed"
    );
  });
});
