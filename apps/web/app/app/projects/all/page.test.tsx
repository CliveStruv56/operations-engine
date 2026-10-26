import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { routerMock } from "@/vitest.setup";
import { withWorkspace } from "@/test/workspace";
import { GENERAL_KIND, type ProjectKinds } from "@/lib/projects";
import type { Project } from "../../workspace";

let search = "";
vi.mock("next/navigation", async () => ({
  useRouter: () => routerMock,
  useSearchParams: () => new URLSearchParams(search),
  usePathname: () => "/app/projects/all",
}));

const { default: AllProjectsPage } = await import("./page");

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
    updated_at: "2026-10-26T10:00:00Z",
    ...over,
  }) as Project;

const PROJECTS = [
  project({ id: "g1", name: "Hall refit" }),
  project({ id: "d1", name: "Orchard Lane", kind: "development", stage_current: "site" }),
  project({ id: "a1", name: "Old fete", archived: true }),
];

function mount() {
  render(withWorkspace(<AllProjectsPage />, { projects: PROJECTS, projectKinds: KINDS }));
}

describe("all projects", () => {
  beforeEach(() => {
    search = "";
  });

  it("lists live projects of every kind, each opening its kind's home", () => {
    mount();
    expect(screen.getByRole("link", { name: "Hall refit" })).toHaveAttribute(
      "href",
      "/app?project=g1"
    );
    expect(screen.getByRole("link", { name: "Orchard Lane" })).toHaveAttribute(
      "href",
      "/app/projects/d1"
    );
    expect(screen.queryByText("Old fete")).toBeNull();
  });

  it("filters by kind through the URL", async () => {
    mount();
    await userEvent.click(screen.getByRole("button", { name: "Development projects" }));
    expect(routerMock.replace).toHaveBeenCalledWith("/app/projects/all?kind=development");
  });

  it("shows only the chosen kind, and archived projects on request", () => {
    search = "kind=general&archived=1";
    mount();
    expect(screen.getByRole("link", { name: "Old fete" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Orchard Lane" })).toBeNull();
    expect(screen.getByRole("button", { name: "General projects" })).toHaveAttribute(
      "aria-pressed",
      "true"
    );
  });
});
