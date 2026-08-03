import { describe, expect, it } from "vitest";
import { achievedShare, catalogueWarning, fmtMoney, type CatalogueRow } from "./grants";

const catalogue = (over: Partial<CatalogueRow> = {}): CatalogueRow => ({
  key: "fund",
  name: "A Fund",
  funder: "A Trust",
  funder_type: "trust",
  nations: ["england"],
  kind: "revenue",
  amount_note: null,
  typical_award: null,
  match_note: null,
  eligibility: "Charities",
  status: "open",
  deadlines: null,
  route_url: null,
  docs_required: [],
  reporting_note: null,
  last_verified: "2026-05-01",
  next_review: "2026-11-01",
  notes: null,
  stale: false,
  ...over,
});

describe("catalogueWarning", () => {
  it("stays quiet only for a row that is open and in date", () => {
    expect(catalogueWarning(catalogue())).toBeNull();
  });

  it("warns about an unverified row, which is how seeded rows arrive", () => {
    // Seeded catalogue rows ship status 'unverified' and stale on purpose, so
    // the badge fires until somebody has actually checked the funder.
    const warning = catalogueWarning(catalogue({ status: "unverified", stale: true }));
    expect(warning).toMatch(/unverified/);
    expect(warning).toMatch(/confirm with the funder/);
  });

  it("warns about a row that is open but past its review date", () => {
    expect(catalogueWarning(catalogue({ stale: true }))).toMatch(/past its review date/);
  });

  it("warns about a closed row even when it is in date", () => {
    expect(catalogueWarning(catalogue({ status: "closed" }))).toMatch(/closed/);
  });
});

describe("achievedShare", () => {
  it("is the fraction of target achieved", () => {
    expect(achievedShare(180, 250)).toBeCloseTo(0.72);
  });

  it("does not cap over-delivery", () => {
    expect(achievedShare(500, 250)).toBe(2);
  });

  it("is null when there is nothing to compare, never zero", () => {
    // "not recorded" and "achieved nothing" must not render the same.
    expect(achievedShare(null, 250)).toBeNull();
    expect(achievedShare(180, null)).toBeNull();
    expect(achievedShare(180, 0)).toBeNull();
  });

  it("treats a real zero as a real zero", () => {
    expect(achievedShare(0, 250)).toBe(0);
  });
});

describe("fmtMoney", () => {
  it("renders pounds without decimals", () => {
    expect(fmtMoney(27500)).toBe("£27,500");
  });

  it("renders an em dash for a missing amount rather than £0", () => {
    expect(fmtMoney(null)).toBe("—");
    expect(fmtMoney(0)).toBe("£0");
  });
});
