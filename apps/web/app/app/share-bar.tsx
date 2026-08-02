"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { useWorkspace, type Conversation } from "./workspace";

/** Owner-only visibility toggle for the active conversation. Sits in the
 * banner-strip position above the chat; same switch pattern as the
 * composer's Vault toggle. */
export default function ShareBar({
  conversation,
  onError,
}: {
  conversation: Conversation;
  onError: (message: string) => void;
}) {
  const ws = useWorkspace();
  const [busy, setBusy] = useState(false);
  const shared = conversation.visibility === "tenant";

  async function toggle() {
    if (busy) return;
    setBusy(true);
    try {
      await api(
        `/conversations/${conversation.id}`,
        {
          method: "PATCH",
          body: JSON.stringify({ visibility: shared ? "private" : "tenant" }),
        },
        ws.tenant!.id
      );
      await ws.refreshConversations();
    } catch (err) {
      onError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex items-center gap-2.5 border-b border-edge bg-sidebar px-6 py-1.5">
      <button
        type="button"
        role="switch"
        aria-checked={shared}
        aria-label="Share this chat with the team"
        disabled={busy}
        onClick={toggle}
        className={`relative h-[18px] w-8 flex-none rounded-full transition disabled:opacity-50 after:absolute after:top-0.5 after:left-0.5 after:h-3.5 after:w-3.5 after:rounded-full after:bg-white after:transition after:content-[''] ${
          shared ? "bg-grounded after:translate-x-[14px]" : "bg-edge-strong"
        }`}
      />
      <span className="text-xs font-bold text-subtle">
        {shared
          ? "Shared with team — members can read this chat"
          : "Private — only you can see this chat"}
      </span>
    </div>
  );
}
