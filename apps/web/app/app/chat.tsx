"use client";

import { memo, useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { api, apiStream } from "@/lib/api";
import { openPresigned } from "@/lib/groundwork";
import { ACCEPT, uploadMime } from "@/lib/uploads";
import { PulsingDots, Spinner } from "@/components/activity";
import {
  ArrowUpIcon,
  ClipIcon,
  CopyIcon,
  DocIcon,
  GlobeIcon,
  StopIcon,
} from "@/components/icons";
import { AnswerMarkdown, stripCiteMarkers } from "@/components/markdown";
import EmptyHero, { type DocMeta, type Suggestion } from "./hero";
import ProjectPlanPanel from "./project-plan";
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

/** Wrapped in `memo` below — see the note there before changing these props. */
function AssistantMessageInner({
  m,
  scope,
  onExport,
  exporting,
  readOnly,
}: {
  m: Message;
  scope: string | undefined;
  /** Takes the message id rather than closing over it, so the parent can pass
   *  one stable callback instead of a fresh arrow per render (which would
   *  defeat the memo). */
  onExport: (id: string) => void;
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
            onClick={() => onExport(m.id)}
            disabled={exporting}
            className="rounded-full bg-accent-tint px-[13px] py-1.5 text-xs font-bold text-accent-deep hover:bg-accent hover:text-white disabled:opacity-50"
          >
            {exporting ? "Building deck…" : "Download .pptx"}
          </button>
        )}
        {m.model && (
          <span className="ml-auto text-[11px] font-semibold text-faint">
            {scope === "project" && "Drafted from project documents · "}
            {scope === "vault" && "Drafted from your whole vault · "}
            {m.model}
          </span>
        )}
      </div>
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
  const [uploadingCount, setUploadingCount] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [exportingId, setExportingId] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const abortRef = useRef<AbortController | null>(null);
  // Set when this panel just created the conversation itself: the URL update
  // that follows must not refetch (and clobber) the in-flight local state.
  const justCreatedRef = useRef<string | null>(null);
  // Streamed deltas are coalesced and applied once per animation frame rather
  // than once per token. A token-per-setState re-parsed the whole accumulated
  // answer through ReactMarkdown every time — quadratic work over a reply,
  // which made the stream *look* slower than it arrived. A frame is the
  // fastest cadence a display can show anyway, so nothing is lost, and the
  // scroll effect below drops to frame rate with it.
  const pendingRef = useRef("");
  const frameRef = useRef<number | null>(null);

  const flushDeltas = useCallback(() => {
    frameRef.current = null;
    const pending = pendingRef.current;
    if (!pending) return;
    pendingRef.current = "";
    setStreamText((t) => (t ?? "") + pending);
  }, []);

  const pushDelta = useCallback(
    (delta: string) => {
      pendingRef.current += delta;
      frameRef.current ??= requestAnimationFrame(flushDeltas);
    },
    [flushDeltas]
  );

  // Drop anything buffered without applying it. Every stream ending clears
  // streamText, so a queued frame would otherwise fire afterwards and revive
  // the bubble with a stray fragment of the reply that just finished.
  const discardDeltas = useCallback(() => {
    if (frameRef.current !== null) cancelAnimationFrame(frameRef.current);
    frameRef.current = null;
    pendingRef.current = "";
  }, []);

  useEffect(() => discardDeltas, [discardDeltas]);

  /** Workspace URL, with or without an open conversation. Omitting `convId`
   *  is what returns someone to a usable, empty composer. Declared above the
   *  effects that call it — as a `const` it is not hoisted the way the plain
   *  function it replaced was, and a reference from an effect above this line
   *  throws on first render. */
  const convHref = useCallback(
    (convId?: string) => {
      const q = new URLSearchParams();
      if (activeProjectId) q.set("project", activeProjectId);
      if (convId) q.set("c", convId);
      const s = q.toString();
      return s ? `/app?${s}` : "/app";
    },
    [activeProjectId]
  );

  // Ownership has to be established positively. Treating "absent from
  // ws.conversations" as writable fails open: the list is also empty when its
  // fetch failed, which would put a live composer on a teammate's shared chat
  // and silently discard whatever was typed into it. createdHereIds keeps the
  // ids this panel made — ws.conversations lags a create by one refresh, and
  // writability must not blink off under a reply that is still streaming.
  const createdHere = activeConversationId !== null && createdHereIds.includes(activeConversationId);
  const unknownConversation = activeConversationId !== null && !createdHere && activeConv === null;
  // Absent from a list that *loaded successfully* means the conversation is
  // gone — deleted here, or in another tab. Note the distinction from
  // `unknownConversation` above, which is also true when the list failed to
  // load and we genuinely know nothing; that case must keep failing closed.
  const goneConversation = unknownConversation && ws.conversationsLoaded;
  // A conversation that is gone counts as no conversation at all: the composer
  // works, and the next message opens a fresh chat.
  //
  // Deliberately *not* driven by the URL. Clearing `?c=` is attempted below,
  // but when that navigation does not land the panel used to sit forever on
  // "opening a new one…" — the redirect was the only thing standing between
  // the user and a usable screen. Recovery now happens in render and the URL
  // is merely tidied after it.
  const conversationId = goneConversation ? null : activeConversationId;
  const readOnly =
    (activeConv !== null && !activeConv.is_mine) || (unknownConversation && !goneConversation);

  // Drop a dead conversation out of the URL instead of stranding the composer
  // on it. Deleting the open chat used to leave `?c=<deleted-id>` in the
  // address, and the read-only guard then reported it as somebody else's chat
  // — a dead end with no way back to a usable composer, reachable by refresh,
  // back button, bookmark or a second tab, not just by deleting.
  useEffect(() => {
    if (goneConversation) router.replace(convHref());
  }, [goneConversation, router, convHref]);

  useEffect(() => {
    // A 404 from the conversation that was just closed must not follow the
    // user into the next one.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setError(null);
  }, [activeConversationId]);

  useEffect(() => {
    // Null covers the gone case too, so a dead conversation is never fetched
    // and its 404 never paints an error banner.
    if (!conversationId) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setMessages([]);
      return;
    }
    if (justCreatedRef.current === conversationId) {
      justCreatedRef.current = null;
      return;
    }
    api<Message[]>(`/conversations/${conversationId}/messages`, {}, tenantId)
      .then(setMessages)
      .catch((e) => setError(String(e)));
  }, [conversationId, tenantId]);

  // Document metadata for the hero (context chip + title-derived suggestions)
  // and the composer's attachment chips — best-effort, both render without it.
  const refreshDocs = useCallback(() => {
    api<DocMeta[]>("/documents", {}, tenantId)
      .then(setDocs)
      .catch(() => setDocs(null));
  }, [tenantId]);
  useEffect(refreshDocs, [refreshDocs]);

  // Files dropped into this conversation. They ride the ordinary vault
  // pipeline, so the chips just mirror ingest status until everything lands.
  const attachments = conversationId
    ? (docs ?? []).filter((d) => d.conversation_id === conversationId)
    : [];
  const attachmentsBusy = attachments.some((d) =>
    ["uploaded", "parsing", "embedding"].includes(d.status)
  );
  useEffect(() => {
    if (!attachmentsBusy) return;
    const t = setInterval(refreshDocs, 3000);
    return () => clearInterval(t);
  }, [attachmentsBusy, refreshDocs]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight });
  }, [messages, streamText]);

  // useCallback so AssistantMessage's memo actually holds: a fresh arrow here
  // would change on every streamed frame and re-render every settled message.
  const exportSlides = useCallback(
    async (messageId: string) => {
      if (!conversationId) return;
      setExportingId(messageId);
      setError(null);
      try {
        const out = await api<{ download_url: string }>(
          `/conversations/${conversationId}/messages/${messageId}/slides`,
          { method: "POST" },
          tenantId
        );
        openPresigned(out.download_url);
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
      } finally {
        setExportingId(null);
      }
    },
    [conversationId, tenantId]
  );

  function stopStreaming() {
    abortRef.current?.abort();
  }

  /** The open conversation, or a fresh one — a first message and a first
   *  attachment both need it, so the create lives once. Null = the create
   *  failed and the error banner already says so. */
  async function ensureConversation(titleSeed: string): Promise<string | null> {
    // Null when the previous chat was deleted, so the first action after that
    // opens a fresh one rather than posting into a conversation that is gone.
    if (conversationId) return conversationId;
    try {
      const created = await api<{ id: string }>(
        "/conversations",
        {
          method: "POST",
          body: JSON.stringify({
            title: titleSeed.slice(0, 80),
            project_id: activeProjectId,
          }),
        },
        tenantId
      );
      justCreatedRef.current = created.id;
      setCreatedHereIds((ids) => [...ids, created.id]);
      setModes((s) => ({ ...s, [created.id]: s["new"] ?? "chat" }));
      router.replace(convHref(created.id));
      ws.refreshConversations();
      return created.id;
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      return null;
    }
  }

  async function attach(files: FileList) {
    setError(null);
    for (const file of Array.from(files)) {
      const mime = uploadMime(file);
      if (!mime) {
        setError(`${file.name}: this file type isn't supported`);
        continue;
      }
      // Attaching before the first message still needs somewhere to attach to.
      const convId = await ensureConversation(file.name);
      if (!convId) return;
      setUploadingCount((n) => n + 1);
      try {
        const { id, upload_url } = await api<{ id: string; upload_url: string }>(
          "/documents",
          {
            method: "POST",
            body: JSON.stringify({
              title: file.name,
              mime,
              size_bytes: file.size,
              project_id: activeProjectId,
              conversation_id: convId,
            }),
          },
          tenantId
        );
        const put = await fetch(upload_url, {
          method: "PUT",
          headers: { "Content-Type": mime },
          body: file,
        });
        if (!put.ok) throw new Error(`Upload failed (${put.status})`);
        await api(`/documents/${id}/complete`, { method: "POST" }, tenantId);
      } catch (err) {
        setError(`${file.name}: ${err instanceof Error ? err.message : String(err)}`);
      } finally {
        setUploadingCount((n) => n - 1);
      }
    }
    refreshDocs();
  }

  async function send(e?: React.FormEvent) {
    e?.preventDefault();
    const content = draft.trim();
    if (!content || streamText !== null) return;
    setError(null);
    setDraft("");
    if (inputRef.current) inputRef.current.style.height = "auto";

    const convId = await ensureConversation(content);
    if (!convId) return;

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
        onDelta: pushDelta,
        onDone: (message) => {
          // The persisted message replaces the streamed text wholesale, so
          // anything still buffered is redundant — drop it rather than let a
          // queued frame land after the bubble has gone.
          discardDeltas();
          setSoftCap(Boolean(message.soft_cap));
          setStreamText(null);
          const done = message as unknown as Message & { scope_used?: string | null };
          setMessages((m) => [...m, done]);
          if (done.scope_used) setScopes((s) => ({ ...s, [done.id]: done.scope_used! }));
          ws.refreshConversations();
        },
        onError: (_code, msg) => {
          discardDeltas();
          setStreamText(null);
          setError(msg);
        },
        onAbort: () => {
          // The server may still have persisted the reply — converge on its state.
          discardDeltas();
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
                    onExport={exportSlides}
                    exporting={exportingId === m.id}
                    readOnly={readOnly}
                  />
                )
              )}
              {streamText !== null && (
                <article className="max-w-full rounded-2xl border border-edge bg-card px-5 py-4 shadow-card sm:px-6 sm:py-5">
                  {streamText ? (
                    <>
                      <AnswerMarkdown content={stripCiteMarkers(streamText)} />
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

      {activeProject && !activeProject.is_development && !empty && (
        <div className="border-t border-edge px-4 py-3 sm:px-6">
          <div className="mx-auto w-full max-w-[720px]">
            <ProjectPlanPanel
              projectId={activeProject.id}
              hasPlan={activeProject.has_plan}
              compact
            />
          </div>
        </div>
      )}

      {readOnly ? (
        <div className="px-4 pt-2 pb-4 sm:px-6 sm:pb-6">
          <p className="mx-auto w-full max-w-[720px] rounded-[18px] border border-edge bg-sidebar px-5 py-3.5 text-center text-[13px] font-semibold text-subtle">
            {unknownConversation
              ? // Reachable only when the list itself failed to load — a
                // deleted chat no longer lands here at all, it opens an empty
                // composer instead.
                "Couldn't check who owns this chat — refresh to reply"
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
          {(attachments.length > 0 || uploadingCount > 0) && (
            <div className="flex flex-wrap gap-1.5 px-0.5 pb-2">
              {attachments.map((d) => (
                <span
                  key={d.id}
                  className={`flex items-center gap-1.5 rounded-full border border-edge px-2.5 py-1 text-[11.5px] font-semibold ${
                    d.status === "failed" ? "bg-danger-soft text-danger" : "bg-sidebar text-subtle"
                  }`}
                  title={d.status === "failed" ? (d.error ?? "Failed to read") : d.title}
                >
                  <ClipIcon className="h-3 w-3" />
                  <span className="max-w-44 truncate">{d.title}</span>
                  {d.status !== "ready" && (
                    <span className="text-[10.5px] font-bold uppercase">
                      {d.status === "failed" ? "failed" : "reading…"}
                    </span>
                  )}
                </span>
              ))}
              {uploadingCount > 0 && (
                <span className="flex items-center gap-1.5 rounded-full border border-edge bg-sidebar px-2.5 py-1 text-[11.5px] font-semibold text-subtle">
                  <Spinner className="h-3 w-3" /> Uploading…
                </span>
              )}
            </div>
          )}
          <div className="flex items-end gap-2.5">
            <button
              type="button"
              onClick={() => fileRef.current?.click()}
              disabled={uploadingCount > 0}
              aria-label="Attach a file to this chat"
              title="Attach a file — it joins the vault and this chat reads it first"
              className="mb-1.5 flex-none rounded-lg p-1.5 text-subtle transition hover:bg-sidebar hover:text-ink disabled:opacity-50"
            >
              <ClipIcon className="h-[18px] w-[18px]" />
            </button>
            <input
              ref={fileRef}
              type="file"
              multiple
              accept={ACCEPT}
              className="hidden"
              onChange={(e) => {
                if (e.target.files?.length) attach(e.target.files);
                // Same file again (a failed upload, a corrected copy) must
                // still fire a change event.
                e.target.value = "";
              }}
            />
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
