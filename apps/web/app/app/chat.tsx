"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { api, apiStream } from "@/lib/api";
import { openPresigned } from "@/lib/groundwork";
import { PulsingDots, Spinner } from "@/components/activity";
import {
  ArrowUpIcon,
  CopyIcon,
  DocIcon,
  GlobeIcon,
  StopIcon,
} from "@/components/icons";
import { AnswerMarkdown } from "@/components/markdown";
import EmptyHero, { type DocMeta, type Suggestion } from "./hero";
import ShareBar from "./share-bar";
import { useWorkspace } from "./workspace";

type Citation = {
  n: number;
  chunk_id: string;
  document_id: string;
  title: string;
  page_start: number | null;
  page_end: number | null;
  snippet: string;
  url?: string | null;
  source_type?: string;
};

type Message = {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  citations: Citation[];
  model: string | null;
  cost_usd: number | null;
};

const MODES: { key: string; label: string }[] = [
  { key: "chat", label: "Chat" },
  { key: "analyse", label: "Analyse" },
  { key: "report", label: "Report" },
  { key: "financial", label: "Financial" },
  { key: "slides", label: "Slide deck" },
  { key: "research", label: "Research" },
];

// Matches the "## Slide N — title" shape the slides task prompt enforces.
function isSlideDeck(content: string): boolean {
  return /^##\s*slide\s*\d/im.test(content);
}

function domainOf(url: string | null | undefined): string | null {
  if (!url) return null;
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return null;
  }
}

/** Cite renderer for AnswerMarkdown: [n] markers that match a real citation
 * become buttons; anything else stays literal text. */
function citeButton(
  citations: Citation[],
  onCite: (n: number) => void
): (n: number) => React.ReactNode {
  const nums = new Set(citations.map((c) => c.n));
  // Returns nodes, not a component — the display-name rule misfires here.
  // eslint-disable-next-line react/display-name
  return (n) =>
    nums.has(n) ? (
      <button
        onClick={() => onCite(n)}
        className="mx-0.5 inline-flex h-[17px] min-w-[17px] items-center justify-center rounded-[5px] bg-accent-tint px-1 align-[2px] text-[10.5px] font-extrabold text-accent-deep hover:bg-accent hover:text-white"
        aria-label={`Source ${n}`}
      >
        {n}
      </button>
    ) : (
      `[${n}]`
    );
}

function SourceCard({ c }: { c: Citation }) {
  const web = c.source_type === "web";
  return (
    <div id={`src-${c.chunk_id}`} className="rounded-[11px] border border-edge bg-canvas p-3">
      <div className="flex items-center gap-2 text-xs font-bold">
        <span className="mr-0.5 inline-flex h-[17px] min-w-[17px] items-center justify-center rounded-[5px] bg-accent-tint px-1 text-[10.5px] font-extrabold text-accent-deep">
          {c.n}
        </span>
        {web ? (
          <GlobeIcon className="h-3 w-3 text-accent-deep" />
        ) : (
          <DocIcon className="h-3 w-3 text-accent-deep" />
        )}
        <span className="min-w-0 truncate">{c.title}</span>
        <em className="ml-auto shrink-0 text-[11px] font-semibold not-italic text-faint">
          {web
            ? domainOf(c.url)
            : c.page_start != null
              ? `p. ${c.page_start}${
                  c.page_end != null && c.page_end !== c.page_start ? `–${c.page_end}` : ""
                }`
              : ""}
        </em>
      </div>
      <p className="mt-1.5 line-clamp-4 text-[11.5px] leading-relaxed text-subtle italic">
        &ldquo;{c.snippet}&rdquo;
      </p>
      {web && c.url && (
        <a
          href={c.url}
          target="_blank"
          rel="noreferrer"
          className="mt-1.5 block truncate text-[11px] font-bold text-accent-deep hover:underline"
        >
          Open source ↗
        </a>
      )}
    </div>
  );
}

function AssistantMessage({
  m,
  scope,
  onExport,
  exporting,
  readOnly,
}: {
  m: Message;
  scope: string | undefined;
  onExport: () => void;
  exporting: boolean;
  readOnly: boolean;
}) {
  const [showAllSources, setShowAllSources] = useState(false);
  const [copied, setCopied] = useState(false);
  const cites = m.citations ?? [];
  const docCount = new Set(
    cites.filter((c) => c.source_type !== "web").map((c) => c.document_id)
  ).size;
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
        <span className="mb-3 inline-flex items-center gap-2 rounded-full bg-grounded-tint px-[13px] py-1.5 text-[11.5px] font-bold text-grounded">
          <i className="h-1.5 w-1.5 rounded-full bg-grounded" />
          {docCount > 0 && `Grounded in ${docCount} of your documents`}
          {docCount > 0 && webCount > 0 && " · "}
          {webCount > 0 && `${webCount} web source${webCount === 1 ? "" : "s"}`}
        </span>
      )}
      <AnswerMarkdown
        content={m.content}
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
          {copied ? <span className="text-[10px] font-bold">✓</span> : <CopyIcon className="h-3.5 w-3.5" />}
        </button>
        {cites.length > 3 && (
          <button
            onClick={() => setShowAllSources((v) => !v)}
            className="rounded-full bg-accent-tint px-[13px] py-1.5 text-xs font-bold text-accent-deep hover:bg-accent hover:text-white"
          >
            {showAllSources ? "Show fewer sources" : `Show all ${cites.length} sources`}
          </button>
        )}
        {!readOnly && isSlideDeck(m.content) && !m.id.startsWith("local-") && (
          <button
            onClick={onExport}
            disabled={exporting}
            className="rounded-full bg-accent-tint px-[13px] py-1.5 text-xs font-bold text-accent-deep hover:bg-accent hover:text-white disabled:opacity-50"
          >
            {exporting ? "Building deck…" : "Download .pptx"}
          </button>
        )}
        {m.model && (
          <span className="ml-auto text-[11px] font-semibold text-faint">
            {m.model}
            {scope === "project" && " · from project documents"}
            {scope === "vault" && " · from the whole vault"}
          </span>
        )}
      </div>
    </article>
  );
}

export default function ChatPanel({
  activeProjectId,
  activeConversationId,
}: {
  activeProjectId: string | null;
  activeConversationId: string | null;
}) {
  const router = useRouter();
  const ws = useWorkspace();
  const tenantId = ws.tenant!.id;
  const activeProject = ws.projects.find((p) => p.id === activeProjectId) ?? null;
  const activeConv = ws.conversations.find((c) => c.id === activeConversationId) ?? null;
  const [scopes, setScopes] = useState<Record<string, string>>({});
  const [messages, setMessages] = useState<Message[]>([]);
  const [draft, setDraft] = useState("");
  const [createdHereIds, setCreatedHereIds] = useState<string[]>([]);
  const [streamText, setStreamText] = useState<string | null>(null);
  const [softCap, setSoftCap] = useState(false);
  const [useVault, setUseVault] = useState(true);
  // Task mode is sticky per conversation ("new" = the not-yet-created one).
  const [modes, setModes] = useState<Record<string, string>>({});
  const modeKey = activeConversationId ?? "new";
  const mode = modes[modeKey] ?? "chat";
  const webSearchEnabled = ws.tenant!.features?.web_search === true;
  const devProjectsEnabled = ws.tenant!.features?.projects === true;
  const [docs, setDocs] = useState<DocMeta[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [exportingId, setExportingId] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const abortRef = useRef<AbortController | null>(null);
  // Set when this panel just created the conversation itself: the URL update
  // that follows must not refetch (and clobber) the in-flight local state.
  const justCreatedRef = useRef<string | null>(null);
  // Ownership has to be established positively. Treating "absent from
  // ws.conversations" as writable fails open: the list is also empty when its
  // fetch failed, which would put a live composer on a teammate's shared chat
  // and silently discard whatever was typed into it. createdHereIds keeps the
  // ids this panel made — ws.conversations lags a create by one refresh, and
  // writability must not blink off under a reply that is still streaming.
  const createdHere = activeConversationId !== null && createdHereIds.includes(activeConversationId);
  const unknownConversation = activeConversationId !== null && !createdHere && activeConv === null;
  const readOnly = (activeConv !== null && !activeConv.is_mine) || unknownConversation;

  useEffect(() => {
    if (!activeConversationId) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setMessages([]);
      return;
    }
    if (justCreatedRef.current === activeConversationId) {
      justCreatedRef.current = null;
      return;
    }
    api<Message[]>(`/conversations/${activeConversationId}/messages`, {}, tenantId)
      .then(setMessages)
      .catch((e) => setError(String(e)));
  }, [activeConversationId, tenantId]);

  // Document metadata for the hero (context chip + title-derived suggestions)
  // — best-effort, the hero renders without it too.
  useEffect(() => {
    api<DocMeta[]>("/documents", {}, tenantId)
      .then(setDocs)
      .catch(() => setDocs(null));
  }, [tenantId]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight });
  }, [messages, streamText]);

  function convHref(convId: string) {
    const q = new URLSearchParams();
    if (activeProjectId) q.set("project", activeProjectId);
    q.set("c", convId);
    return `/app?${q.toString()}`;
  }

  async function exportSlides(messageId: string) {
    if (!activeConversationId) return;
    setExportingId(messageId);
    setError(null);
    try {
      const out = await api<{ download_url: string }>(
        `/conversations/${activeConversationId}/messages/${messageId}/slides`,
        { method: "POST" },
        tenantId
      );
      openPresigned(out.download_url);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setExportingId(null);
    }
  }

  function stopStreaming() {
    abortRef.current?.abort();
  }

  async function send(e?: React.FormEvent) {
    e?.preventDefault();
    const content = draft.trim();
    if (!content || streamText !== null) return;
    setError(null);
    setDraft("");
    if (inputRef.current) inputRef.current.style.height = "auto";

    let convId = activeConversationId;
    try {
      if (!convId) {
        const created = await api<{ id: string }>(
          "/conversations",
          {
            method: "POST",
            body: JSON.stringify({
              title: content.slice(0, 80),
              project_id: activeProjectId,
            }),
          },
          tenantId
        );
        convId = created.id;
        justCreatedRef.current = convId;
        setCreatedHereIds((ids) => [...ids, created.id]);
        setModes((s) => ({ ...s, [created.id]: s["new"] ?? "chat" }));
        router.replace(convHref(convId));
        ws.refreshConversations();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      return;
    }

    setMessages((m) => [
      ...m,
      {
        id: `local-${Date.now()}`,
        role: "user",
        content,
        citations: [],
        model: null,
        cost_usd: null,
      },
    ]);
    setStreamText("");
    const ctrl = new AbortController();
    abortRef.current = ctrl;

    await apiStream(
      `/conversations/${convId}/messages`,
      { content, use_vault: useVault, task_kind: mode },
      tenantId,
      {
        onDelta: (delta) => setStreamText((t) => (t ?? "") + delta),
        onDone: (message) => {
          setSoftCap(Boolean(message.soft_cap));
          setStreamText(null);
          const done = message as unknown as Message & { scope_used?: string | null };
          setMessages((m) => [...m, done]);
          if (done.scope_used) setScopes((s) => ({ ...s, [done.id]: done.scope_used! }));
          ws.refreshConversations();
        },
        onError: (_code, msg) => {
          setStreamText(null);
          setError(msg);
        },
        onAbort: () => {
          // The server may still have persisted the reply — converge on its state.
          setStreamText(null);
          if (convId) {
            api<Message[]>(`/conversations/${convId}/messages`, {}, tenantId)
              .then(setMessages)
              .catch(() => {});
          }
        },
      },
      ctrl.signal
    );
    abortRef.current = null;
  }

  function pickSuggestion(s: Suggestion) {
    setDraft(s.text);
    if (s.mode) setModes((st) => ({ ...st, [modeKey]: s.mode! }));
    inputRef.current?.focus();
  }

  const empty = messages.length === 0 && streamText === null;
  const availableModes = MODES.filter((m) => m.key !== "research" || webSearchEnabled);

  return (
    <section className="flex min-h-0 flex-1 flex-col bg-canvas">
      {/* The empty-state hero carries the project context; the banner only
          needs to keep the scope visible once a conversation is underway. */}
      {activeProject && !empty && (
        <p className="border-b border-edge bg-sidebar px-6 py-1.5 text-xs font-bold text-subtle">
          Project: {activeProject.name} — answers prefer this project&apos;s documents
        </p>
      )}
      {activeConv?.is_mine && !empty && <ShareBar conversation={activeConv} onError={setError} />}
      {softCap && (
        <p className="border-b border-edge bg-warn-soft px-6 py-2 text-sm font-semibold text-warn">
          This workspace has used its monthly budget — replies use the economy model until it
          resets.
        </p>
      )}

      <div ref={scrollRef} className="min-h-0 flex-1 overflow-y-auto px-4 py-5 sm:px-6">
        <div className="mx-auto flex min-h-full w-full max-w-[720px] flex-col">
          {empty ? (
            <EmptyHero
              activeProject={activeProject}
              docs={docs}
              devProjectsEnabled={devProjectsEnabled}
              onPick={pickSuggestion}
            />
          ) : (
            <div className="space-y-4">
              {messages.map((m) =>
                m.role === "user" ? (
                  <div key={m.id} className="flex justify-end">
                    <div className="max-w-[85%] rounded-2xl rounded-br-[4px] bg-accent-tint px-[18px] py-[13px] text-[14.5px] font-semibold whitespace-pre-wrap sm:max-w-[420px]">
                      {m.content}
                    </div>
                  </div>
                ) : (
                  <AssistantMessage
                    key={m.id}
                    m={m}
                    scope={scopes[m.id]}
                    onExport={() => exportSlides(m.id)}
                    exporting={exportingId === m.id}
                    readOnly={readOnly}
                  />
                )
              )}
              {streamText !== null && (
                <article className="max-w-full rounded-2xl border border-edge bg-card px-5 py-4 shadow-card sm:px-6 sm:py-5">
                  {streamText ? (
                    <>
                      <AnswerMarkdown content={streamText} />
                      <PulsingDots className="mt-1.5" />
                    </>
                  ) : (
                    <PulsingDots className="py-1" />
                  )}
                </article>
              )}
            </div>
          )}
        </div>
      </div>

      {error && (
        <p
          role="alert"
          className="border-t border-edge bg-danger-soft px-6 py-2 text-sm font-semibold text-danger"
        >
          {error}
        </p>
      )}

      {readOnly ? (
        <div className="px-4 pt-2 pb-4 sm:px-6 sm:pb-6">
          <p className="mx-auto w-full max-w-[720px] rounded-[18px] border border-edge bg-sidebar px-5 py-3.5 text-center text-[13px] font-semibold text-subtle">
            {unknownConversation
              ? ws.conversationsLoaded
                ? "This chat isn't one of yours — read only"
                : "Couldn't check who owns this chat — refresh to reply"
              : `Shared by ${activeConv?.owner_email ?? "a teammate"} — read only`}
          </p>
        </div>
      ) : (
      <div className="px-4 pt-2 pb-4 sm:px-6 sm:pb-6">
        <form
          onSubmit={send}
          className="mx-auto w-full max-w-[720px] rounded-[18px] border border-edge-strong bg-card p-3 shadow-hearth"
        >
          <div
            role="radiogroup"
            aria-label="Mode"
            className="flex gap-1.5 overflow-x-auto px-0.5 pb-2.5 [scrollbar-width:none]"
          >
            {availableModes.map((m) => (
              <button
                key={m.key}
                type="button"
                role="radio"
                aria-checked={mode === m.key}
                onClick={() => setModes((s) => ({ ...s, [modeKey]: m.key }))}
                className={`shrink-0 rounded-full px-[13px] py-1.5 text-xs font-bold whitespace-nowrap transition ${
                  mode === m.key
                    ? "bg-accent text-white"
                    : "text-subtle hover:bg-sidebar"
                }`}
              >
                {m.label}
              </button>
            ))}
          </div>
          <div className="flex items-end gap-2.5">
            <textarea
              ref={inputRef}
              rows={1}
              value={draft}
              onChange={(e) => {
                setDraft(e.target.value);
                e.target.style.height = "auto";
                e.target.style.height = `${Math.min(e.target.scrollHeight, 200)}px`;
              }}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
                  e.preventDefault();
                  send();
                }
              }}
              placeholder={
                mode === "research"
                  ? "Research a question across the web…"
                  : useVault
                    ? "Ask about your documents — or draft something new…"
                    : "Ask anything…"
              }
              className="max-h-[200px] w-full resize-none bg-transparent px-0.5 py-2 text-base leading-normal text-ink placeholder:text-faint focus:outline-none sm:text-[15px]"
            />
            {streamText !== null ? (
              <button
                type="button"
                onClick={stopStreaming}
                className="inline-flex flex-none items-center gap-2 rounded-xl bg-ink px-[18px] py-[9px] text-[13.5px] font-bold text-white hover:opacity-90"
              >
                <StopIcon className="h-3.5 w-3.5" />
                Stop
              </button>
            ) : (
              <button
                type="submit"
                disabled={!draft.trim()}
                className="inline-flex flex-none items-center gap-2 rounded-xl bg-accent px-[18px] py-[9px] text-[13.5px] font-bold text-white transition hover:bg-accent-deep disabled:cursor-not-allowed disabled:bg-edge disabled:text-faint"
              >
                Send
                <ArrowUpIcon className="h-3.5 w-3.5" />
              </button>
            )}
          </div>
          <div className="mt-2.5 flex items-center gap-2.5 border-t border-edge px-1 pt-[11px]">
            <button
              type="button"
              role="switch"
              aria-checked={useVault}
              aria-label="Vault"
              onClick={() => setUseVault((v) => !v)}
              className={`relative h-[18px] w-8 flex-none rounded-full transition after:absolute after:top-0.5 after:left-0.5 after:h-3.5 after:w-3.5 after:rounded-full after:bg-white after:transition after:content-[''] ${
                useVault ? "bg-grounded after:translate-x-[14px]" : "bg-edge-strong"
              }`}
            />
            <span className="text-xs font-semibold text-subtle">
              {useVault
                ? "Vault on — answers cite your documents"
                : "Vault off — answers come from the model alone"}
            </span>
            <span className="ml-auto hidden text-[11.5px] font-semibold text-faint sm:block">
              <kbd className="rounded-[5px] border border-edge bg-sidebar px-1.5 py-0.5 text-[10.5px] font-bold">
                ↵
              </kbd>{" "}
              Send ·{" "}
              <kbd className="rounded-[5px] border border-edge bg-sidebar px-1.5 py-0.5 text-[10.5px] font-bold">
                ⇧↵
              </kbd>{" "}
              New line
            </span>
            {streamText !== null && <Spinner className="ml-2 text-accent sm:ml-0" />}
          </div>
        </form>
      </div>
      )}
    </section>
  );
}
