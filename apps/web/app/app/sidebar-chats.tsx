"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { ChatIcon } from "@/components/icons";
import { useWorkspace, type Conversation } from "./workspace";

/** Workspace URL builder + nav styles, shared with sidebar.tsx (this file is
 * the import root so the dependency stays one-directional). */
export function href(params: { view?: "vault"; project?: string | null; c?: string }) {
  const q = new URLSearchParams();
  if (params.view) q.set("view", params.view);
  if (params.project) q.set("project", params.project);
  if (params.c) q.set("c", params.c);
  const s = q.toString();
  return s ? `/app?${s}` : "/app";
}

export const item =
  "group relative flex items-center gap-2.5 rounded-card px-3 py-2 text-[13.5px] font-semibold";
export const itemRest = "text-subtle hover:bg-ink/[.045]";
export const itemActive =
  "bg-accent-tint text-ink before:absolute before:-left-3.5 before:top-2 before:bottom-2 before:w-[3px] before:rounded before:bg-electric-blue before:content-['']";
// Each section starts with a hairline divider so the groups (Projects /
// Shared in … / Chats in …) read as clearly segmented blocks.
export const navLabel =
  "mt-4 flex items-baseline gap-3 border-t border-edge-strong px-3 pb-1.5 pt-3.5 text-xs font-bold uppercase tracking-[.1em] text-faint";

// A date sub-label inside the Chats section — quieter than navLabel, so the
// dates read as ordering, not as another filter.
const dateLabel = "px-3 pt-2 pb-1 text-xs font-semibold text-faint";

/** Bucket a conversation into a date group by its updated_at date. */
function groupOf(c: Conversation): string {
  const day = (d: Date) => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
  const diff = Math.round((day(new Date()) - day(new Date(c.updated_at))) / 86_400_000);
  if (diff <= 0) return "Today";
  if (diff === 1) return "Yesterday";
  if (diff < 7) return "This week";
  return "Earlier";
}

/** Chat lists for the sidebar: teammates' shared chats (read-only, no
 * delete), then the caller's own chats date-grouped with two-step delete.
 * Both follow the selected project, and their headings name it — a silent
 * filter read as "these are all my chats". */
export default function SidebarChats({
  projectId,
  convId,
  view,
  onWorkspace,
}: {
  projectId: string | null;
  convId: string | null;
  view: "chat" | "vault";
  onWorkspace: boolean;
}) {
  const ws = useWorkspace();
  const router = useRouter();
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);
  // Closing the confirm row unmounts its focused button, so focus would drop
  // to <body>. This remembers which ✕ to hand it back to — or, when the chat
  // was deleted and its ✕ is gone, the page itself.
  const returnFocusTo = useRef<string | null>(null);

  useEffect(() => {
    if (confirmDeleteId !== null || returnFocusTo.current === null) return;
    const target =
      document.querySelector<HTMLElement>(`[data-delete-chat="${returnFocusTo.current}"]`) ??
      document.getElementById("main-content");
    target?.focus();
    returnFocusTo.current = null;
  }, [confirmDeleteId]);

  const inScope = projectId
    ? ws.conversations.filter((c) => c.project_id === projectId)
    : ws.conversations;
  const recentChats = inScope.filter((c) => c.is_mine).slice(0, 30);
  const sharedChats = inScope.filter((c) => !c.is_mine).slice(0, 15);
  const chatGroups = ["Today", "Yesterday", "This week", "Earlier"]
    .map((label) => ({ label, chats: recentChats.filter((c) => groupOf(c) === label) }))
    .filter((g) => g.chats.length > 0);
  const projectName = projectId
    ? (ws.projects.find((p) => p.id === projectId)?.name ?? "this project")
    : null;
  // The scope keeps its own casing — an uppercased project name is a
  // different-looking name.
  const scope = (
    <span
      className="normal-case tracking-normal text-ink"
      title={projectName ?? undefined}
    >
      {projectName ?? "all projects"}
    </span>
  );

  async function deleteConversation(id: string) {
    setDeleting(true);
    try {
      await api(`/conversations/${id}`, { method: "DELETE" }, ws.tenant!.id);
      await ws.refreshConversations();
      if (id === convId) {
        router.replace(href({ project: projectId }));
      }
    } catch (err) {
      ws.setError(err instanceof Error ? err.message : String(err));
    } finally {
      returnFocusTo.current = id;
      setDeleting(false);
      setConfirmDeleteId(null);
    }
  }

  return (
    <>
      {sharedChats.length > 0 && (
        <>
          <div className={navLabel}>
            <span className="min-w-0 truncate">Shared in {scope}</span>
          </div>
          {sharedChats.map((c) => (
            <Link
              key={c.id}
              href={href({ project: projectId, c: c.id })}
              aria-current={
                onWorkspace && view === "chat" && convId === c.id ? "page" : undefined
              }
              title={`${c.title ?? "Untitled"} — shared by ${c.owner_email ?? "a teammate"}`}
              className={`${item} mb-0.5 ${
                onWorkspace && view === "chat" && convId === c.id ? itemActive : itemRest
              }`}
            >
              <ChatIcon className="h-3.5 w-3.5" />
              <span className="min-w-0">
                <span className="block truncate font-medium">{c.title ?? "Untitled"}</span>
                <span className="block truncate text-xs font-semibold text-faint">
                  {c.owner_email ?? "a teammate"}
                </span>
              </span>
            </Link>
          ))}
        </>
      )}

      <div className={navLabel}>
        <span className="min-w-0 truncate">Chats in {scope}</span>
        <Link
          href={href({ project: projectId })}
          className="ml-auto shrink-0 text-xs font-bold normal-case tracking-normal text-electric-blue hover:underline"
          title="Start a new conversation"
        >
          + New
        </Link>
      </div>
      {chatGroups.length === 0 && (
        <p className="px-3 py-1 text-xs font-medium text-faint">
          {/* With teammates' chats listed just above, a bare "No chats"
              would contradict them. */}
          No chats {sharedChats.length > 0 && "of your own "}in {projectName ?? "any project"} yet
        </p>
      )}
      {chatGroups.map((g) => (
        <div key={g.label}>
          <div className={dateLabel}>{g.label}</div>
          {g.chats.map((c) => (
            <div key={c.id} className="group relative">
              {confirmDeleteId === c.id ? (
                <div
                  className="mb-0.5 flex items-center justify-between gap-2 rounded-card bg-danger-soft px-3 py-2"
                  onClick={(e) => e.stopPropagation()}
                >
                  <span className="truncate text-xs font-semibold text-danger">
                    Delete chat?
                  </span>
                  <span className="flex shrink-0 gap-2">
                    <button
                      // The ✕ that opened this row is gone, so focus moves here.
                      autoFocus
                      onClick={() => deleteConversation(c.id)}
                      disabled={deleting}
                      className="text-xs font-bold text-danger underline disabled:opacity-50"
                    >
                      Delete
                    </button>
                    <button
                      // A delete already sent cannot be taken back, so "Keep"
                      // waits for it rather than pretending to cancel it.
                      disabled={deleting}
                      onClick={() => {
                        returnFocusTo.current = c.id;
                        setConfirmDeleteId(null);
                      }}
                      className="text-xs font-semibold text-subtle underline"
                    >
                      Keep
                    </button>
                  </span>
                </div>
              ) : (
                <>
                  <Link
                    href={href({ project: projectId, c: c.id })}
                    aria-current={
                      onWorkspace && view === "chat" && convId === c.id ? "page" : undefined
                    }
                    className={`${item} mb-0.5 pr-8 ${
                      onWorkspace && view === "chat" && convId === c.id
                        ? itemActive
                        : itemRest
                    }`}
                  >
                    <ChatIcon className="h-3.5 w-3.5" />
                    <span className="block truncate font-medium">
                      {c.title ?? "Untitled"}
                    </span>
                  </Link>
                  {c.is_mine && (
                    <button
                      disabled={deleting}
                      onClick={(e) => {
                        e.stopPropagation();
                        setConfirmDeleteId(c.id);
                      }}
                      data-delete-chat={c.id}
                      title="Delete conversation"
                      aria-label={`Delete conversation ${c.title ?? "Untitled"}`}
                      // Invisible, not display:none — a hidden button can never
                      // take keyboard focus, so it could only be used by mouse.
                      // Touch screens cannot hover, so there it is always shown.
                      className="absolute top-1/2 right-1.5 grid h-6 w-6 -translate-y-1/2 place-items-center rounded-card border border-edge-ui bg-card text-subtle opacity-0 group-hover:opacity-100 hover:text-danger focus-visible:opacity-100 [@media(hover:none)]:opacity-100"
                    >
                      ✕
                    </button>
                  )}
                </>
              )}
            </div>
          ))}
        </div>
      ))}
    </>
  );
}
