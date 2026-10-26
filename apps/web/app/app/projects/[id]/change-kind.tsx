"use client";

import { useState } from "react";
import Link from "next/link";
import { btnSecondary } from "@/components/ui/styles";
import { upgradeTargets } from "@/lib/projects";
import type { Project } from "../../workspace";
import { useWorkspace } from "../../workspace";

/** "Change kind": the kinds this project may become (the registry's
 *  `upgrades_to`, today general → development), each through its module's
 *  setup page with the project carried across. Nothing is offered when no
 *  target's module is on. */
export default function ChangeKind({ project }: { project: Project }) {
  const ws = useWorkspace();
  const [open, setOpen] = useState(false);
  const targets = upgradeTargets(project, ws.projectKinds);
  if (targets.length === 0) return null;

  return (
    <div className="relative">
      <button
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        aria-controls="change-kind-panel"
        className={btnSecondary}
      >
        Change kind
      </button>
      {open && (
        <div
          id="change-kind-panel"
          className="absolute right-0 z-10 mt-2 w-80 rounded-card border border-edge-ui bg-surface p-3 text-sm"
        >
          {targets.map(({ kind, path }) => {
            // A plan and a development project's stage-based task list are
            // mutually exclusive (ASSUMPTIONS #51); the API refuses with 409.
            const blocked = project.has_plan && kind.key === "development";
            return (
              <div key={kind.key} className="py-1">
                <p className="font-medium">Make it a {kind.label.toLowerCase()}</p>
                <p className="mt-0.5 text-xs text-ink-muted">{kind.description}</p>
                {blocked ? (
                  <p className="mt-1.5 text-xs text-ink-muted">
                    This project has a plan, so it can&rsquo;t become a{" "}
                    {kind.label.toLowerCase()} — that has its own stage-by-stage task list.
                  </p>
                ) : (
                  <>
                    <p className="mt-1.5 text-xs text-ink-muted">
                      Its chats, documents and links stay as they are.
                    </p>
                    <Link
                      href={`${path}?project=${project.id}`}
                      className="mt-2 inline-block text-sm font-semibold text-electric-blue hover:underline"
                    >
                      Set it up →
                    </Link>
                  </>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
