"use client";

import { Children, cloneElement, isValidElement } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

export type CiteRenderer = (n: number) => React.ReactNode;

// Mirrors CITATION_RE / MIN_UNPREFIXED_ID in the api's
// app/routers/conversations.py. The model writes [c:<uuid>] markers and the API
// only rewrites them to [n] in its final `done` event, so raw uuids are live in
// every streamed delta. Fullwidth brackets and a missing `c:` are both things
// the GLM/DeepSeek family does in practice. Keep the two in step.
const CITE_MARKER_RE = /[[【]\s*(c:)?\s*([0-9a-fA-F][0-9a-fA-F-]{3,35})\s*[\]】]/g;
// The tail of a marker that straddles two deltas — hide the half that landed
// rather than let it flash as text for a frame.
const PARTIAL_CITE_MARKER_RE = /[[【]\s*(?:c:)?\s*[0-9a-fA-F-]{0,35}$/;

/** Strip citation markers from a partially streamed answer. Until the stream
 * finishes there are no resolved [n] numbers to show — and an unstripped
 * marker renders as a bare uuid mid-sentence. Short bracketed hex without the
 * `c:` prefix is left alone; it is far more often prose than a citation. */
export function stripCiteMarkers(text: string): string {
  return text
    .replace(CITE_MARKER_RE, (raw, prefix, id: string) =>
      prefix || id.length >= 8 ? "" : raw
    )
    .replace(PARTIAL_CITE_MARKER_RE, "");
}

/** Walk rendered markdown children and replace [n] citation markers inside
 * text nodes with cite buttons — recursing so markers survive inside bold,
 * italics, list items and table cells. */
function injectCites(children: React.ReactNode, cite: CiteRenderer): React.ReactNode {
  return Children.map(children, (child) => {
    if (typeof child === "string") {
      const parts = child.split(/(\[\d+\])/g);
      if (parts.length === 1) return child;
      return parts.map((part, i) => {
        const m = /^\[(\d+)\]$/.exec(part);
        return m ? <span key={i}>{cite(Number(m[1]))}</span> : part;
      });
    }
    if (isValidElement<{ children?: React.ReactNode }>(child) && child.props.children) {
      return cloneElement(child, undefined, injectCites(child.props.children, cite));
    }
    return child;
  });
}

/** Assistant-answer markdown in the Hearth voice. `cite` renders an inline
 * [n] marker; when omitted, markers (if any) stay as plain text. */
export function AnswerMarkdown({
  content,
  cite,
}: {
  content: string;
  cite?: CiteRenderer;
}) {
  const wrap = (node: React.ReactNode) => (cite ? injectCites(node, cite) : node);
  return (
    <div className="md-answer text-[14.5px] leading-[1.7] text-ink">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          p: ({ children }) => <p>{wrap(children)}</p>,
          li: ({ children }) => <li>{wrap(children)}</li>,
          h1: ({ children }) => <h3>{wrap(children)}</h3>,
          h2: ({ children }) => <h3>{wrap(children)}</h3>,
          h3: ({ children }) => <h4>{wrap(children)}</h4>,
          h4: ({ children }) => <h4>{wrap(children)}</h4>,
          td: ({ children }) => <td>{wrap(children)}</td>,
          th: ({ children }) => <th>{wrap(children)}</th>,
          a: ({ children, href }) => (
            <a href={href} target="_blank" rel="noreferrer noopener">
              {children}
            </a>
          ),
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
