import Link from "next/link";
import { projectPagePath } from "@/lib/projects";
import type { Project } from "../workspace";

/** Keeps the project scope visible once a conversation is underway — the
 *  empty-state hero carries it before then. */
export default function ScopeBanner({ project }: { project: Project }) {
  return (
    <p className="flex items-center gap-3 border-b border-edge bg-sidebar px-6 py-1.5 text-xs font-bold text-subtle">
      <span className="min-w-0 truncate">
        Project: {project.name} — answers prefer this project&apos;s documents
      </span>
      <Link
        href={projectPagePath(project.id)}
        className="ml-auto shrink-0 text-electric-blue hover:underline"
      >
        Project page
      </Link>
    </p>
  );
}
