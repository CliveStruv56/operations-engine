"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ALL_PROJECTS_PATH, effectiveKind } from "@/lib/projects";
import { useWorkspace } from "../../workspace";
import DevelopmentRoom from "./development-room";
import CoreProjectPage from "./core-page";

/** Every project's page (docs/project-types-brief.md §5.1). A development
 *  project — while its module is on — gets the Groundwork room; every other
 *  project, a development one with the module off included, gets the core
 *  page. Both carry the add-on tabs. */
export default function ProjectPage({ id }: { id: string }) {
  const ws = useWorkspace();
  const project = ws.projects.find((p) => p.id === id) ?? null;
  // A project a teammate created after this session loaded its list is not in
  // it yet: refresh once before calling the link wrong.
  const [refreshed, setRefreshed] = useState(false);
  const { refreshProjects } = ws;

  useEffect(() => {
    if (project || refreshed) return;
    refreshProjects().finally(() => setRefreshed(true));
  }, [project, refreshed, refreshProjects]);

  if (!project) {
    if (!refreshed) return <main className="p-8 data text-ink-faint">Loading project…</main>;
    return (
      <main className="min-h-0 flex-1 overflow-y-auto p-8">
        <div className="mx-auto max-w-xl rounded-card border border-edge bg-surface p-6">
          <h1 className="font-display text-[20px] font-medium tracking-[-0.01em]">
            This project isn&rsquo;t here
          </h1>
          <p className="mt-2 text-sm text-ink-muted">
            It may have been deleted, or the link may be wrong.
          </p>
          <Link
            href={ALL_PROJECTS_PATH}
            className="mt-4 inline-block text-sm text-ink-muted underline hover:text-ink"
          >
            Back to all projects
          </Link>
        </div>
      </main>
    );
  }

  return effectiveKind(project, ws.projectKinds).key === "development" ? (
    <DevelopmentRoom id={id} />
  ) : (
    <CoreProjectPage project={project} />
  );
}
