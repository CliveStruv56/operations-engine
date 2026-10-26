// Project kinds and add-ons (docs/project-types-brief.md). The API's registry
// (apps/api/app/projects/kinds.py) is the source of truth: GET /project-kinds
// says which kinds and add-ons this workspace can use, and the sidebar and the
// new-project picker are built from it. A new kind needs no change here beyond
// an icon — an unknown kind falls back to the general kind's behaviour.

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

/** Where a kind created by its module's own page ("setup") is set up. A setup
 *  kind missing from this map is not offered in the picker — better hidden
 *  than a card that leads nowhere. */
export const SETUP_PATHS: Record<string, string> = {
  development: "/app/projects/new",
};

/** The page that holds a project's room (`home: "room"`). */
export function roomPath(projectId: string): string {
  return `/app/projects/${projectId}`;
}
