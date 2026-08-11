import { describe, expect, it } from "vitest";
import { stripCiteMarkers } from "./markdown";

const UUID = "3174bc60-028e-4df2-82c7-d9b3a4eb1b11";

describe("stripCiteMarkers", () => {
  it("hides a full marker mid-stream", () => {
    expect(stripCiteMarkers(`Leave is 25 days [c:${UUID}].`)).toBe("Leave is 25 days .");
  });

  it("hides a marker the model wrote without the c: prefix", () => {
    // Seen live 11 Aug 2026, together with CJK brackets.
    expect(stripCiteMarkers(`Rate is 3.75% 【${UUID}】.`)).toBe("Rate is 3.75% .");
  });

  it("hides a fabricated prefixed id that is not hex", () => {
    // Found by the local end-to-end run: `[c:s1]` matched nothing, so it
    // reached the reader verbatim. The prefix is the model's own claim that
    // this is a citation.
    for (const fake of ["[c:s1]", "[c:source-1]", "[c:ref]", "【c:s1】"]) {
      expect(stripCiteMarkers(`Need is high ${fake}.`)).toBe("Need is high .");
    }
  });

  it("leaves short bracketed prose alone", () => {
    // Without the prefix there is nothing to distinguish these from writing.
    for (const prose of ["[42]", "[dead]", "[TBC]", "[c: the note below]"]) {
      expect(stripCiteMarkers(`Section ${prose} continues.`)).toBe(
        `Section ${prose} continues.`
      );
    }
  });

  it("hides the half of a marker that straddles two deltas", () => {
    expect(stripCiteMarkers("Leave is 25 days [c:3174bc")).toBe("Leave is 25 days ");
  });
});
