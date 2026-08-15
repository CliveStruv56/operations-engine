import { describe, expect, it } from "vitest";
import { buildSuggestions, type DocMeta } from "./hero";
import type { Project } from "./workspace";

const doc = (over: Partial<DocMeta> = {}): DocMeta => ({
  id: crypto.randomUUID(),
  title: "Employee handbook 2026",
  project_id: null,
  conversation_id: null,
  is_primary: false,
  status: "ready",
  error: null,
  summary: null,
  ...over,
});

const project = (over: Partial<Project> = {}): Project =>
  ({
    id: "p1",
    name: "Riverside site",
    is_development: false,
    has_plan: false,
    ...over,
  }) as Project;

describe("buildSuggestions", () => {
  it("asks about the documents the vault actually holds", () => {
    const docs = [
      doc({ title: "Employee handbook 2026", is_primary: true }),
      doc({ title: "Public liability policy" }),
    ];
    const texts = buildSuggestions(null, docs).map((s) => s.text);
    expect(texts).toContain("Summarise the key points of Employee handbook 2026");
    expect(texts.some((t) => t.includes("Public liability policy"))).toBe(true);
    expect(texts).toContain("What are the key dates and actions across our documents?");
    expect(texts).toHaveLength(4);
  });

  it("falls back to canned openers only while the vault is empty", () => {
    const texts = buildSuggestions(null, []).map((s) => s.text);
    expect(texts).toContain("Summarise our health and safety procedures");
    expect(texts).toHaveLength(4);
  });

  it("skips documents that are not indexed yet", () => {
    const texts = buildSuggestions(null, [doc({ status: "parsing" })]).map((s) => s.text);
    expect(texts.some((t) => t.includes("Employee handbook"))).toBe(false);
  });

  it("keeps the drafting chips for an active project", () => {
    const s = buildSuggestions(project(), [doc({ project_id: "p1" })]);
    expect(s.some((x) => x.mode === "report")).toBe(true);
    expect(s.map((x) => x.text)).toContain("Summarise the key points of Employee handbook 2026");
  });
});
