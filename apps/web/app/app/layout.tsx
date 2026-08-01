"use client";

import { Suspense, useState } from "react";
import CommandPalette from "./command-palette";
import Sidebar from "./sidebar";
import { useWorkspace, WorkspaceProvider } from "./workspace";

function Onboarding() {
  const ws = useWorkspace();
  const [newName, setNewName] = useState("");

  return (
    <main className="flex min-h-screen items-center justify-center p-6">
      <div className="w-full max-w-md">
        <p className="data mb-2 text-ink-faint uppercase">Operations Engine</p>
        {ws.error && (
          <p className="mb-4 rounded-sm bg-danger-soft px-3 py-2 text-sm text-danger">
            {ws.error}
          </p>
        )}

        {ws.memberships && ws.memberships.length > 0 ? (
          <section className="rounded-md border border-line bg-surface p-6 shadow-sm">
            <h1 className="text-xl font-semibold tracking-tight">Choose a workspace</h1>
            <div className="mt-4 divide-y divide-line border-y border-line">
              {ws.memberships.map((m) => (
                <button
                  key={m.tenant_id}
                  onClick={() => ws.selectTenant(m.tenant_id)}
                  className="flex w-full items-center justify-between px-1 py-3 text-left hover:bg-accent-soft"
                >
                  <span className="font-medium">{m.name}</span>
                  <span className="data text-ink-muted uppercase">{m.role}</span>
                </button>
              ))}
            </div>
          </section>
        ) : (
          <section className="rounded-md border border-line bg-surface p-6 shadow-sm">
            <h1 className="text-xl font-semibold tracking-tight">Set up your workspace</h1>
            <p className="mt-1 text-sm text-ink-muted">
              Your team&apos;s documents and conversations live here.
            </p>
            <form
              onSubmit={(e) => {
                e.preventDefault();
                ws.createTenant(newName);
              }}
              className="mt-5 space-y-3"
            >
              <input
                required
                placeholder="Company name"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                className="w-full rounded-sm border border-line bg-surface px-3 py-2 text-sm"
              />
              <button
                type="submit"
                className="w-full rounded-sm bg-accent px-4 py-2 text-sm font-medium text-accent-ink hover:opacity-90"
              >
                Create workspace
              </button>
            </form>
          </section>
        )}
      </div>
    </main>
  );
}

function WorkspaceShell({ children }: { children: React.ReactNode }) {
  const ws = useWorkspace();
  const [navOpen, setNavOpen] = useState(false);

  if (ws.loading) {
    return (
      <main className="flex min-h-screen items-center justify-center">
        <p className="data text-ink-faint">Loading workspace…</p>
      </main>
    );
  }

  if (!ws.tenant) return <Onboarding />;

  // Hearth: app chrome is fixed platform-wide — the tenant accent appears
  // only in the logo area and exported artefacts (slides, health cards).
  return (
    <div className="flex h-screen flex-col md:flex-row">
      <header className="flex shrink-0 items-center gap-3 border-b border-edge bg-sidebar px-4 py-2.5 md:hidden">
        <button
          onClick={() => setNavOpen(true)}
          aria-label="Open navigation"
          className="rounded-sm border border-line px-2 py-1 text-sm"
        >
          ☰
        </button>
        <span className="truncate text-sm font-semibold">{ws.tenant.name}</span>
      </header>
      <Sidebar open={navOpen} onClose={() => setNavOpen(false)} />
      <CommandPalette />
      <div className="flex min-h-0 min-w-0 flex-1 flex-col bg-canvas">
        {ws.error && (
          <p className="border-b border-line bg-danger-soft px-6 py-2 text-sm text-danger">
            {ws.error}
          </p>
        )}
        {children}
      </div>
    </div>
  );
}

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <WorkspaceProvider>
      <Suspense fallback={null}>
        <WorkspaceShell>{children}</WorkspaceShell>
      </Suspense>
    </WorkspaceProvider>
  );
}
