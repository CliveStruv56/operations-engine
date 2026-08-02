"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { api } from "@/lib/api";
import {
  ChatIcon,
  HomeIcon,
  PulseIcon,
  SearchIcon,
  TargetIcon,
  VaultIcon,
} from "@/components/icons";
import { useWorkspace, type Conversation } from "./workspace";

function href(params: { view?: "vault"; project?: string | null; c?: string }) {
  const q = new URLSearchParams();
  if (params.view) q.set("view", params.view);
  if (params.project) q.set("project", params.project);
  if (params.c) q.set("c", params.c);
  const s = q.toString();
  return s ? `/app?${s}` : "/app";
}

const item =
  "group relative flex items-center gap-2.5 rounded-[10px] px-3 py-2 text-[13.5px] font-semibold";
const itemRest = "text-subtle hover:bg-ink/[.045]";
const itemActive =
  "bg-card text-ink shadow-card before:absolute before:-left-3.5 before:top-2 before:bottom-2 before:w-[3px] before:rounded before:bg-accent before:content-['']";
// Each section starts with a hairline divider so the groups (Development
// projects / Projects / Recent — …) read as clearly segmented blocks.
const navLabel =
  "mt-4 flex items-baseline border-t border-edge-strong px-3 pb-1.5 pt-3.5 text-[10.5px] font-bold uppercase tracking-[.1em] text-faint";

/** Bucket a conversation into a Recent group by its updated_at date. */
function groupOf(c: Conversation): string {
  const day = (d: Date) => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
  const diff = Math.round((day(new Date()) - day(new Date(c.updated_at))) / 86_400_000);
  if (diff <= 0) return "Today";
  if (diff === 1) return "Yesterday";
  if (diff < 7) return "This week";
  return "Earlier";
}

export default function Sidebar({ open, onClose }: { open: boolean; onClose: () => void }) {
  const ws = useWorkspace();
  const router = useRouter();
  const pathname = usePathname();
  const sp = useSearchParams();
  const [addingProject, setAddingProject] = useState(false);
  const [projectName, setProjectName] = useState("");
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);

  const tenant = ws.tenant;
  if (!tenant) return null;

  const view = sp.get("view") === "vault" ? "vault" : "chat";
  const projectId = sp.get("project");
  const convId = sp.get("c");
  const onWorkspace = pathname === "/app";
  const onDevPages = pathname.startsWith("/app/projects");

  const devProjects = tenant.features?.projects === true
    ? ws.projects.filter((p) => !p.archived && p.is_development)
    : [];
  const coreProjects = ws.projects.filter((p) => !p.archived && !p.is_development);
  const recentChats = (
    projectId ? ws.conversations.filter((c) => c.project_id === projectId) : ws.conversations
  ).slice(0, 30);
  const chatGroups = ["Today", "Yesterday", "This week", "Earlier"]
    .map((label) => ({ label, chats: recentChats.filter((c) => groupOf(c) === label) }))
    .filter((g) => g.chats.length > 0);

  // Time-dependent by design: trial countdown and chat date groups may be a
  // render stale at worst — they refresh on any navigation.
  // eslint-disable-next-line react-hooks/purity
  const now = Date.now();
  const trialDaysLeft = tenant.trial_ends_at
    ? Math.max(0, Math.ceil((new Date(tenant.trial_ends_at).getTime() - now) / 86_400_000))
    : null;

  async function createProject(e: React.FormEvent) {
    e.preventDefault();
    const created = await ws.createProject(projectName);
    setProjectName("");
    setAddingProject(false);
    if (created) {
      router.push(href({ view: view === "vault" ? "vault" : undefined, project: created.id }));
      onClose();
    }
  }

  async function deleteConversation(id: string) {
    setDeleting(true);
    try {
      await api(`/conversations/${id}`, { method: "DELETE" }, tenant!.id);
      await ws.refreshConversations();
      if (id === convId) {
        router.replace(href({ project: projectId }));
      }
    } catch (err) {
      ws.setError(err instanceof Error ? err.message : String(err));
    } finally {
      setDeleting(false);
      setConfirmDeleteId(null);
    }
  }

  return (
    <>
      {open && (
        <div
          className="fixed inset-0 z-30 bg-ink/40 md:hidden"
          onClick={onClose}
          aria-hidden="true"
        />
      )}
      <aside
        className={`${open ? "flex" : "hidden"} fixed inset-y-0 left-0 z-40 w-[268px] shrink-0 flex-col border-r border-edge bg-sidebar md:static md:z-auto md:flex`}
      >
        <div className="flex items-center gap-2.5 px-5 pt-[18px] pb-4">
          {tenant.logo_url ? (
            // Presigned storage URL — next/image can't optimise it.
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={tenant.logo_url}
              alt={tenant.name}
              className="max-h-9 w-auto max-w-[160px]"
            />
          ) : (
            <span className="grid h-[34px] w-[34px] place-items-center rounded-[10px] bg-accent font-display text-lg font-semibold text-white">
              {tenant.name.slice(0, 1).toUpperCase()}
            </span>
          )}
          <span className="min-w-0">
            <span className="block truncate text-[15.5px] font-extrabold tracking-tight">
              {tenant.name}
            </span>
            <span className="block text-[10.5px] font-bold uppercase tracking-[.09em] text-faint">
              Flowgrid OS
            </span>
          </span>
        </div>

        <div className="px-3.5">
          <button
            onClick={() => window.dispatchEvent(new CustomEvent("open-command-palette"))}
            className="mb-2 flex w-full items-center gap-2 rounded-[10px] border border-edge bg-card px-3 py-2 text-[13px] text-faint hover:border-edge-strong"
          >
            <SearchIcon className="h-3.5 w-3.5" />
            Search chats &amp; documents
            <kbd className="ml-auto rounded-[5px] border border-edge bg-sidebar px-1.5 py-0.5 text-[10.5px] font-bold text-faint">
              ⌘K
            </kbd>
          </button>
        </div>

        <nav className="min-h-0 flex-1 overflow-y-auto px-3.5 pb-3" onClick={onClose}>
          <Link
            href={href({ project: projectId })}
            className={`${item} mb-0.5 ${onWorkspace && view === "chat" ? itemActive : itemRest}`}
          >
            <ChatIcon />
            Chat
          </Link>
          <Link
            href={href({ view: "vault", project: projectId })}
            className={`${item} ${onWorkspace && view === "vault" ? itemActive : itemRest}`}
          >
            <VaultIcon />
            Vault
          </Link>

          {tenant.features?.projects === true && (
            <>
              <div className={navLabel}>
                Development projects
                <Link
                  href="/app/projects"
                  className={`ml-auto text-[10.5px] font-bold ${
                    onDevPages ? "text-accent-deep" : "text-faint hover:text-accent-deep"
                  }`}
                >
                  All ↗
                </Link>
              </div>
              {devProjects.length === 0 && (
                <Link
                  href="/app/projects"
                  className="block px-3 py-1 text-xs font-medium text-faint hover:text-ink"
                >
                  Stage-gated schemes, gates &amp; funding →
                </Link>
              )}
              {devProjects.map((p) => (
                <div key={p.id} className="group relative">
                  <Link
                    href={href({ view: view === "vault" ? "vault" : undefined, project: p.id })}
                    className={`${item} mb-0.5 pr-9 ${
                      onWorkspace && projectId === p.id ? itemActive : itemRest
                    }`}
                  >
                    <PulseIcon />
                    <span className="block truncate">{p.name}</span>
                  </Link>
                  <Link
                    href={`/app/projects/${p.id}`}
                    title="Open project room"
                    aria-label={`Open ${p.name} project room`}
                    className="absolute top-1/2 right-2 grid h-[22px] w-[22px] -translate-y-1/2 place-items-center rounded-card text-faint hover:bg-card hover:text-accent-deep"
                  >
                    ↗
                  </Link>
                </div>
              ))}
            </>
          )}

          <div className={navLabel}>
            Projects
            <button
              onClick={(e) => {
                e.stopPropagation();
                setAddingProject(true);
              }}
              className="ml-auto text-[10.5px] font-bold text-accent-deep hover:underline"
            >
              + New
            </button>
          </div>
          <Link
            href={href({ view: view === "vault" ? "vault" : undefined })}
            className={`${item} mb-0.5 ${onWorkspace && projectId === null ? itemActive : itemRest}`}
          >
            <TargetIcon />
            Everything
          </Link>
          {coreProjects.map((p) => (
            <Link
              key={p.id}
              href={href({ view: view === "vault" ? "vault" : undefined, project: p.id })}
              className={`${item} mb-0.5 ${
                onWorkspace && projectId === p.id ? itemActive : itemRest
              }`}
            >
              <HomeIcon />
              <span className="truncate">{p.name}</span>
              <span className="ml-auto text-[11.5px] font-semibold text-faint">
                {p.document_count}
              </span>
            </Link>
          ))}
          {addingProject && (
            <form
              onSubmit={createProject}
              className="mt-1 px-3"
              onClick={(e) => e.stopPropagation()}
            >
              <input
                autoFocus
                required
                value={projectName}
                onChange={(e) => setProjectName(e.target.value)}
                onBlur={() => !projectName && setAddingProject(false)}
                placeholder="Project name"
                className="w-full rounded-[10px] border border-edge bg-card px-3 py-1.5 text-sm placeholder:text-faint focus:outline-none"
              />
            </form>
          )}

          {chatGroups.length === 0 && (
            <>
              <div className={navLabel}>Recent</div>
              <p className="px-3 py-1 text-xs font-medium text-faint">No conversations yet</p>
            </>
          )}
          {chatGroups.map((g) => (
            <div key={g.label}>
              <div className={navLabel}>
                Recent — {g.label}
                {g.label === chatGroups[0].label && (
                  <Link
                    href={href({ project: projectId })}
                    className="ml-auto text-[10.5px] font-bold text-accent-deep hover:underline"
                    title="Start a new conversation"
                  >
                    + New
                  </Link>
                )}
              </div>
              {g.chats.map((c) => (
                <div key={c.id} className="group relative">
                  {confirmDeleteId === c.id ? (
                    <div
                      className="mb-0.5 flex items-center justify-between gap-2 rounded-[10px] bg-danger-soft px-3 py-2"
                      onClick={(e) => e.stopPropagation()}
                    >
                      <span className="truncate text-xs font-semibold text-danger">
                        Delete chat?
                      </span>
                      <span className="flex shrink-0 gap-2">
                        <button
                          onClick={() => deleteConversation(c.id)}
                          disabled={deleting}
                          className="text-xs font-bold text-danger underline disabled:opacity-50"
                        >
                          Delete
                        </button>
                        <button
                          onClick={() => setConfirmDeleteId(null)}
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
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setConfirmDeleteId(c.id);
                        }}
                        title="Delete conversation"
                        aria-label={`Delete conversation ${c.title ?? "Untitled"}`}
                        className="absolute top-1/2 right-2 hidden h-[22px] w-[22px] -translate-y-1/2 place-items-center rounded-card border border-edge bg-card text-subtle group-hover:grid hover:text-danger focus-visible:grid"
                      >
                        ✕
                      </button>
                    </>
                  )}
                </div>
              ))}
            </div>
          ))}
        </nav>

        {trialDaysLeft !== null && (
          <div className="mx-3.5 mb-2 rounded-xl border border-edge bg-card p-3.5">
            <div className="flex justify-between text-[12.5px] font-bold">
              Trial — {trialDaysLeft} day{trialDaysLeft === 1 ? "" : "s"} left
              <span className="text-accent-deep">{tenant.seats} seats</span>
            </div>
            <div className="mt-2 h-[5px] overflow-hidden rounded-full bg-sidebar">
              <div
                className="h-full rounded-full bg-accent"
                style={{ width: `${Math.min(100, Math.round((trialDaysLeft / 14) * 100))}%` }}
              />
            </div>
            <div className="mt-2 flex items-center justify-between text-[11.5px] font-semibold text-faint">
              Ends {new Date(tenant.trial_ends_at!).toLocaleDateString("en-GB")}
            </div>
          </div>
        )}

        <div className="border-t border-edge px-5 py-3.5">
          <div className="flex items-center gap-2.5">
            <span className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-ink text-[13px] font-bold text-[#F8EFE2]">
              {(ws.email ?? "?").slice(0, 1).toUpperCase()}
            </span>
            <span className="min-w-0">
              <span className="block text-[13px] font-bold capitalize">{tenant.role}</span>
              <span className="block truncate text-[11px] font-semibold text-faint">
                {ws.email}
              </span>
            </span>
          </div>
          <div className="mt-2.5 flex items-center gap-3">
            <Link
              href="/app/usage"
              onClick={onClose}
              className={`text-xs font-semibold ${
                pathname.startsWith("/app/usage")
                  ? "text-accent-deep"
                  : "text-subtle hover:text-ink"
              }`}
            >
              Usage
            </Link>
            {(tenant.role === "admin" || tenant.role === "owner") && (
              <Link
                href="/app/settings"
                onClick={onClose}
                className={`text-xs font-semibold ${
                  pathname.startsWith("/app/settings")
                    ? "text-accent-deep"
                    : "text-subtle hover:text-ink"
                }`}
              >
                Settings
              </Link>
            )}
            <button
              onClick={ws.logout}
              className="ml-auto text-xs font-semibold text-subtle hover:text-ink"
            >
              Sign out
            </button>
          </div>
        </div>
      </aside>
    </>
  );
}
