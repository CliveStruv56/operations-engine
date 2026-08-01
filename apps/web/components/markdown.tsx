"use client";

import { Children, cloneElement, isValidElement } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

export type CiteRenderer = (n: number) => React.ReactNode;

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
