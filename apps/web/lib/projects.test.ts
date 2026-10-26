import { describe, expect, it } from "vitest";
import {
  CORE_KINDS,
  GENERAL_KIND,
  effectiveKind,
  moduleAdds,
  parseProjectKinds,
  projectStatus,
  upgradeTargets,
  type ProjectKinds,
} from "./projects";

const DEVELOPMENT = {
  key: "development",
  label: "Development project",
  description: "A stage-gated housing scheme.",
  home: "room" as const,
  create: "setup" as const,
  upgrades_to: [],
  available: true,
};

const withDevelopment = (available: boolean): ProjectKinds => ({
  kinds: [GENERAL_KIND, { ...DEVELOPMENT, available }],
  addons: [],
});

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

describe("upgradeTargets", () => {
  it("offers a general project the development kind while its module is on", () => {
    expect(upgradeTargets({ kind: "general" }, withDevelopment(true))).toEqual([
      { kind: { ...DEVELOPMENT, available: true }, path: "/app/projects/new" },
    ]);
  });

  it("offers nothing when the target's module is off, or from a development project", () => {
    expect(upgradeTargets({ kind: "general" }, withDevelopment(false))).toEqual([]);
    expect(upgradeTargets({ kind: "development" }, withDevelopment(true))).toEqual([]);
  });
});

describe("projectStatus", () => {
  const base = { stage_current: null, has_plan: false, open_task_count: 0, document_count: 1 };

  it("names the stage of a development project and counts for the rest", () => {
    expect(projectStatus({ ...base, stage_current: "site" }, DEVELOPMENT)).toBe("Site");
    expect(projectStatus({ ...base, has_plan: true, open_task_count: 2 }, GENERAL_KIND)).toBe(
      "2 tasks"
    );
    expect(projectStatus(base, GENERAL_KIND)).toBe("1 doc");
  });
});

describe("moduleAdds", () => {
  it("says what a module adds, or nothing", () => {
    expect(
      moduleAdds({ flag: "grants", label: "Grant funding", kinds: [], addons: ["Grant applications"] })
    ).toBe("Adds a Grant applications tab on every project");
    expect(moduleAdds({ flag: "web_search", label: "Web search", kinds: [], addons: [] })).toBeNull();
  });
});
