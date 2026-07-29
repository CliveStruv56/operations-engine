"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase/client";
import { api, ApiError } from "@/lib/api";
import ChatPanel from "./chat";
import VaultPanel from "./vault";

type Tenant = {
  id: string;
  name: string;
  plan: string;
  seats: number;
  trial_ends_at: string | null;
  role: string;
};

type MembershipRef = { tenant_id: string; name: string; role: string };

export default function WorkspacePage() {
  const router = useRouter();
  const [email, setEmail] = useState<string | null>(null);
  const [tenant, setTenant] = useState<Tenant | null>(null);
  const [memberships, setMemberships] = useState<MembershipRef[] | null>(null);
  const [newName, setNewName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<"chat" | "vault">("chat");

  const loadTenant = useCallback(async (tenantId?: string) => {
    try {
      const me = await api<Tenant>("/tenants/me", {}, tenantId);
      setTenant(me);
      setMemberships(null);
      setError(null);
      if (tenantId) localStorage.setItem("tenantId", tenantId);
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
  }, []);

  useEffect(() => {
    const supabase = createClient();
    supabase.auth.getUser().then(({ data }) => setEmail(data.user?.email ?? null));
    // Fetch-on-mount: every setState in loadTenant happens after an await.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    loadTenant(localStorage.getItem("tenantId") ?? undefined);
  }, [loadTenant]);

  async function createTenant(e: React.FormEvent) {
    e.preventDefault();
    try {
      const created = await api<{ id: string }>("/tenants", {
        method: "POST",
        body: JSON.stringify({ name: newName }),
      });
      await loadTenant(created.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  async function logout() {
    await createClient().auth.signOut();
    localStorage.removeItem("tenantId");
    router.push("/login");
    router.refresh();
  }

  if (loading) {
    return <main className="p-8 text-neutral-500">Loading…</main>;
  }

  return (
    <main className="mx-auto max-w-3xl p-8 space-y-6">
      <header className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">
          {tenant ? tenant.name : "Operations Engine"}
        </h1>
        <div className="flex items-center gap-3 text-sm text-neutral-600">
          {email && <span>{email}</span>}
          <button onClick={logout} className="underline">
            Sign out
          </button>
        </div>
      </header>

      {error && <p className="text-sm text-red-600">{error}</p>}

      {tenant && (
        <section className="rounded border border-neutral-200 p-4 text-sm space-y-1">
          <p>
            Plan: <strong>{tenant.plan}</strong> · Seats: {tenant.seats} · Your
            role: {tenant.role}
          </p>
          {tenant.trial_ends_at && (
            <p className="text-neutral-500">
              Trial ends {new Date(tenant.trial_ends_at).toLocaleDateString()}
            </p>
          )}
        </section>
      )}

      {tenant && (
        <>
          <nav className="flex gap-1 border-b border-neutral-200 text-sm">
            {(["chat", "vault"] as const).map((t) => (
              <button
                key={t}
                onClick={() => setTab(t)}
                className={`rounded-t px-4 py-2 capitalize ${
                  tab === t
                    ? "border border-b-0 border-neutral-200 bg-white font-medium"
                    : "text-neutral-500 hover:text-neutral-800"
                }`}
              >
                {t}
              </button>
            ))}
          </nav>
          {tab === "chat" ? (
            <ChatPanel tenantId={tenant.id} />
          ) : (
            <VaultPanel tenantId={tenant.id} />
          )}
        </>
      )}

      {memberships && memberships.length > 0 && (
        <section className="space-y-2">
          <h2 className="font-medium">Choose a workspace</h2>
          {memberships.map((m) => (
            <button
              key={m.tenant_id}
              onClick={() => {
                setLoading(true);
                loadTenant(m.tenant_id);
              }}
              className="block w-full rounded border border-neutral-200 p-3 text-left hover:bg-neutral-50"
            >
              {m.name} <span className="text-sm text-neutral-500">({m.role})</span>
            </button>
          ))}
        </section>
      )}

      {memberships && memberships.length === 0 && (
        <form onSubmit={createTenant} className="space-y-3">
          <h2 className="font-medium">Create your workspace</h2>
          <input
            required
            placeholder="Company name"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            className="w-full rounded border border-neutral-300 px-3 py-2"
          />
          <button
            type="submit"
            className="rounded bg-neutral-900 px-4 py-2 text-white"
          >
            Create workspace
          </button>
        </form>
      )}
    </main>
  );
}
