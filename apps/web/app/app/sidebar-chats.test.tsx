import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import SidebarChats from "./sidebar-chats";
import type { Conversation, Project } from "./workspace";
import { withWorkspace } from "@/test/workspace";

const MEADOW = { id: "p1", name: "Milbrook Meadow" } as Project;

const chat = (over: Partial<Conversation>): Conversation => ({
  id: "c",
  title: "A chat",
  project_id: null,
  visibility: "private",
  is_mine: true,
  owner_email: null,
  updated_at: new Date().toISOString(),
  ...over,
});

const CHATS = [
  chat({ id: "c1", title: "Meadow drainage", project_id: "p1" }),
  chat({ id: "c2", title: "Unrelated question" }),
  chat({ id: "c3", title: "Team notes", project_id: "p1", is_mine: false }),
];

function mount(projectId: string | null, conversations = CHATS) {
  return render(
    withWorkspace(
      <SidebarChats projectId={projectId} convId={null} view="chat" onWorkspace />,
      { projects: [MEADOW], conversations }
    )
  );
}

describe("the sidebar chat list's scope", () => {
  it("names the selected project, so the filter is not silent", () => {
    // A bare "Recent" over a project's chats read as "these are all my chats".
    mount("p1");
    expect(screen.getByText(/^Chats in/)).toHaveTextContent("Chats in Milbrook Meadow");
    expect(screen.getByText(/^Shared in/)).toHaveTextContent("Shared in Milbrook Meadow");
    expect(screen.getByText("Meadow drainage")).toBeInTheDocument();
    expect(screen.queryByText("Unrelated question")).toBeNull();
  });

  it("says when every project's chats are shown", () => {
    mount(null);
    expect(screen.getByText(/^Chats in/)).toHaveTextContent("Chats in all projects");
    expect(screen.getByText("Unrelated question")).toBeInTheDocument();
  });

  it("keeps dates as sub-labels under one heading", () => {
    // "Recent — Earlier" as the first heading looked like a date filter.
    mount(null);
    expect(screen.getAllByText(/^Chats in/)).toHaveLength(1);
    expect(screen.getByText("Today")).toBeInTheDocument();
  });

  it("names the project when it has no chats yet", () => {
    mount("p1", []);
    expect(screen.getByText("No chats in Milbrook Meadow yet")).toBeInTheDocument();
  });
});
