"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
} from "react";
import { useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase/client";
import { api, ApiError } from "@/lib/api";

export type Tenant = {
  id: string;
  name: string;
  plan: string;
  seats: number;
  brand: Record<string, unknown>;
  features: Record<string, unknown>;
  trial_ends_at: string | null;
  role: string;
  logo_url: string | null;
};

export type MembershipRef = { tenant_id: string; name: string; role: string };

export type Project = {
  id: string;
  name: string;
  description: string | null;
  archived: boolean;
  document_count: number;
  is_development: boolean;
};

export type Conversation = {
  id: string;
  title: string | null;
  project_id: string | null;
  visibility: "private" | "tenant";
  is_mine: boolean;
  owner_email: string | null;
  updated_at: string;
};

type WorkspaceState = {
  loading: boolean;
  email: string | null;
  tenant: Tenant | null;
  /** The selected workspace is suspended. Distinct from "no tenant": the
   *  member has one, they just cannot use it, so offering them the
   *  create-a-workspace onboarding would be wrong. */
  suspended: boolean;
  memberships: MembershipRef[] | null;
  projects: Project[];
  conversations: Conversation[];
  /** False until a /conversations fetch has succeeded — an empty list alone
   *  cannot tell "no chats" apart from "the fetch failed". */
  conversationsLoaded: boolean;
  error: string | null;
  setError: (e: string | null) => void;
  selectTenant: (tenantId?: string) => Promise<void>;
  createTenant: (name: string) => Promise<void>;
  createProject: (name: string) => Promise<Project | null>;
  refreshProjects: () => Promise<void>;
  refreshConversations: () => Promise<void>;
  refreshTenant: () => Promise<void>;
  logout: () => Promise<void>;
};

const WorkspaceContext = createContext<WorkspaceState | null>(null);

export function useWorkspace(): WorkspaceState {
  const ctx = useContext(WorkspaceContext);
  if (!ctx) throw new Error("useWorkspace must be used inside WorkspaceProvider");
  return ctx;
}

export function WorkspaceProvider({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [email, setEmail] = useState<string | null>(null);
  const [tenant, setTenant] = useState<Tenant | null>(null);
  const [suspended, setSuspended] = useState(false);
  const [memberships, setMemberships] = useState<MembershipRef[] | null>(null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [conversationsLoaded, setConversationsLoaded] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // A failing list must not take down the workspace, but it should be visible:
  // log it and surface a non-fatal banner instead of leaving the sidebar blank.
  const loadProjects = useCallback(async (tenantId: string) => {
    try {
      setProjects(await api<Project[]>("/projects", {}, tenantId));
    } catch (err) {
      console.error("Failed to load projects", err);
      setError("Couldn't load your projects — refresh to try again.");
    }
  }, []);

  const loadConversations = useCallback(async (tenantId: string) => {
    try {
      setConversations(await api<Conversation[]>("/conversations", {}, tenantId));
      setConversationsLoaded(true);
    } catch (err) {
      console.error("Failed to load conversations", err);
      // Consumers must be able to tell "you have no chats" from "we don't
      // know what you have" — the composer's read-only guard depends on it.
      setConversationsLoaded(false);
      setError("Couldn't load your conversations — refresh to try again.");
    }
  }, []);

  const selectTenant = useCallback(
    async (tenantId?: string) => {
      try {
        const me = await api<Tenant>("/tenants/me", {}, tenantId);
        setTenant(me);
        setMemberships(null);
        setSuspended(false);
        setError(null);
        // Groundwork pages read the tenant from localStorage, so persist it
        // even when it was resolved by sole-membership fallback.
        localStorage.setItem("tenantId", me.id);
        await Promise.all([loadProjects(me.id), loadConversations(me.id)]);
      } catch (e) {
        if (e instanceof ApiError && e.code === "tenant_required") {
          const list = (e.payload as { memberships?: MembershipRef[] })?.memberships ?? [];
          setMemberships(list);
        } else if (e instanceof ApiError && e.code === "tenant_suspended") {
          // Not an error state to recover from in-app — the shell renders a
          // dedicated screen, so no red banner on top of it.
          setSuspended(true);
          setTenant(null);
          setError(null);
        } else {
          setError(e instanceof Error ? e.message : String(e));
        }
      } finally {
        setLoading(false);
      }
    },
    [loadProjects, loadConversations]
  );

  useEffect(() => {
    const supabase = createClient();
    supabase.auth.getUser().then(({ data }) => setEmail(data.user?.email ?? null));
    // Fetch-on-mount: every setState in selectTenant happens after an await.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    selectTenant(localStorage.getItem("tenantId") ?? undefined);
  }, [selectTenant]);

  const createTenant = useCallback(
    async (name: string) => {
      try {
        const created = await api<{ id: string }>("/tenants", {
          method: "POST",
          body: JSON.stringify({ name }),
        });
        await selectTenant(created.id);
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
      }
    },
    [selectTenant]
  );

  const createProject = useCallback(
    async (name: string): Promise<Project | null> => {
      if (!tenant) return null;
      try {
        const created = await api<Project>(
          "/projects",
          { method: "POST", body: JSON.stringify({ name }) },
          tenant.id
        );
        await loadProjects(tenant.id);
        return created;
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
        return null;
      }
    },
    [tenant, loadProjects]
  );

  const refreshProjects = useCallback(async () => {
    if (tenant) await loadProjects(tenant.id);
  }, [tenant, loadProjects]);

  const refreshConversations = useCallback(async () => {
    if (tenant) await loadConversations(tenant.id);
  }, [tenant, loadConversations]);

  const refreshTenant = useCallback(async () => {
    if (tenant) await selectTenant(tenant.id);
  }, [tenant, selectTenant]);

  // Refetch on tab focus so tenant-shared data (projects, shared chats)
  // converges after a teammate changes something. Targeted refreshers only —
  // refreshTenant re-runs selectTenant and would flash error/picker state.
  const lastFocusRefetch = useRef(0);
  useEffect(() => {
    function onVisible() {
      if (document.visibilityState !== "visible") return;
      if (Date.now() - lastFocusRefetch.current < 20_000) return;
      lastFocusRefetch.current = Date.now();
      refreshProjects();
      refreshConversations();
    }
    document.addEventListener("visibilitychange", onVisible);
    return () => document.removeEventListener("visibilitychange", onVisible);
  }, [refreshProjects, refreshConversations]);

  const logout = useCallback(async () => {
    await createClient().auth.signOut();
    localStorage.removeItem("tenantId");
    router.push("/login");
    router.refresh();
  }, [router]);

  return (
    <WorkspaceContext.Provider
      value={{
        loading,
        email,
        tenant,
        suspended,
        memberships,
        projects,
        conversations,
        conversationsLoaded,
        error,
        setError,
        selectTenant,
        createTenant,
        createProject,
        refreshProjects,
        refreshConversations,
        refreshTenant,
        logout,
      }}
    >
      {children}
    </WorkspaceContext.Provider>
  );
}
