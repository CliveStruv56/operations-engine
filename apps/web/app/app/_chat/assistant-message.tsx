import { memo, useState } from "react";
import { CopyIcon } from "@/components/icons";
import { AnswerMarkdown, stripCiteMarkers } from "@/components/markdown";
import { SourceCard, citeButton } from "./sources";
import type { Message } from "./types";

// Matches the "## Slide N — title" shape the slides task prompt enforces.
function isSlideDeck(content: string): boolean {
  return /^##\s*slide\s*\d/im.test(content);
}

/** Wrapped in `memo` below — see the note there before changing these props. */
function AssistantMessageInner({
  m,
  scope,
  onExport,
  exporting,
  onSaveToVault,
  saving,
  onPdf,
  pdfBusy,
  coverage,
  onAddDocument,
  onAssertFact,
  readOnly,
}: {
  m: Message;
  scope: string | undefined;
  /** Takes the message id rather than closing over it, so the parent can pass
   *  one stable callback instead of a fresh arrow per render (which would
   *  defeat the memo). */
  onExport: (id: string) => void;
  exporting: boolean;
  onSaveToVault: (id: string) => void;
  saving: boolean;
  onPdf: (id: string) => void;
  pdfBusy: boolean;
  /** "none" when the vault was asked and could not back the answer. */
  coverage: string | undefined;
  onAddDocument: () => void;
  onAssertFact: (id: string) => void;
  readOnly: boolean;
}) {
  const [showAllSources, setShowAllSources] = useState(false);
  const [copied, setCopied] = useState(false);
  const cites = m.citations ?? [];
  const docCount = new Set(cites.filter((c) => c.source_type !== "web").map((c) => c.document_id))
    .size;
  const webCount = new Set(cites.filter((c) => c.source_type === "web").map((c) => c.url)).size;
  const visible = showAllSources ? cites : cites.slice(0, 3);

  function copy() {
    navigator.clipboard?.writeText(m.content).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    });
  }

  return (
    <article className="max-w-full rounded-2xl border border-edge bg-card px-5 py-4 shadow-card sm:px-6 sm:py-5">
      {cites.length > 0 && (
        <span className="mb-3 inline-flex items-center gap-2 rounded-full bg-grounded-tint px-[13px] py-1.5 text-xs font-bold text-grounded">
          <i className="h-1.5 w-1.5 rounded-full bg-grounded" />
          {docCount > 0 && `Grounded in ${docCount} of your documents`}
          {docCount > 0 && webCount > 0 && " · "}
          {webCount > 0 && `${webCount} web source${webCount === 1 ? "" : "s"}`}
        </span>
      )}
      {/* Stored answers arrive already resolved — _resolve_citations turns
          [c:<id>] into [n] before the row is written. Strip anyway: rows
          written before a marker shape was recognised (the fullwidth 【…】 and
          prefix-less forms both post-date August's conversations) still carry
          raw ids, and no backend fix rewrites what is already on disk. Only
          markers are removed, so the [n] the cite buttons need survive. */}
      <AnswerMarkdown
        content={stripCiteMarkers(m.content)}
        cite={cites.length > 0 ? citeButton(cites, () => setShowAllSources(true)) : undefined}
      />
      {cites.length > 0 && (
        <div className="mt-3 grid grid-cols-1 gap-2.5 sm:grid-cols-2 lg:grid-cols-3">
          {visible.map((c) => (
            <SourceCard key={c.chunk_id} c={c} />
          ))}
        </div>
      )}
      <div className="mt-3.5 flex flex-wrap items-center gap-2 border-t border-edge pt-3">
        <button
          onClick={copy}
          aria-label="Copy answer"
          title="Copy answer"
          className="grid h-7 w-7 place-items-center rounded-lg border border-edge text-subtle hover:bg-sidebar hover:text-ink"
        >
          {copied ? (
            <span className="text-[10px] font-bold">✓</span>
          ) : (
            <CopyIcon className="h-3.5 w-3.5" />
          )}
        </button>
        {cites.length > 3 && (
          <button
            onClick={() => setShowAllSources((v) => !v)}
            className="rounded-full bg-accent-tint px-[13px] py-1.5 text-xs font-bold text-electric-blue hover:bg-deep-violet hover:text-white"
          >
            {showAllSources ? "Show fewer sources" : `Show all ${cites.length} sources`}
          </button>
        )}
        {!readOnly && isSlideDeck(m.content) && !m.id.startsWith("local-") && (
          <button
            onClick={() => onExport(m.id)}
            disabled={exporting}
            className="rounded-full bg-accent-tint px-[13px] py-1.5 text-xs font-bold text-electric-blue hover:bg-deep-violet hover:text-white disabled:opacity-50"
          >
            {exporting ? "Building deck…" : "Download .pptx"}
          </button>
        )}
        {!readOnly && !m.id.startsWith("local-") && (
          <>
            <button
              onClick={() => onPdf(m.id)}
              disabled={pdfBusy}
              className="rounded-full bg-accent-tint px-[13px] py-1.5 text-xs font-bold text-electric-blue hover:bg-deep-violet hover:text-white disabled:opacity-50"
            >
              {pdfBusy ? "Building PDF…" : "Download as PDF"}
            </button>
            <button
              onClick={() => onSaveToVault(m.id)}
              disabled={saving}
              className="rounded-full bg-accent-tint px-[13px] py-1.5 text-xs font-bold text-electric-blue hover:bg-deep-violet hover:text-white disabled:opacity-50"
            >
              {saving ? "Saving…" : "Save to documents"}
            </button>
          </>
        )}
        {m.model && (
          <span className="ml-auto text-xs font-semibold text-faint">
            {scope === "project" && "Drafted from project documents · "}
            {scope === "vault" && "Drafted from all your documents · "}
            {m.model}
          </span>
        )}
      </div>
      {coverage === "none" && !readOnly && (
        <p className="mt-2.5 flex flex-wrap items-center gap-2.5 rounded-card bg-sidebar px-3 py-2 text-xs text-ink-muted">
          <span>Your documents could not back this answer.</span>
          <button
            onClick={onAddDocument}
            className="font-medium text-electric-blue underline hover:text-ink"
          >
            Add a document
          </button>
          <button
            onClick={() => onAssertFact(m.id)}
            className="font-medium text-electric-blue underline hover:text-ink"
          >
            Assert it as a fact
          </button>
        </p>
      )}
    </article>
  );
}

/** Settled messages never change, but the panel re-renders on every streamed
 *  frame — and each of these runs a full `ReactMarkdown` parse plus the
 *  recursive `injectCites` walk. Unmemoized, a ten-message conversation
 *  re-parsed all ten answers on every delta of the eleventh, which is what
 *  made long replies stutter. Keep every prop here primitive or referentially
 *  stable or this silently stops working. */
const AssistantMessage = memo(AssistantMessageInner);

export default AssistantMessage;
