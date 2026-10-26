"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { HomeIcon, PulseIcon, TargetIcon } from "@/components/icons";
import { PRODUCT_LANGUAGE } from "@/lib/product-language";
import {
  ALL_PROJECTS_PATH,
  effectiveKind,
  projectPagePath,
  projectStatus,
} from "@/lib/projects";
import { href, item, itemActive, itemRest, navLabel } from "./sidebar-chats";
import NewProjectForm from "./new-project-form";
import { useWorkspace } from "./workspace";

/** One icon per kind. A kind without an entry here falls back to the general
 *  project's icon — a new kind still renders, it just looks generic. */
const KIND_ICONS: Record<string, () => React.ReactNode> = {
  general: () => <HomeIcon />,
  development: () => <PulseIcon />,
};

export function KindIcon({ kind }: { kind: string }) {
  return (KIND_ICONS[kind] ?? KIND_ICONS.general)();
}

/** How many projects the sidebar lists before "All N projects" takes over.
 *  The list is most recently updated first, so these are the live ones. */
export const SIDEBAR_PROJECT_CAP = 8;

/** The one Projects list (docs/project-types-brief.md §5): every project,
 *  whatever its kind, most recently updated first (the API's order). Each row
 *  opens its kind's home — the scoped chat, or the project room. */
export default function SidebarProjects({
  view,
  projectId,
  pathname,
  onWorkspace,
  onClose,
}: {
  view: "chat" | "vault";
  projectId: string | null;
  pathname: string;
  onWorkspace: boolean;
  onClose: () => void;
}) {
  const ws = useWorkspace();
  const router = useRouter();
  const [adding, setAdding] = useState(false);
  const viewParam = view === "vault" ? ("vault" as const) : undefined;
  const portfolioOn = ws.tenant?.features?.projects === true;
  const live = ws.projects.filter((p) => !p.archived);
  // Past the cap, keep the open project listed even if it is an old one —
  // the row that says where you are must not vanish.
  const shown = live.filter(
    (p, i) =>
      i < SIDEBAR_PROJECT_CAP || p.id === projectId || pathname.startsWith(projectPagePath(p.id))
  );

  function onCreated(id: string) {
    setAdding(false);
    router.push(href({ view: viewParam, project: id }));
    onClose();
  }

  return (
    <>
      <div className={navLabel}>
        Projects
        {portfolioOn && (
          <Link
            href="/app/projects"
            aria-current={pathname === "/app/projects" ? "page" : undefined}
            aria-label={`${PRODUCT_LANGUAGE.groundwork.function} portfolio`}
            className={`ml-auto shrink-0 text-xs font-bold normal-case tracking-normal ${
              pathname === "/app/projects"
                ? "text-electric-blue"
                : "text-subtle hover:text-electric-blue"
            }`}
          >
            Portfolio
          </Link>
        )}
        {/* "+ New", like the Chats heading — "+ New project" wrapped onto two
            lines beside Portfolio. The label keeps the full name. */}
        <button
          onClick={(e) => {
            e.stopPropagation();
            setAdding(true);
          }}
          aria-label="New project"
          title="New project"
          className={`${portfolioOn ? "" : "ml-auto"} shrink-0 text-xs font-bold normal-case tracking-normal text-electric-blue hover:underline`}
        >
          + New
        </button>
      </div>
      <Link
        href={href({ view: viewParam })}
        aria-current={onWorkspace && projectId === null ? "true" : undefined}
        className={`${item} mb-0.5 ${onWorkspace && projectId === null ? itemActive : itemRest}`}
      >
        <TargetIcon />
        {PRODUCT_LANGUAGE.projects.all}
      </Link>
      {shown.map((p) => {
        const kind = effectiveKind(p, ws.projectKinds);
        const inRoom = kind.home === "room";
        const target = inRoom ? projectPagePath(p.id) : href({ view: viewParam, project: p.id });
        const onPage = pathname.startsWith(projectPagePath(p.id));
        const active = onPage || (onWorkspace && projectId === p.id);
        const note = projectStatus(p, kind);
        return (
          <Link
            key={p.id}
            href={target}
            aria-current={active ? (onPage ? "page" : "true") : undefined}
            aria-label={`${p.name}, ${kind.label}, ${note}`}
            title={`${kind.label} · ${note}`}
            className={`${item} mb-0.5 ${active ? itemActive : itemRest}`}
          >
            <KindIcon kind={kind.key} />
            <span className="truncate">{p.name}</span>
            <span className="ml-auto shrink-0 text-xs font-semibold text-faint">{note}</span>
          </Link>
        );
      })}
      {(live.length > shown.length || ws.projects.length > live.length) && (
        <Link
          href={ALL_PROJECTS_PATH}
          aria-current={pathname === ALL_PROJECTS_PATH ? "page" : undefined}
          className={`${item} mb-0.5 ${pathname === ALL_PROJECTS_PATH ? itemActive : itemRest}`}
        >
          <span className="ml-6 text-xs font-bold text-electric-blue">
            {live.length > shown.length
              ? `All ${live.length} projects →`
              : "All projects, including archived →"}
          </span>
        </Link>
      )}
      {adding && (
        <NewProjectForm
          onCreated={onCreated}
          onCancel={() => setAdding(false)}
          onLeave={onClose}
        />
      )}
    </>
  );
}
