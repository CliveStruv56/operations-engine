// Project kinds and add-ons (docs/project-types-brief.md). The API's registry
// (apps/api/app/projects/kinds.py) is the source of truth: GET /project-kinds
// says which kinds and add-ons this workspace can use, and the sidebar and the
// new-project picker are built from it. A new kind needs no change here beyond
// an icon — an unknown kind falls back to the general kind's behaviour.

import { api } from "@/lib/api";
import { STAGE_LABEL } from "@/lib/groundwork";

export type ProjectKind = {
  key: string;
  label: string;
  description: string;
  /** Where clicking a project of this kind goes. */
  home: "chat" | "room";
  /** "inline": created by the new-project form. "setup": the module's own page. */
  create: "inline" | "setup";
  upgrades_to: string[];
  available: boolean;
};

export type ProjectAddOn = {
  key: string;
  label: string;
  description: string;
  available: boolean;
};

export type ProjectKinds = { kinds: ProjectKind[]; addons: ProjectAddOn[] };

export const GENERAL_KIND: ProjectKind = {
  key: "general",
  label: "General project",
  description: "Chat and documents, with an optional plan of tasks.",
  home: "chat",
  create: "inline",
  upgrades_to: ["development"],
  available: true,
};

/** Until /project-kinds answers, and if it fails: only the core kind, which
 *  needs no module and always exists. */
export const CORE_KINDS: ProjectKinds = { kinds: [GENERAL_KIND], addons: [] };

/** Accept whatever the endpoint returned without trusting its shape — a
 *  mocked or failing response must leave the sidebar working, not blank. */
export function parseProjectKinds(raw: unknown): ProjectKinds {
  const body = raw as Partial<ProjectKinds> | null;
  if (!body || !Array.isArray(body.kinds) || body.kinds.length === 0) return CORE_KINDS;
  return { kinds: body.kinds, addons: Array.isArray(body.addons) ? body.addons : [] };
}

/** The kind a project behaves as: its own while that kind's module is on, the
 *  general kind otherwise (module switched off, or a kind this client does not
 *  know). Switching a module off must never lose a project from the list. */
export function effectiveKind(
  project: { kind?: string; kind_available?: boolean },
  kinds: ProjectKinds
): ProjectKind {
  const own = kinds.kinds.find((k) => k.key === project.kind);
  if (own && project.kind_available !== false) return own;
  return kinds.kinds.find((k) => k.key === GENERAL_KIND.key) ?? GENERAL_KIND;
}

/** A project's one-line status: the stage for a development project, open
 *  plan tasks or documents otherwise. */
export function projectStatus(
  project: {
    stage_current: string | null;
    has_plan: boolean;
    open_task_count: number;
    document_count: number;
  },
  kind: ProjectKind
): string {
  if (kind.key === "development" && project.stage_current) {
    return STAGE_LABEL[project.stage_current] ?? project.stage_current;
  }
  if (project.has_plan && project.open_task_count > 0) {
    return `${project.open_task_count} task${project.open_task_count === 1 ? "" : "s"}`;
  }
  return `${project.document_count} doc${project.document_count === 1 ? "" : "s"}`;
}

/** Where a kind created by its module's own page ("setup") is set up. A setup
 *  kind missing from this map is not offered in the picker — better hidden
 *  than a card that leads nowhere. */
export const SETUP_PATHS: Record<string, string> = {
  development: "/app/projects/new",
};

/** Every project's own page: the development room for a development
 *  project, the core page (overview, documents, add-on tabs) for the rest.
 *  It is the home of a `home: "room"` kind; a chat-home kind links to it. */
export function projectPagePath(projectId: string): string {
  return `/app/projects/${projectId}`;
}

/** The full, filterable list of projects — the sidebar shows only the most
 *  recent few and links here for the rest. */
export const ALL_PROJECTS_PATH = "/app/projects/all";

/** A setup kind this project may become, with where to set it up. Kinds
 *  whose module is off, or with no setup page, are left out. */
export function upgradeTargets(
  project: { kind?: string; kind_available?: boolean },
  kinds: ProjectKinds
): { kind: ProjectKind; path: string }[] {
  const from = effectiveKind(project, kinds);
  return from.upgrades_to.flatMap((key) => {
    const kind = kinds.kinds.find((k) => k.key === key && k.available);
    const path = SETUP_PATHS[key];
    return kind && path ? [{ kind, path }] : [];
  });
}

/** One module as the catalogue describes it: the flag, its label, and the
 *  kinds and add-ons it supplies. `enabled` is present on a workspace's own
 *  list (GET /modules), absent on the operator's (GET /admin/modules). */
export type ModuleEntry = {
  flag: string;
  label: string;
  kinds: { key: string; label: string }[];
  addons: string[];
  enabled?: boolean;
};

export const listWorkspaceModules = (tenantId: string) =>
  api<ModuleEntry[]>("/modules", {}, tenantId);

/** One line on what switching a module on adds. */
export function moduleAdds(m: ModuleEntry): string | null {
  const parts = [
    ...m.kinds.map((k) => `the ${k.label} kind`),
    ...m.addons.map((a) => `a ${a} tab on every project`),
  ];
  return parts.length ? `Adds ${parts.join(" and ")}` : null;
}
