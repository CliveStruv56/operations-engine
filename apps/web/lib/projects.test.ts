import { describe, expect, it } from "vitest";
import { CORE_KINDS, effectiveKind, parseProjectKinds } from "./projects";

describe("parseProjectKinds", () => {
  it("falls back to the core kind on anything that is not a kinds list", () => {
    // The e2e mocks answer every unknown API path with [] — that must not
    // leave the picker or the sidebar without a kind.
    expect(parseProjectKinds([])).toEqual(CORE_KINDS);
    expect(parseProjectKinds(null)).toEqual(CORE_KINDS);
    expect(parseProjectKinds({ kinds: [] })).toEqual(CORE_KINDS);
  });
});

describe("effectiveKind", () => {
  it("uses the general kind when the project's own is unknown or switched off", () => {
    expect(effectiveKind({ kind: "development", kind_available: true }, CORE_KINDS).key).toBe(
      "general"
    );
    expect(effectiveKind({ kind: "general", kind_available: false }, CORE_KINDS).key).toBe(
      "general"
    );
  });
});
