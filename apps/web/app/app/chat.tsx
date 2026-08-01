"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { api, apiStream } from "@/lib/api";
import { useWorkspace } from "./workspace";

type Citation = {
  n: number;
  chunk_id: string;
  document_id: string;
  title: string;
  page_start: number | null;
  page_end: number | null;
  snippet: string;
};
type Message = {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  citations: Citation[];
  model: string | null;
  cost_usd: number | null;
};

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
  const [scopes, setScopes] = useState<Record<string, string>>({});
  const [messages, setMessages] = useState<Message[]>([]);
  const [draft, setDraft] = useState("");
  const [streamText, setStreamText] = useState<string | null>(null);
  const [softCap, setSoftCap] = useState(false);
  const [useVault, setUseVault] = useState(true);
  const [evidence, setEvidence] = useState<Citation | null>(null);
  const [error, setError] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  // Set when this panel just created the conversation itself: the URL update
  // that follows must not refetch (and clobber) the in-flight local state.
  const justCreatedRef = useRef<string | null>(null);

  useEffect(() => {
    if (!activeConversationId) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setMessages([]);
      setEvidence(null);
      return;
    }
    if (justCreatedRef.current === activeConversationId) {
      justCreatedRef.current = null;
      return;
    }
    setEvidence(null);
    api<Message[]>(`/conversations/${activeConversationId}/messages`, {}, tenantId)
      .then(setMessages)
      .catch((e) => setError(String(e)));
  }, [activeConversationId, tenantId]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight });
  }, [messages, streamText]);

  function convHref(convId: string) {
    const q = new URLSearchParams();
    if (activeProjectId) q.set("project", activeProjectId);
    q.set("c", convId);
    return `/app?${q.toString()}`;
  }

  async function send(e: React.FormEvent) {
    e.preventDefault();
    const content = draft.trim();
    if (!content || streamText !== null) return;
    setError(null);
    setDraft("");

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

    await apiStream(`/conversations/${convId}/messages`, { content, use_vault: useVault }, tenantId, {
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
    });
  }

  return (
    <section className="flex min-h-0 flex-1">
      <div className="flex min-w-0 flex-1 flex-col">
        {activeProject && (
          <p className="border-b border-line bg-paper px-6 py-1.5">
            <span className="data text-ink-muted uppercase">
              Project: {activeProject.name} — answers prefer this project&apos;s documents
            </span>
          </p>
        )}
        {softCap && (
          <p className="border-b border-line bg-warn-soft px-6 py-2 text-sm text-warn">
            This workspace has used its monthly budget — replies use the economy model until it
            resets.
          </p>
        )}
        <div ref={scrollRef} className="min-h-0 flex-1 space-y-4 overflow-y-auto px-6 py-5">
          {messages.length === 0 && streamText === null && (
            <div className="flex h-full items-center justify-center">
              <p className="max-w-sm text-center text-sm text-ink-faint">
                Ask about anything in your vault — policies, prices, procedures — or draft
                something new.
              </p>
            </div>
          )}
          {messages.map((m) => (
            <div key={m.id} className={m.role === "user" ? "text-right" : ""}>
              <div
                className={`inline-block max-w-[85%] rounded-md px-4 py-2.5 text-left text-sm whitespace-pre-wrap ${
                  m.role === "user"
                    ? "bg-ink text-surface"
                    : "border border-line bg-paper"
                }`}
              >
                {m.content}
              </div>
              {m.role === "assistant" && m.citations?.length > 0 && (
                <div className="mt-1.5 flex flex-wrap gap-1.5">
                  {m.citations.map((c) => (
                    <button
                      key={c.chunk_id}
                      onClick={() => setEvidence(c)}
                      className="stamp bg-accent-soft text-accent hover:opacity-80"
                      title={c.title}
                    >
                      {c.n} · {c.title.length > 32 ? c.title.slice(0, 32) + "…" : c.title}
                      {c.page_start != null && ` · p.${c.page_start}`}
                    </button>
                  ))}
                </div>
              )}
              {m.role === "assistant" && m.model && (
                <p className="data mt-1 text-ink-faint uppercase">
                  {m.model}
                  {scopes[m.id] === "project" && " · from project documents"}
                  {scopes[m.id] === "vault" && " · from the whole vault"}
                </p>
              )}
            </div>
          ))}
          {streamText !== null && (
            <div>
              <div className="inline-block max-w-[85%] rounded-md border border-line bg-paper px-4 py-2.5 text-sm whitespace-pre-wrap">
                {streamText || "…"}
              </div>
            </div>
          )}
        </div>
        {error && (
          <p className="border-t border-line bg-danger-soft px-6 py-2 text-sm text-danger">
            {error}
          </p>
        )}
        <form onSubmit={send} className="flex items-center gap-2 border-t border-line p-4">
          <input
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder={useVault ? "Ask about your documents…" : "Ask anything…"}
            className="min-w-0 flex-1 rounded-sm border border-line bg-surface px-3 py-2 text-sm"
          />
          <button
            type="button"
            onClick={() => setUseVault((v) => !v)}
            aria-pressed={useVault}
            title={
              useVault
                ? "Answers use your vault and cite documents"
                : "Vault off — answers come from the model alone"
            }
            className={`stamp shrink-0 ${
              useVault ? "bg-accent-soft text-accent" : "text-ink-faint"
            }`}
          >
            vault {useVault ? "on" : "off"}
          </button>
          <button
            type="submit"
            disabled={streamText !== null}
            className="rounded-sm bg-accent px-5 py-2 text-sm font-medium text-accent-ink hover:opacity-90 disabled:opacity-50"
          >
            Send
          </button>
        </form>
      </div>

      {evidence && (
        <aside className="flex w-80 shrink-0 flex-col border-l border-line bg-paper">
          <header className="flex items-start justify-between gap-2 border-b border-line px-4 py-3">
            <div className="min-w-0">
              <p className="data text-ink-faint uppercase">Source {evidence.n}</p>
              <h3 className="mt-0.5 truncate text-sm font-semibold">{evidence.title}</h3>
              {evidence.page_start != null && (
                <p className="data mt-0.5 text-ink-muted">
                  Page {evidence.page_start}
                  {evidence.page_end != null && evidence.page_end !== evidence.page_start
                    ? `–${evidence.page_end}`
                    : ""}
                </p>
              )}
            </div>
            <button
              onClick={() => setEvidence(null)}
              className="shrink-0 text-ink-muted hover:text-ink"
              aria-label="Close source panel"
            >
              ✕
            </button>
          </header>
          <div className="min-h-0 flex-1 overflow-y-auto p-4">
            <p className="text-sm whitespace-pre-wrap text-ink-muted">{evidence.snippet}</p>
          </div>
        </aside>
      )}
    </section>
  );
}
