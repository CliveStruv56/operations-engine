"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { api, apiStream } from "@/lib/api";
import { uploadMime } from "@/lib/uploads";
import EmptyHero, { type DocMeta, type Suggestion } from "./hero";
import ProjectPlanPanel from "./project-plan";
import ShareBar from "./share-bar";
import { useWorkspace } from "./workspace";
import Composer, { ReadOnlyNotice } from "./_chat/composer";
import MessageList from "./_chat/message-list";
import ScopeBanner from "./_chat/scope-banner";
import type { Message } from "./_chat/types";
import { useDeltaBuffer } from "./_chat/use-delta-buffer";
import { uploadDocument, useMessageActions } from "./_chat/use-message-actions";

// The chat panel: conversation state, streaming and ownership. Its parts —
// message list, sources, composer, scope banner, and the per-answer actions —
// live in ./_chat (a private folder, so not a route).
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
  // Like scopes: live-session only, keyed by message id. "none" marks an
  // answer the vault could not back, which is when recovery actions show.
  const [coverages, setCoverages] = useState<Record<string, string>>({});
  const [messages, setMessages] = useState<Message[]>([]);
  const [draft, setDraft] = useState("");
  const [createdHereIds, setCreatedHereIds] = useState<string[]>([]);
  const [softCap, setSoftCap] = useState(false);
  const [useVault, setUseVault] = useState(true);
  // "Include company data": the claims register plus the community-profile
  // and contact-book lookups (where those modules are on for the tenant).
  const [useCompany, setUseCompany] = useState(true);
  // Task mode is sticky per conversation ("new" = the not-yet-created one).
  const [modes, setModes] = useState<Record<string, string>>({});
  const modeKey = activeConversationId ?? "new";
  const mode = modes[modeKey] ?? "chat";
  const webSearchEnabled = ws.tenant!.features?.web_search === true;
  const devProjectsEnabled = ws.tenant!.features?.projects === true;
  const grantsEnabled = ws.tenant!.features?.grants === true;
  const [docs, setDocs] = useState<DocMeta[] | null>(null);
  const [uploadingCount, setUploadingCount] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const abortRef = useRef<AbortController | null>(null);
  // Set when this panel just created the conversation itself: the URL update
  // that follows must not refetch (and clobber) the in-flight local state.
  const justCreatedRef = useRef<string | null>(null);
  const { streamText, setStreamText, pushDelta, discardDeltas } = useDeltaBuffer();

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
  const createdHere =
    activeConversationId !== null && createdHereIds.includes(activeConversationId);
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

  const actions = useMessageActions({
    conversationId,
    tenantId,
    activeProjectId,
    messages,
    refreshDocs,
    setError,
  });

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
        await uploadDocument(tenantId, file, {
          title: file.name,
          mime,
          project_id: activeProjectId,
          conversation_id: convId,
        });
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

    // apiStream reports every ending through one of its handlers, but a throw
    // from one of those handlers would otherwise leave streamText at "" and
    // the composer locked until reload (code review WEB-2).
    try {
      await apiStream(
        `/conversations/${convId}/messages`,
        {
          content,
          use_vault: useVault,
          use_company: useCompany,
          task_kind: mode,
        },
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
            const done = message as unknown as Message & {
              scope_used?: string | null;
              coverage?: string | null;
            };
            setMessages((m) => [...m, done]);
            if (done.scope_used) setScopes((s) => ({ ...s, [done.id]: done.scope_used! }));
            if (done.coverage) setCoverages((s) => ({ ...s, [done.id]: done.coverage! }));
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
    } catch (err) {
      discardDeltas();
      setStreamText(null);
      setError(err instanceof Error ? err.message : "Something went wrong — try again.");
    } finally {
      abortRef.current = null;
    }
  }

  function pickSuggestion(s: Suggestion) {
    setDraft(s.text);
    if (s.mode) setModes((st) => ({ ...st, [modeKey]: s.mode! }));
    inputRef.current?.focus();
  }

  const empty = messages.length === 0 && streamText === null;

  return (
    <section className="flex min-h-0 flex-1 flex-col bg-canvas">
      {/* The empty-state hero carries the project context; the banner only
          needs to keep the scope visible once a conversation is underway. */}
      {activeProject && !empty && <ScopeBanner project={activeProject} />}
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
              grantsEnabled={grantsEnabled}
              firstUse={
                docs !== null &&
                docs.length === 0 &&
                ws.projects.length === 0 &&
                ws.conversations.length === 0
              }
              onPick={pickSuggestion}
            />
          ) : (
            <MessageList
              messages={messages}
              streamText={streamText}
              scopes={scopes}
              coverages={coverages}
              actions={actions}
              readOnly={readOnly}
            />
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
        <ReadOnlyNotice
          // Reachable only when the list itself failed to load — a deleted
          // chat no longer lands here at all, it opens an empty composer.
          ownerUnknown={unknownConversation}
          ownerEmail={activeConv?.owner_email ?? null}
        />
      ) : (
        <Composer
          mode={mode}
          onModeChange={(key) => setModes((s) => ({ ...s, [modeKey]: key }))}
          webSearchEnabled={webSearchEnabled}
          attachments={attachments}
          uploadingCount={uploadingCount}
          onAttach={attach}
          draft={draft}
          onDraftChange={setDraft}
          inputRef={inputRef}
          streaming={streamText !== null}
          onSend={send}
          onStop={stopStreaming}
          useVault={useVault}
          onToggleVault={() => setUseVault((v) => !v)}
          useCompany={useCompany}
          onToggleCompany={() => setUseCompany((v) => !v)}
        />
      )}
    </section>
  );
}
