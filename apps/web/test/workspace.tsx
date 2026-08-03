import { WorkspaceContext, type WorkspaceState } from "@/app/app/workspace";

/** A loaded, unremarkable workspace. Tests override only what they assert on,
 *  so adding a field to WorkspaceState does not touch every test. */
const BASE: WorkspaceState = {
  loading: false,
  email: "member@example.com",
  tenant: null,
  suspended: false,
  memberships: null,
  projects: [],
  conversations: [],
  conversationsLoaded: true,
  error: null,
  setError: () => {},
  selectTenant: async () => {},
  createTenant: async () => {},
  createProject: async () => null,
  refreshProjects: async () => {},
  refreshConversations: async () => {},
  refreshTenant: async () => {},
  logout: async () => {},
};

export function workspaceState(overrides: Partial<WorkspaceState> = {}): WorkspaceState {
  return { ...BASE, ...overrides };
}

/** Mount `ui` inside a workspace context. */
export function withWorkspace(
  ui: React.ReactNode,
  overrides: Partial<WorkspaceState> = {}
) {
  return (
    <WorkspaceContext.Provider value={workspaceState(overrides)}>
      {ui}
    </WorkspaceContext.Provider>
  );
}
