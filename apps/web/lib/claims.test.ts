import { describe, expect, it } from "vitest";
import { claimNote, fillStatement, parseClaimValue, type Claim, type ClaimKind } from "./claims";

const kind = (over: Partial<ClaimKind> = {}): ClaimKind => ({
  key: "annual_income",
  label: "Annual income",
  category: "finance",
  value_kind: "money",
  unit: "GBP",
  cardinality: "single",
  periodic: true,
  review_days: 365,
  statement_template: "The organisation's annual income was {value}.",
  question_hints: ["income"],
  register_key: null,
  notes: null,
  ...over,
});

describe("fillStatement", () => {
  it("renders money the way a funder would read it", () => {
    expect(fillStatement(kind(), null, 412000)).toBe(
      "The organisation's annual income was £412,000.",
    );
  });

  it("names the subject of a multi-valued kind", () => {
    expect(
      fillStatement(
        kind({
          key: "trustee",
          label: "Trustee",
          cardinality: "multi",
          value_kind: "text",
          statement_template: "{subject} is a trustee.",
        }),
        "Ade Cole",
        "Ade Cole",
      ),
    ).toBe("Ade Cole is a trustee.");
  });

  it("writes a date in words, not ISO — matching the API renderer", () => {
    expect(
      fillStatement(
        kind({
          key: "confirmation_statement_due",
          label: "Confirmation statement due",
          value_kind: "date",
          statement_template: "The organisation's next confirmation statement is due {value}.",
        }),
        null,
        "2026-09-15",
      ),
    ).toBe("The organisation's next confirmation statement is due 15 September 2026.");
  });
});

describe("claimNote", () => {
  it("formats the dates it quotes", () => {
    const base = { status: "confirmed", stale: true, expired: false } as Claim;
    expect(claimNote({ ...base, last_verified: "2025-11-02" } as Claim)).toBe(
      "Last checked 2 Nov 2025, and now past review.",
    );
    expect(
      claimNote({ ...base, stale: true, expired: true, expires_on: "2026-04-30" } as Claim),
    ).toMatch(/^This lapsed on 30 Apr 2026\./);
  });
});

describe("parseClaimValue", () => {
  it("reads a money figure with commas", () => {
    expect(parseClaimValue(kind(), "412,000")).toBe(412000);
  });

  it("keeps text as text", () => {
    expect(parseClaimValue(kind({ value_kind: "text" }), "SCIO")).toBe("SCIO");
  });
});
