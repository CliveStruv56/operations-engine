import { describe, expect, it } from "vitest";
import { fillStatement, parseClaimValue, type ClaimKind } from "./claims";

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
});

describe("parseClaimValue", () => {
  it("reads a money figure with commas", () => {
    expect(parseClaimValue(kind(), "412,000")).toBe(412000);
  });

  it("keeps text as text", () => {
    expect(parseClaimValue(kind({ value_kind: "text" }), "SCIO")).toBe("SCIO");
  });
});
