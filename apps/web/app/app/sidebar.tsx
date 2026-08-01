"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { api } from "@/lib/api";
import { useWorkspace } from "./workspace";

function href(params: { view?: "vault"; project?: string | null; c?: string }) {
  const q = new URLSearchParams();
  if (params.view) q.set("view", params.view);
  if (params.project) q.set("project", params.project);
  if (params.c) q.set("c", params.c);
  const s = q.toString();
  return s ? `/app?${s}` : "/app";
}

const itemBase = "block w-full rounded-sm border-l-2 px-3 py-1.5 text-left text-sm";
const itemActive = "border-accent bg-accent-soft font-medium text-accent";
const itemRest = "border-transparent text-ink hover:bg-accent-soft/50 hover:text-ink";

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
        className={`${open ? "flex" : "hidden"} fixed inset-y-0 left-0 z-40 w-64 shrink-0 flex-col border-r border-line bg-paper md:static md:z-auto md:flex md:w-60`}
      >
        <div className="border-b border-line px-5 py-4">
          <p className="data text-ink-faint uppercase">Operations Engine</p>
          <h1 className="mt-1 truncate text-base font-semibold tracking-tight">{tenant.name}</h1>
        </div>

        <nav className="min-h-0 flex-1 overflow-y-auto p-3" onClick={onClose}>
          <Link
            href={href({ project: projectId })}
            className={`${itemBase} mb-1 py-2 ${onWorkspace && view === "chat" ? itemActive : itemRest}`}
          >
            Chat
            <span className="mt-0.5 block text-xs font-normal text-ink-muted">
              Ask about your documents
            </span>
          </Link>
          <Link
            href={href({ view: "vault", project: projectId })}
            className={`${itemBase} mb-1 py-2 ${onWorkspace && view === "vault" ? itemActive : itemRest}`}
          >
            Vault
            <span className="mt-0.5 block text-xs font-normal text-ink-muted">
              The documents behind the answers
            </span>
          </Link>

          {tenant.features?.projects === true && (
            <>
              <div className="mt-5 mb-1 flex items-baseline justify-between px-3">
                <p className="data text-ink-muted uppercase">Development projects</p>
                <Link
                  href="/app/projects"
                  className={`data uppercase ${onDevPages ? "text-accent" : "text-ink-faint hover:text-accent"}`}
                >
                  All ↗
                </Link>
              </div>
              {devProjects.length === 0 && (
                <Link
                  href="/app/projects"
                  className="block px-3 py-1 text-xs text-ink-faint hover:text-ink"
                >
                  Stage-gated schemes, gates &amp; funding →
                </Link>
              )}
              {devProjects.map((p) => (
                <div key={p.id} className="group relative">
                  <Link
                    href={href({ view: view === "vault" ? "vault" : undefined, project: p.id })}
                    className={`${itemBase} mb-0.5 pr-9 ${
                      onWorkspace && projectId === p.id ? itemActive : itemRest
                    }`}
                  >
                    <span className="block truncate">{p.name}</span>
                  </Link>
                  <Link
                    href={`/app/projects/${p.id}`}
                    title="Open project room"
                    aria-label={`Open ${p.name} project room`}
                    className="data absolute top-1/2 right-2 -translate-y-1/2 rounded-sm px-1 text-ink-faint uppercase hover:text-accent"
                  >
                    ↗
                  </Link>
                </div>
              ))}
            </>
          )}

          <p className="data mt-5 mb-1 px-3 text-ink-muted uppercase">Projects</p>
          <Link
            href={href({ view: view === "vault" ? "vault" : undefined })}
            className={`${itemBase} mb-0.5 ${onWorkspace && projectId === null ? itemActive : itemRest}`}
          >
            Everything
          </Link>
          {coreProjects.map((p) => (
            <Link
              key={p.id}
              href={href({ view: view === "vault" ? "vault" : undefined, project: p.id })}
              className={`${itemBase} mb-0.5 flex items-baseline justify-between gap-2 ${
                onWorkspace && projectId === p.id ? itemActive : itemRest
              }`}
            >
              <span className="truncate">{p.name}</span>
              <span className="data shrink-0 text-ink-faint">{p.document_count}</span>
            </Link>
          ))}
          {addingProject ? (
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
                className="w-full rounded-sm border border-line bg-surface px-2 py-1 text-sm"
              />
            </form>
          ) : (
            <button
              onClick={(e) => {
                e.stopPropagation();
                setAddingProject(true);
              }}
              className="mt-1 block w-full px-3 py-1 text-left text-xs text-ink-muted hover:text-accent"
            >
              + New project
            </button>
          )}

          <div className="mt-5 mb-1 flex items-baseline justify-between px-3">
            <p className="data text-ink-muted uppercase">Recent chats</p>
            <Link
              href={href({ project: projectId })}
              className="data text-ink-faint uppercase hover:text-accent"
              title="Start a new conversation"
            >
              + New
            </Link>
          </div>
          {recentChats.length === 0 && (
            <p className="px-3 py-1 text-xs text-ink-faint">No conversations yet</p>
          )}
          {recentChats.map((c) => (
            <div key={c.id} className="group relative">
              {confirmDeleteId === c.id ? (
                <div
                  className="mb-0.5 flex items-center justify-between gap-2 rounded-sm border-l-2 border-danger bg-danger-soft px-3 py-1.5"
                  onClick={(e) => e.stopPropagation()}
                >
                  <span className="truncate text-xs text-danger">Delete chat?</span>
                  <span className="flex shrink-0 gap-2">
                    <button
                      onClick={() => deleteConversation(c.id)}
                      disabled={deleting}
                      className="text-xs font-medium text-danger underline disabled:opacity-50"
                    >
                      Delete
                    </button>
                    <button
                      onClick={() => setConfirmDeleteId(null)}
                      className="text-xs text-ink-muted underline"
                    >
                      Keep
                    </button>
                  </span>
                </div>
              ) : (
                <>
                  <Link
                    href={href({ project: projectId, c: c.id })}
                    className={`${itemBase} mb-0.5 pr-8 ${
                      onWorkspace && view === "chat" && convId === c.id ? itemActive : itemRest
                    }`}
                  >
                    <span className="block truncate">{c.title ?? "Untitled"}</span>
                  </Link>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      setConfirmDeleteId(c.id);
                    }}
                    title="Delete conversation"
                    aria-label={`Delete conversation ${c.title ?? "Untitled"}`}
                    className="absolute top-1/2 right-2 -translate-y-1/2 rounded-sm px-1 text-ink-faint opacity-0 group-hover:opacity-100 hover:text-danger focus-visible:opacity-100"
                  >
                    ✕
                  </button>
                </>
              )}
            </div>
          ))}
        </nav>

        <div className="space-y-2 border-t border-line px-5 py-4">
          <p className="data text-ink-muted uppercase">
            {tenant.plan} · {tenant.seats} seats · {tenant.role}
          </p>
          {tenant.trial_ends_at && (
            <p className="data text-warn">
              Trial ends {new Date(tenant.trial_ends_at).toLocaleDateString("en-GB")}
            </p>
          )}
          <p className="truncate text-xs text-ink-muted">{ws.email}</p>
          <button onClick={ws.logout} className="text-xs text-ink-muted underline hover:text-ink">
            Sign out
          </button>
        </div>
      </aside>
    </>
  );
}
