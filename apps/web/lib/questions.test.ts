import { describe, expect, it } from "vitest";
import {
  countLabel,
  countTone,
  staleNote,
  type Answer,
  type QuestionSet,
} from "./questions";

const answer = (over: Partial<Answer> = {}): Answer => ({
  question_id: "q1",
  question: "What is the project?",
  guidance: "",
  text: "A community-led housing scheme.",
  limit: 200,
  limit_kind: "characters",
  length: 30,
  over_by: 0,
  to_confirm: 0,
  citations: [],
  ...over,
});

const set = (over: Partial<QuestionSet> = {}): QuestionSet => ({
  key: "fund_eoi",
  name: "Expression of interest",
  funder: "A Trust",
  stage: "eoi",
  source_url: null,
  status: "open",
  questions: [],
  last_verified: "2026-05-01",
  next_review: "2026-11-01",
  stale: false,
  source: "platform",
  ...over,
});

describe("countLabel", () => {
  it("shows the funder's limit alongside the count", () => {
    expect(countLabel(answer({ length: 1240, limit: 2000 }))).toBe("1,240 / 2,000 characters");
  });

  it("uses the question's own units", () => {
    expect(countLabel(answer({ length: 400, limit: 500, limit_kind: "words" }))).toBe(
      "400 / 500 words"
    );
  });

  it("drops the limit when the question has none", () => {
    expect(countLabel(answer({ length: 30, limit: null }))).toBe("30 characters");
  });
});

describe("countTone", () => {
  // `grounded` green is reserved for trust states, so a comfortable answer
  // gets no colour — the counter only speaks up when it has something to say.
  it("stays quiet well under the limit", () => {
    expect(countTone(answer({ length: 100, limit: 1000 }))).toContain("ink-faint");
  });

  it("warns as the limit approaches", () => {
    expect(countTone(answer({ length: 900, limit: 1000 }))).toContain("warn");
  });

  it("goes danger once over", () => {
    expect(countTone(answer({ length: 1100, limit: 1000, over_by: 100 }))).toContain("danger");
  });

  it("never warns about a question with no limit", () => {
    expect(countTone(answer({ length: 99999, limit: null }))).toContain("ink-faint");
  });
});

describe("staleNote", () => {
  it("says nothing about a verified, in-date form", () => {
    expect(staleNote(set())).toBeNull();
  });

  it("flags a form past its review date", () => {
    expect(staleNote(set({ stale: true }))).toContain("past review");
  });

  it("says an in-date unverified form is unverified, not overdue", () => {
    const note = staleNote(set({ status: "unverified" }));
    expect(note).toContain("have not been verified");
    expect(note).not.toContain("past review");
  });

  it("says both when a form is unverified and overdue", () => {
    const note = staleNote(set({ status: "unverified", stale: true }));
    expect(note).toContain("never been verified");
    expect(note).toContain("past review");
  });

  it("says a tenant's own copy is not one we have checked", () => {
    // The distinction matters: our catalogue is curated, a tenant's own copy
    // is whatever they typed, and the UI must not present the two alike.
    expect(staleNote(set({ source: "tenant" }))).toContain("your workspace's own copy");
  });

  it("handles nothing chosen yet", () => {
    expect(staleNote(null)).toBeNull();
  });
});
