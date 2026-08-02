"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { PulseIcon } from "@/components/icons";
import { useWorkspace } from "./workspace";

/** Mirror of the API's ActivityFeedItem. */
export type ActivityItem = {
  action: string;
  actor_email: string | null;
  target_type: string | null;
  target_id: string | null;
  target_title: string | null;
  meta: Record<string, unknown>;
  created_at: string;
};

function timeAgo(iso: string): string {
  const mins = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 60_000));
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.round(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.round(hours / 24);
  return days === 1 ? "yesterday" : `${days}d ago`;
}

/** Humanise an audit action into a phrase; null = don't render (unknown
 * actions stay hidden, so a widened API allowlist can't leak odd rows). */
function phrase(i: ActivityItem): string | null {
  const title = i.target_title;
  switch (i.action) {
    case "document.complete":
      return `added ${title ?? "a document"} to the vault`;
    case "document.delete":
      return "removed a document";
    case "project.create":
      return `created project ${title ?? ""}`.trim();
    case "project.update":
      return `updated project ${title ?? ""}`.trim();
    case "project.delete":
      return "deleted a project";
    case "member.role_change":
      return typeof i.meta.new_role === "string"
        ? `changed a member's role to ${i.meta.new_role}`
        : "changed a member's role";
    case "invite.accept":
      return "joined the workspace";
    case "tenant.update":
      return "updated workspace settings";
    case "conversation.share":
      return typeof i.meta.title === "string" && i.meta.title
        ? `shared a chat: ${i.meta.title}`
        : "shared a chat with the team";
    case "conversation.unshare":
      return "unshared a chat";
  }
  if (i.action.startsWith("projects.")) return "updated a development project";
  return null;
}

/** "Recent team activity" for the chat empty-state hero. Self-fetching and
 * fail-silent, like DevStatusCard — renders nothing on error or no rows. */
export default function ActivityCard() {
  const ws = useWorkspace();
  const tenantId = ws.tenant?.id;
  const [items, setItems] = useState<ActivityItem[] | null>(null);

  useEffect(() => {
    if (!tenantId) return;
    let stale = false;
    api<ActivityItem[]>("/activity", {}, tenantId)
      .then((rows) => {
        if (!stale) setItems(rows);
      })
      .catch((err) => {
        console.error("Activity fetch failed", err);
        if (!stale) setItems(null);
      });
    return () => {
      stale = true;
    };
  }, [tenantId]);

  const rows = (items ?? [])
    .map((i) => ({ i, text: phrase(i) }))
    .filter((r): r is { i: ActivityItem; text: string } => r.text !== null)
    .slice(0, 6);
  if (rows.length === 0) return null;

  return (
    <div className="mt-7 w-full max-w-[620px] rounded-card border border-edge bg-card px-5 py-4 text-left shadow-card">
      <div className="flex items-center gap-2 text-[10.5px] font-bold tracking-[.1em] text-faint uppercase">
        <PulseIcon className="h-3 w-3" />
        Recent team activity
      </div>
      <ul className="mt-2.5 space-y-1.5">
        {rows.map(({ i, text }, n) => (
          <li key={`${i.created_at}-${n}`} className="flex items-baseline gap-2 text-[12.5px]">
            <span className="min-w-0 truncate font-semibold text-subtle">
              <span className="font-bold text-ink">
                {i.actor_email ? i.actor_email.split("@")[0] : "Someone"}
              </span>{" "}
              {text}
            </span>
            <span className="ml-auto shrink-0 text-[11px] font-semibold text-faint">
              {timeAgo(i.created_at)}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
