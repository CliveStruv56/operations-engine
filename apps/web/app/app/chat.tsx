"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api, apiStream } from "@/lib/api";

type Conversation = { id: string; title: string | null; updated_at: string };
type Message = {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  model: string | null;
  cost_usd: number | null;
};

export default function ChatPanel({ tenantId }: { tenantId: string }) {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [draft, setDraft] = useState("");
  const [streamText, setStreamText] = useState<string | null>(null);
  const [softCap, setSoftCap] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  const loadConversations = useCallback(async () => {
    const list = await api<Conversation[]>("/conversations", {}, tenantId);
    setConversations(list);
    return list;
  }, [tenantId]);

  const openConversation = useCallback(
    async (id: string) => {
      setActiveId(id);
      setMessages(await api<Message[]>(`/conversations/${id}/messages`, {}, tenantId));
    },
    [tenantId]
  );

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    loadConversations().catch((e) => setError(String(e)));
  }, [loadConversations]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight });
  }, [messages, streamText]);

  async function send(e: React.FormEvent) {
    e.preventDefault();
    const content = draft.trim();
    if (!content || streamText !== null) return;
    setError(null);
    setDraft("");

    let convId = activeId;
    try {
      if (!convId) {
        const created = await api<Conversation>(
          "/conversations",
          { method: "POST", body: JSON.stringify({ title: content.slice(0, 80) }) },
          tenantId
        );
        convId = created.id;
        setActiveId(convId);
        await loadConversations();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      return;
    }

    setMessages((m) => [
      ...m,
      { id: `local-${Date.now()}`, role: "user", content, model: null, cost_usd: null },
    ]);
    setStreamText("");

    await apiStream(`/conversations/${convId}/messages`, { content }, tenantId, {
      onDelta: (delta) => setStreamText((t) => (t ?? "") + delta),
      onDone: (message) => {
        setSoftCap(Boolean(message.soft_cap));
        setStreamText(null);
        setMessages((m) => [...m, message as unknown as Message]);
        loadConversations();
      },
      onError: (_code, msg) => {
        setStreamText(null);
        setError(msg);
      },
    });
  }

  return (
    <section className="flex min-h-0 flex-1">
      <aside className="flex w-60 shrink-0 flex-col border-r border-line">
        <div className="border-b border-line p-3">
          <button
            onClick={() => {
              setActiveId(null);
              setMessages([]);
            }}
            className="w-full rounded-sm bg-accent px-3 py-2 text-left text-sm font-medium text-accent-ink hover:opacity-90"
          >
            New conversation
          </button>
        </div>
        <div className="min-h-0 flex-1 space-y-0.5 overflow-y-auto p-2">
          {conversations.map((c) => (
            <button
              key={c.id}
              onClick={() => openConversation(c.id)}
              className={`block w-full truncate rounded-sm px-3 py-2 text-left text-sm ${
                c.id === activeId
                  ? "bg-accent-soft font-medium"
                  : "text-ink-muted hover:bg-paper hover:text-ink"
              }`}
            >
              {c.title ?? "Untitled"}
            </button>
          ))}
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
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
              {m.role === "assistant" && m.model && (
                <p className="data mt-1 text-ink-faint uppercase">{m.model}</p>
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
        <form onSubmit={send} className="flex gap-2 border-t border-line p-4">
          <input
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder="Ask a question…"
            className="min-w-0 flex-1 rounded-sm border border-line bg-surface px-3 py-2 text-sm"
          />
          <button
            type="submit"
            disabled={streamText !== null}
            className="rounded-sm bg-accent px-5 py-2 text-sm font-medium text-accent-ink hover:opacity-90 disabled:opacity-50"
          >
            Send
          </button>
        </form>
      </div>
    </section>
  );
}
