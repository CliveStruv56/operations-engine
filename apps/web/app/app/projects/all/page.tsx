"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Stamp } from "@/components/ui";
import { fmtDate } from "@/lib/groundwork";
import { effectiveKind, projectPagePath, projectStatus } from "@/lib/projects";
import { th } from "@/components/ui/styles";
import { href } from "../../sidebar-chats";
import { KindIcon } from "../../sidebar-projects";
import { useWorkspace } from "../../workspace";

/** Every project in the workspace, filterable by kind — the full list the
 *  sidebar's capped one links to (docs/project-types-brief.md §9, phase 2).
 *  The filter lives in the URL (`?kind=`, `?archived=1`) so a filtered view
 *  can be linked to. */
export default function AllProjectsPage() {
  const ws = useWorkspace();
  const router = useRouter();
  const pathname = usePathname();
  const sp = useSearchParams();
  const kindFilter = sp.get("kind");
  const showArchived = sp.get("archived") === "1";

  const rows = ws.projects.map((p) => ({ project: p, kind: effectiveKind(p, ws.projectKinds) }));
  // Offer a chip only for kinds this workspace actually has projects of.
  const kindsInUse = ws.projectKinds.kinds.filter((k) => rows.some((r) => r.kind.key === k.key));
  const visible = rows.filter(
    (r) =>
      (showArchived || !r.project.archived) && (kindFilter === null || r.kind.key === kindFilter)
  );

  function setParam(key: string, value: string | null) {
    const q = new URLSearchParams(sp.toString());
    if (value === null) q.delete(key);
    else q.set(key, value);
    const s = q.toString();
    router.replace(s ? `${pathname}?${s}` : pathname);
  }

  const chip = (active: boolean) =>
    `rounded-full border px-3 py-1 text-xs font-semibold ${
      active
        ? "border-deep-violet bg-lavender-mist text-deep-violet"
        : "border-edge-ui text-subtle hover:text-ink"
    }`;

  return (
    <main className="min-h-0 flex-1 overflow-y-auto">
      <div className="mx-auto max-w-6xl p-6">
        <h1 className="font-display text-[26px] font-medium tracking-[-0.01em]">All projects</h1>
        <p className="mt-0.5 text-sm text-ink-muted">Most recently updated first.</p>

        <div className="mt-4 mb-4 flex flex-wrap items-center gap-2">
          <div role="group" aria-label="Filter by kind" className="flex flex-wrap gap-2">
            <button
              onClick={() => setParam("kind", null)}
              aria-pressed={kindFilter === null}
              className={chip(kindFilter === null)}
            >
              All kinds
            </button>
            {kindsInUse.map((k) => (
              <button
                key={k.key}
                onClick={() => setParam("kind", k.key)}
                aria-pressed={kindFilter === k.key}
                className={chip(kindFilter === k.key)}
              >
                {k.label}s
              </button>
            ))}
          </div>
          <label className="ml-auto flex items-center gap-2 text-sm text-ink-muted">
            <input
              type="checkbox"
              checked={showArchived}
              onChange={(e) => setParam("archived", e.target.checked ? "1" : null)}
              className="accent-(--accent)"
            />
            Show archived
          </label>
        </div>

        {visible.length === 0 ? (
          <p className="rounded-card border border-edge bg-surface p-6 text-sm text-ink-muted">
            {ws.projects.length === 0
              ? "No projects yet. Start one with “+ New project” in the sidebar."
              : "No projects match this filter."}
          </p>
        ) : (
          <div className="overflow-x-auto rounded-card border border-edge bg-surface">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-line">
                  <th className={th}>Project</th>
                  <th className={th}>Kind</th>
                  <th className={th}>Status</th>
                  <th className={th}>Updated</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {visible.map(({ project: p, kind }) => (
                  <tr key={p.id} className={p.archived ? "bg-band text-ink-muted" : ""}>
                    <td className="px-4 py-3 font-medium">
                      <span className="flex items-center gap-2">
                        <KindIcon kind={kind.key} />
                        <Link
                          href={
                            kind.home === "room"
                              ? projectPagePath(p.id)
                              : href({ project: p.id })
                          }
                          className="hover:text-electric-blue hover:underline"
                        >
                          {p.name}
                        </Link>
                        {p.archived && <Stamp>Archived</Stamp>}
                      </span>
                      {kind.home === "chat" && (
                        <Link
                          href={projectPagePath(p.id)}
                          className="ml-6 text-xs font-semibold text-electric-blue hover:underline"
                        >
                          Project page
                        </Link>
                      )}
                    </td>
                    <td className="px-4 py-3 text-ink-muted">{kind.label}</td>
                    <td className="px-4 py-3 text-ink-muted">{projectStatus(p, kind)}</td>
                    <td className="data px-4 py-3 text-ink-faint">{fmtDate(p.updated_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </main>
  );
}
