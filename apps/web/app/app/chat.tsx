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
    <section className="flex h-[32rem] rounded border border-neutral-200 text-sm">
      <aside className="w-56 shrink-0 overflow-y-auto border-r border-neutral-200 p-2 space-y-1">
        <button
          onClick={() => {
            setActiveId(null);
            setMessages([]);
          }}
          className="w-full rounded bg-neutral-900 px-3 py-2 text-left text-white"
        >
          New chat
        </button>
        {conversations.map((c) => (
          <button
            key={c.id}
            onClick={() => openConversation(c.id)}
            className={`block w-full truncate rounded px-3 py-2 text-left hover:bg-neutral-100 ${
              c.id === activeId ? "bg-neutral-100 font-medium" : ""
            }`}
          >
            {c.title ?? "Untitled"}
          </button>
        ))}
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        {softCap && (
          <p className="border-b border-amber-200 bg-amber-50 px-4 py-2 text-amber-800">
            This workspace has hit its monthly usage budget — replies use the
            economy model until it resets.
          </p>
        )}
        <div ref={scrollRef} className="flex-1 space-y-3 overflow-y-auto p-4">
          {messages.length === 0 && streamText === null && (
            <p className="text-neutral-400">Ask anything to start a conversation.</p>
          )}
          {messages.map((m) => (
            <div key={m.id} className={m.role === "user" ? "text-right" : ""}>
              <div
                className={`inline-block max-w-[85%] whitespace-pre-wrap rounded px-3 py-2 text-left ${
                  m.role === "user" ? "bg-neutral-900 text-white" : "bg-neutral-100"
                }`}
              >
                {m.content}
              </div>
              {m.role === "assistant" && m.model && (
                <p className="mt-1 text-xs text-neutral-400">{m.model}</p>
              )}
            </div>
          ))}
          {streamText !== null && (
            <div>
              <div className="inline-block max-w-[85%] whitespace-pre-wrap rounded bg-neutral-100 px-3 py-2">
                {streamText || "…"}
              </div>
            </div>
          )}
        </div>
        {error && <p className="px-4 pb-2 text-red-600">{error}</p>}
        <form onSubmit={send} className="flex gap-2 border-t border-neutral-200 p-3">
          <input
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder="Message…"
            className="min-w-0 flex-1 rounded border border-neutral-300 px-3 py-2"
          />
          <button
            type="submit"
            disabled={streamText !== null}
            className="rounded bg-neutral-900 px-4 py-2 text-white disabled:opacity-50"
          >
            Send
          </button>
        </form>
      </div>
    </section>
  );
}
