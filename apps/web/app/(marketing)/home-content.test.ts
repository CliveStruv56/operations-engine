import { describe, expect, it } from "vitest";
import * as HOME from "./home-content";
import { PRODUCT_LANGUAGE } from "@/lib/product-language";

/* Guards on the home page copy. The wording itself is fixed by the
 * publication fact-check; these pin the rules any later edit must keep. */

function allStrings(value: unknown): string[] {
  if (typeof value === "string") return [value];
  if (Array.isArray(value)) return value.flatMap(allStrings);
  if (value && typeof value === "object") return Object.values(value).flatMap(allStrings);
  return [];
}

const text = allStrings(HOME).join("\n");

describe("home page copy", () => {
  it("carries no ledger tags, dates or launch promises", () => {
    expect(text).not.toMatch(/\[(H|D)\d+/);
    expect(text).not.toMatch(/coming soon/i);
    expect(text).not.toMatch(/\b20\d\d\b/);
  });

  it("never mentions pilots or the security page's held link", () => {
    expect(text).not.toMatch(/pilot/i);
    expect(text).not.toContain("/security-and-data");
  });

  it("keeps PowerPoint to slide-deck answers, not funder responses", () => {
    expect(text).not.toMatch(/funder response/i);
  });

  it("uses the core project sentence verbatim (ruling #71)", () => {
    expect(HOME.WORKS_TODAY.cards.map((c) => c.body)).toContain(
      PRODUCT_LANGUAGE.core.everyProject,
    );
  });

  it("labels planned work as not available", () => {
    expect(HOME.BUILT_NEXT.label).toBe("Being built next · not available yet");
    expect(HOME.WORKS_TODAY.label).toBe("Works today");
    expect(HOME.HERO.secondaryCta.href).toBe("#works-today");
  });
});
