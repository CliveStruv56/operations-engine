import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import SidebarProjects, { SIDEBAR_PROJECT_CAP } from "./sidebar-projects";
import type { Project, Tenant } from "./workspace";
import { withWorkspace } from "@/test/workspace";
import { GENERAL_KIND, type ProjectKinds } from "@/lib/projects";

const TENANT = {
  id: "t1",
  name: "Riverside Community Trust",
  features: { projects: true },
  role: "owner",
} as unknown as Tenant;

const KINDS: ProjectKinds = {
  kinds: [
    GENERAL_KIND,
    {
      key: "development",
      label: "Development project",
      description: "A stage-gated housing scheme.",
      home: "room",
      create: "setup",
      upgrades_to: [],
      available: true,
    },
  ],
  addons: [],
};

const project = (over: Partial<Project>): Project =>
  ({
    id: "p",
    name: "Project",
    description: null,
    archived: false,
    document_count: 0,
    kind: "general",
    kind_available: true,
    stage_current: null,
    is_development: false,
    has_plan: false,
    open_task_count: 0,
    ...over,
  }) as Project;

function mount(
  projects: Project[],
  kinds: ProjectKinds = KINDS,
  { projectId = null, pathname = "/app" }: { projectId?: string | null; pathname?: string } = {}
) {
  render(
    withWorkspace(
      <nav>
        <SidebarProjects
          view="chat"
          projectId={projectId}
          pathname={pathname}
          onWorkspace
          onClose={() => {}}
        />
      </nav>,
      { tenant: TENANT, projects, projectKinds: kinds }
    )
  );
}

describe("the one Projects list", () => {
  it("lists every kind in one section, each opening its kind's home", () => {
    mount([
      project({ id: "g1", name: "Hall refit", document_count: 3 }),
      project({
        id: "d1",
        name: "Orchard Lane",
        kind: "development",
        is_development: true,
        stage_current: "site",
      }),
    ]);

    const general = screen.getByRole("link", { name: /Hall refit, General project, 3 docs/ });
    expect(general).toHaveAttribute("href", "/app?project=g1");

    // A development project opens its room, and says which stage it is in.
    const dev = screen.getByRole("link", { name: /Orchard Lane, Development project, Site/ });
    expect(dev).toHaveAttribute("href", "/app/projects/d1");

    // No second "Development projects" section, and no ↗ side door.
    expect(screen.queryByText(/^Development projects$/)).toBeNull();
    expect(screen.queryByText("↗")).toBeNull();
  });

  it("keeps a switched-off module's projects, as general projects", () => {
    mount([
      project({
        id: "d1",
        name: "Orchard Lane",
        kind: "development",
        kind_available: false,
        is_development: true,
        stage_current: "site",
      }),
    ]);
    const row = screen.getByRole("link", { name: /Orchard Lane, General project/ });
    expect(row).toHaveAttribute("href", "/app?project=d1");
  });

  it("treats a kind this client does not know as a general project", () => {
    mount([project({ id: "x1", name: "Future thing", kind: "tender" })]);
    expect(screen.getByRole("link", { name: /Future thing, General project/ })).toHaveAttribute(
      "href",
      "/app?project=x1"
    );
  });

  it("hides archived projects and counts open plan tasks", () => {
    mount([
      project({ id: "a1", name: "Old", archived: true }),
      project({ id: "p1", name: "Planned", has_plan: true, open_task_count: 2 }),
    ]);
    expect(screen.queryByRole("link", { name: /^Old/ })).toBeNull();
    const planned = screen.getByRole("link", { name: /Planned, General project, 2 tasks/ });
    expect(within(planned).getByText("2 tasks")).toBeInTheDocument();
  });
});

describe("a long Projects list", () => {
  const many = Array.from({ length: SIDEBAR_PROJECT_CAP + 2 }, (_, i) =>
    project({ id: `p${i}`, name: `Scheme ${i}` })
  );

  it("shows the most recent few and links to the rest", () => {
    mount(many);
    expect(screen.getByRole("link", { name: /^Scheme 0, / })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /^Scheme 9, / })).toBeNull();
    expect(
      screen.getByRole("link", { name: `All ${SIDEBAR_PROJECT_CAP + 2} projects →` })
    ).toHaveAttribute("href", "/app/projects/all");
  });

  it("keeps the open project listed even when it is past the cap", () => {
    mount(many, KINDS, { projectId: "p9" });
    expect(screen.getByRole("link", { name: /^Scheme 9, / })).toHaveAttribute(
      "aria-current",
      "true"
    );
  });

  it("marks a general project current while its project page is open", () => {
    mount([project({ id: "g1", name: "Hall refit" })], KINDS, {
      pathname: "/app/projects/g1",
    });
    expect(screen.getByRole("link", { name: /^Hall refit, / })).toHaveAttribute(
      "aria-current",
      "page"
    );
  });

  it("links to archived projects through the full list", () => {
    mount([project({ id: "a1", name: "Old", archived: true })]);
    expect(
      screen.getByRole("link", { name: "All projects, including archived →" })
    ).toHaveAttribute("href", "/app/projects/all");
  });
});
