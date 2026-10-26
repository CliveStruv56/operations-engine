import { Suspense } from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { withWorkspace } from "@/test/workspace";
import { GENERAL_KIND, type ProjectKinds } from "@/lib/projects";
import type { Project, Tenant } from "../../workspace";

const gw = vi.fn();
vi.mock("@/lib/groundwork", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/groundwork")>()),
  gw: (...args: unknown[]) => gw(...args),
}));
// The plan panel fetches on mount; its own behaviour is tested elsewhere.
vi.mock("../../project-plan", () => ({ default: () => <div>Plan panel</div> }));

const { default: ProjectPage } = await import("./page");

const TENANT = {
  id: "t1",
  name: "Riverside Community Trust",
  features: { projects: true, grants: true },
  role: "owner",
} as unknown as Tenant;

const kinds = (developmentOn: boolean): ProjectKinds => ({
  kinds: [
    GENERAL_KIND,
    {
      key: "development",
      label: "Development project",
      description: "A stage-gated housing scheme.",
      home: "room",
      create: "setup",
      upgrades_to: [],
      available: developmentOn,
    },
  ],
  addons: [
    { key: "contacts", label: "Contacts", description: "", available: false },
    { key: "grants", label: "Grant applications", description: "", available: true },
  ],
});

const project = (over: Partial<Project>): Project =>
  ({
    id: "p1",
    name: "Hall refit",
    description: "New kitchen and accessible toilets.",
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

function mount(p: Project, projectKinds = kinds(true)) {
  render(
    withWorkspace(
      <Suspense fallback={null}>
        <ProjectPage params={Promise.resolve({ id: p.id })} />
      </Suspense>,
      { tenant: TENANT, projects: [p], projectKinds }
    )
  );
}

describe("the project page", () => {
  beforeEach(() => gw.mockReset());

  it("gives a general project core tabs and the add-ons that are on", async () => {
    mount(project({}));
    expect(await screen.findByRole("heading", { name: "Hall refit" })).toBeInTheDocument();
    const tabs = screen.getAllByRole("button").map((b) => b.textContent);
    expect(tabs).toEqual(
      expect.arrayContaining(["Overview", "Documents", "Grant applications"])
    );
    expect(tabs).not.toContain("Contacts");
    expect(screen.getByText("Plan panel")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Chat about this project" })).toHaveAttribute(
      "href",
      "/app?project=p1"
    );
    expect(gw).not.toHaveBeenCalled();
  });

  it("opens the development room for a development project", async () => {
    gw.mockReturnValue(new Promise(() => {}));
    mount(project({ kind: "development", is_development: true, stage_current: "site" }));
    expect(await screen.findByText("Loading project…")).toBeInTheDocument();
    expect(gw).toHaveBeenCalledWith("/projects/p1/groundwork");
  });

  it("keeps a development project usable, and says why, while its module is off", async () => {
    mount(
      project({ kind: "development", kind_available: false, is_development: true }),
      kinds(false)
    );
    expect(await screen.findByText(/This is a development project/)).toBeInTheDocument();
    expect(screen.getByText(/Nothing has been deleted/)).toBeInTheDocument();
    expect(gw).not.toHaveBeenCalled();
  });

  it("offers to make a general project a development project", async () => {
    mount(project({}));
    await userEvent.click(await screen.findByRole("button", { name: "Change kind" }));
    expect(screen.getByRole("link", { name: "Set it up →" })).toHaveAttribute(
      "href",
      "/app/projects/new?project=p1"
    );
  });

  it("explains why a project with a plan cannot become a development project", async () => {
    mount(project({ has_plan: true }));
    await userEvent.click(await screen.findByRole("button", { name: "Change kind" }));
    expect(screen.queryByRole("link", { name: "Set it up →" })).toBeNull();
    expect(screen.getByText(/This project has a plan/)).toBeInTheDocument();
  });

  it("offers no kind change when the development module is off", async () => {
    mount(project({}), kinds(false));
    await screen.findByRole("heading", { name: "Hall refit" });
    expect(screen.queryByRole("button", { name: "Change kind" })).toBeNull();
  });
});
