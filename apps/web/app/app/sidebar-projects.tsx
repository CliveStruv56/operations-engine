"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { HomeIcon, PulseIcon, TargetIcon } from "@/components/icons";
import { STAGE_LABEL } from "@/lib/groundwork";
import { PRODUCT_LANGUAGE } from "@/lib/product-language";
import { effectiveKind, roomPath, type ProjectKind } from "@/lib/projects";
import { href, item, itemActive, itemRest, navLabel } from "./sidebar-chats";
import NewProjectForm from "./new-project-form";
import { useWorkspace, type Project } from "./workspace";

/** One icon per kind. A kind without an entry here falls back to the general
 *  project's icon — a new kind still renders, it just looks generic. */
const KIND_ICONS: Record<string, () => React.ReactNode> = {
  general: () => <HomeIcon />,
  development: () => <PulseIcon />,
};

function status(project: Project, kind: ProjectKind): string {
  if (kind.key === "development" && project.stage_current) {
    return STAGE_LABEL[project.stage_current] ?? project.stage_current;
  }
  if (project.has_plan && project.open_task_count > 0) {
    return `${project.open_task_count} task${project.open_task_count === 1 ? "" : "s"}`;
  }
  return `${project.document_count} doc${project.document_count === 1 ? "" : "s"}`;
}

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
            className={`ml-auto text-xs font-bold normal-case tracking-normal ${
              pathname === "/app/projects"
                ? "text-electric-blue"
                : "text-subtle hover:text-electric-blue"
            }`}
          >
            Portfolio
          </Link>
        )}
        <button
          onClick={(e) => {
            e.stopPropagation();
            setAdding(true);
          }}
          className={`${portfolioOn ? "ml-3" : "ml-auto"} text-xs font-bold normal-case tracking-normal text-electric-blue hover:underline`}
        >
          + New project
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
      {ws.projects
        .filter((p) => !p.archived)
        .map((p) => {
          const kind = effectiveKind(p, ws.projectKinds);
          const inRoom = kind.home === "room";
          const target = inRoom ? roomPath(p.id) : href({ view: viewParam, project: p.id });
          const active = inRoom
            ? pathname.startsWith(roomPath(p.id))
            : onWorkspace && projectId === p.id;
          const note = status(p, kind);
          return (
            <Link
              key={p.id}
              href={target}
              aria-current={active ? (inRoom ? "page" : "true") : undefined}
              aria-label={`${p.name}, ${kind.label}, ${note}`}
              title={`${kind.label} · ${note}`}
              className={`${item} mb-0.5 ${active ? itemActive : itemRest}`}
            >
              {(KIND_ICONS[kind.key] ?? KIND_ICONS.general)()}
              <span className="truncate">{p.name}</span>
              <span className="ml-auto shrink-0 text-xs font-semibold text-faint">{note}</span>
            </Link>
          );
        })}
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
