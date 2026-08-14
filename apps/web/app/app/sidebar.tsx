"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import {
  ChatIcon,
  FormIcon,
  GrantIcon,
  HomeIcon,
  PeopleIcon,
  PulseIcon,
  SealIcon,
  SearchIcon,
  TargetIcon,
  VaultIcon,
} from "@/components/icons";
import { claimsWaiting, claimsWaitingLabel } from "@/lib/claims";
import SidebarChats, { href, item, itemActive, itemRest, navLabel } from "./sidebar-chats";
import NewProjectForm from "./new-project-form";
import { useWorkspace } from "./workspace";

export default function Sidebar({ open, onClose }: { open: boolean; onClose: () => void }) {
  const ws = useWorkspace();
  const router = useRouter();
  const pathname = usePathname();
  const sp = useSearchParams();
  const [addingProject, setAddingProject] = useState(false);

  const tenant = ws.tenant;
  if (!tenant) return null;

  const view = sp.get("view") === "vault" ? "vault" : "chat";
  const projectId = sp.get("project");
  const convId = sp.get("c");
  const onWorkspace = pathname === "/app";
  const onDevPages = pathname.startsWith("/app/projects");

  // What the register is waiting on. A fact only gets updated if somebody is
  // told it has gone off before they need it, and this is the one place that is
  // in front of them without their having gone looking.
  const claims = ws.claimSummary;
  const claimsCount = claims ? claimsWaiting(claims) : 0;
  const claimsNote = claims ? claimsWaitingLabel(claims) : null;

  const devProjects = tenant.features?.projects === true
    ? ws.projects.filter((p) => !p.archived && p.is_development)
    : [];
  const coreProjects = ws.projects.filter((p) => !p.archived && !p.is_development);

  // Time-dependent by design: trial countdown and chat date groups may be a
  // render stale at worst — they refresh on any navigation.
  // eslint-disable-next-line react-hooks/purity
  const now = Date.now();
  const trialDaysLeft = tenant.trial_ends_at
    ? Math.max(0, Math.ceil((new Date(tenant.trial_ends_at).getTime() - now) / 86_400_000))
    : null;

  async function onProjectCreated(id: string) {
    setAddingProject(false);
    router.push(href({ view: view === "vault" ? "vault" : undefined, project: id }));
    onClose();
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
              Flowgrid
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
          {/* Unflagged: a workspace answering a funder's form may have any
              module, or none. */}
          <Link
            href="/app/forms"
            className={`${item} mt-0.5 ${
              pathname.startsWith("/app/forms") ? itemActive : itemRest
            }`}
          >
            <FormIcon />
            Funder forms
          </Link>
          {/* Unflagged for the same reason, and one more: this is the spine
              every module reads its organisation facts from, so gating it on
              any one of them would hide a workspace's own facts from the rest. */}
          <Link
            href="/app/claims"
            aria-label={claimsNote ? `Your organisation — ${claimsNote}` : undefined}
            className={`${item} mt-0.5 ${
              pathname.startsWith("/app/claims") ? itemActive : itemRest
            }`}
          >
            <SealIcon />
            Your organisation
            {claimsCount > 0 && (
              // Warn colours only when something has actually gone off. A pile
              // of proposals is an opportunity, not a fault, and colouring the
              // two the same is how a warning stops being read.
              <span
                title={claimsNote ?? undefined}
                className={`ml-auto rounded-full px-1.5 py-px text-[10.5px] font-bold ${
                  claims && claims.needs_attention > 0
                    ? "bg-warn-soft text-warn"
                    : "bg-accent-soft text-accent-deep"
                }`}
              >
                {claimsCount}
              </span>
            )}
          </Link>
          {tenant.features?.contacts === true && (
            <Link
              href="/app/contacts"
              className={`${item} mt-0.5 ${
                pathname.startsWith("/app/contacts") ? itemActive : itemRest
              }`}
            >
              <PeopleIcon />
              Contacts
            </Link>
          )}

          {tenant.features?.grants === true && (
            <Link
              href="/app/grants"
              className={`${item} mt-0.5 ${
                pathname.startsWith("/app/grants") ? itemActive : itemRest
              }`}
            >
              <GrantIcon />
              Grant funding
            </Link>
          )}

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
                {p.has_plan && p.open_task_count > 0
                  ? `${p.open_task_count} · ${p.document_count}`
                  : p.document_count}
              </span>
            </Link>
          ))}
          {addingProject && (
            <NewProjectForm
              onCreated={onProjectCreated}
              onCancel={() => setAddingProject(false)}
            />
          )}

          <SidebarChats
            projectId={projectId}
            convId={convId}
            view={view}
            onWorkspace={onWorkspace}
          />
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
