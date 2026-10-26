"use client";

import { useState } from "react";
import Link from "next/link";
import { Stamp } from "@/components/ui";
import { btnSecondary } from "@/components/ui/styles";
import { ALL_PROJECTS_PATH, effectiveKind } from "@/lib/projects";
import ProjectPlanPanel from "../../project-plan";
import { href } from "../../sidebar-chats";
import { useWorkspace, type Project } from "../../workspace";
import { TabStrip, useAddonTabs } from "./addon-tabs";
import ChangeKind from "./change-kind";
import { ProjectDocumentsTab } from "./tabs/ProjectDocumentsTab";

/** The project page for every kind without a room of its own — a general
 *  project, or a development project while its module is off. Core tabs
 *  first, then the add-ons (docs/project-types-brief.md §5.1). */
export default function CoreProjectPage({ project }: { project: Project }) {
  const ws = useWorkspace();
  const addons = useAddonTabs();
  const [tab, setTab] = useState("Overview");
  const kind = effectiveKind(project, ws.projectKinds);
  // A stored kind whose module is switched off: say what is hidden, and
  // that nothing is lost, rather than silently showing less.
  const sleeping = project.kind !== kind.key;
  // /project-kinds lists switched-off kinds too, so the label is there.
  const storedLabel =
    ws.projectKinds.kinds.find((k) => k.key === project.kind)?.label ?? project.kind;
  const tabs = ["Overview", "Documents", ...addons.map((a) => a.label)];
  const addon = addons.find((a) => a.label === tab);

  return (
    <main className="min-h-0 flex-1 overflow-y-auto">
      <div className="mx-auto max-w-6xl p-6">
        <p className="data text-ink-faint uppercase">
          <Link href={ALL_PROJECTS_PATH} className="hover:text-ink">
            ← All projects
          </Link>
        </p>
        <header className="mt-1 mb-4 flex flex-wrap items-end justify-between gap-3">
          <div className="min-w-0">
            <h1 className="font-display text-[26px] font-medium tracking-[-0.01em]">
              {project.name}
            </h1>
            <p className="mt-0.5 flex items-center gap-2 text-sm text-ink-muted">
              {kind.label}
              {project.archived && <Stamp>Archived</Stamp>}
            </p>
          </div>
          <div className="flex items-center gap-3">
            <Link href={href({ project: project.id })} className={btnSecondary}>
              Chat about this project
            </Link>
            <ChangeKind project={project} />
          </div>
        </header>

        {sleeping && (
          <p className="mb-3 rounded-card bg-warn-soft px-3 py-2 text-sm text-warn">
            This is a {storedLabel.toLowerCase()}. Its own parts are hidden while that module is
            switched off for this workspace. Nothing has been deleted — they come back when it is
            switched on again.
          </p>
        )}

        <TabStrip tabs={tabs} current={tab} onSelect={setTab} />

        {tab === "Overview" && (
          <div className="flex flex-col gap-5">
            <p className="max-w-2xl text-sm text-ink-muted">
              {project.description || "No description yet."}
            </p>
            {/* A development project keeps its stage-based tasks while asleep;
                a plan beside them would be stranded when the module returns. */}
            {!project.is_development && (
              <ProjectPlanPanel projectId={project.id} hasPlan={project.has_plan} />
            )}
          </div>
        )}
        {tab === "Documents" && <ProjectDocumentsTab id={project.id} />}
        {addon?.render(project.id)}
      </div>
    </main>
  );
}
