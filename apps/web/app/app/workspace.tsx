"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
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
  updated_at: string;
};

type WorkspaceState = {
  loading: boolean;
  email: string | null;
  tenant: Tenant | null;
  memberships: MembershipRef[] | null;
  projects: Project[];
  conversations: Conversation[];
  error: string | null;
  setError: (e: string | null) => void;
  selectTenant: (tenantId?: string) => Promise<void>;
  createTenant: (name: string) => Promise<void>;
  createProject: (name: string) => Promise<Project | null>;
  refreshProjects: () => Promise<void>;
  refreshConversations: () => Promise<void>;
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
  const [memberships, setMemberships] = useState<MembershipRef[] | null>(null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [error, setError] = useState<string | null>(null);

  const loadProjects = useCallback(async (tenantId: string) => {
    try {
      setProjects(await api<Project[]>("/projects", {}, tenantId));
    } catch {
      /* project list failing must not take down the workspace */
    }
  }, []);

  const loadConversations = useCallback(async (tenantId: string) => {
    try {
      setConversations(await api<Conversation[]>("/conversations", {}, tenantId));
    } catch {
      /* conversation list failing must not take down the workspace */
    }
  }, []);

  const selectTenant = useCallback(
    async (tenantId?: string) => {
      try {
        const me = await api<Tenant>("/tenants/me", {}, tenantId);
        setTenant(me);
        setMemberships(null);
        setError(null);
        // Groundwork pages read the tenant from localStorage, so persist it
        // even when it was resolved by sole-membership fallback.
        localStorage.setItem("tenantId", me.id);
        await Promise.all([loadProjects(me.id), loadConversations(me.id)]);
      } catch (e) {
        if (e instanceof ApiError && e.code === "tenant_required") {
          const list = (e.payload as { memberships?: MembershipRef[] })?.memberships ?? [];
          setMemberships(list);
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
        memberships,
        projects,
        conversations,
        error,
        setError,
        selectTenant,
        createTenant,
        createProject,
        refreshProjects,
        refreshConversations,
        logout,
      }}
    >
      {children}
    </WorkspaceContext.Provider>
  );
}
