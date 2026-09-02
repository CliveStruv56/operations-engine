"use client";

import Link from "next/link";
import { Suspense, useState } from "react";
import CommandPalette from "./command-palette";
import Sidebar from "./sidebar";
import { ToastProvider } from "@/components/toast";
import { DialogProvider } from "@/components/ui";
import { useWorkspace, WorkspaceProvider } from "./workspace";

export function Onboarding() {
  const ws = useWorkspace();

  return (
    <main className="flex min-h-screen items-center justify-center p-6">
      <div className="w-full max-w-md">
        <p className="data mb-2 text-ink-faint uppercase">Flowgrid OS</p>
        {ws.error && (
          <p className="mb-4 rounded-card bg-danger-soft px-3 py-2 text-sm text-danger">
            {ws.error}
          </p>
        )}

        {ws.memberships && ws.memberships.length > 0 ? (
          <section className="rounded-card border border-edge bg-surface p-6 shadow-card">
            <h1 className="font-display text-[26px] font-medium tracking-[-0.01em]">Choose a workspace</h1>
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
          <section className="rounded-card border border-edge bg-surface p-6 shadow-card">
            <h1 className="font-display text-[26px] font-medium tracking-[-0.01em]">
              No workspace yet
            </h1>
            <p className="mt-2 text-sm leading-relaxed text-ink-muted">
              Flowgrid workspaces are set up by invitation. Open the invitation
              email sent to you, or contact us if you expected to have access.
            </p>
            <div className="mt-5 flex flex-wrap items-center gap-4">
              <Link
                href="/contact"
                className="rounded-btn bg-accent px-5 py-2.5 text-sm font-medium text-accent-ink hover:bg-accent-deep"
              >
                Contact Flowgrid
              </Link>
              <Link href="/" className="text-sm text-ink-muted underline hover:text-ink">
                Back to the website
              </Link>
              <button
                onClick={() => ws.logout()}
                className="text-sm text-ink-muted underline hover:text-ink"
              >
                Sign out
              </button>
            </div>
          </section>
        )}
      </div>
    </main>
  );
}

/** A suspended workspace is not a missing one. Falling through to Onboarding
 *  invited the member to create a second workspace, which is both confusing
 *  and the opposite of what suspension is for. */
function Suspended() {
  const ws = useWorkspace();
  return (
    <main className="flex min-h-screen items-center justify-center p-6">
      <div className="w-full max-w-md">
        <p className="data mb-2 text-ink-faint uppercase">Flowgrid</p>
        <section className="rounded-card border border-edge bg-surface p-6 shadow-card">
          <h1 className="font-display text-[26px] font-medium tracking-[-0.01em]">
            This workspace is suspended
          </h1>
          <p className="mt-2 text-sm text-ink-muted">
            Access is paused for everyone in it. Nothing has been deleted — your documents,
            chats and projects are all still here, and they come back as soon as it is
            reinstated. Contact whoever provides your workspace.
          </p>
          <div className="mt-5 flex items-center gap-4">
            <button
              onClick={() => {
                // Members of more than one workspace must not be stranded here.
                localStorage.removeItem("tenantId");
                ws.selectTenant();
              }}
              className="rounded-btn bg-accent px-4 py-2 text-sm font-medium text-accent-ink hover:bg-accent-deep"
            >
              Use a different workspace
            </button>
            <button
              onClick={() => ws.logout()}
              className="text-xs text-ink-muted underline hover:text-ink"
            >
              Sign out
            </button>
          </div>
        </section>
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

  if (ws.suspended) return <Suspended />;
  if (!ws.tenant) return <Onboarding />;

  // Hearth: app chrome is fixed platform-wide — the tenant accent appears
  // only in the logo area and exported artefacts (slides, health cards).
  return (
    <div className="flex h-screen flex-col md:flex-row">
      {/* The sidebar is a long run of links — module nav, then every project,
          then every recent chat. Without this, reaching the page itself by
          keyboard means tabbing past all of it on every navigation. */}
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:fixed focus:top-3 focus:left-3 focus:z-[70] focus:rounded-btn focus:bg-card focus:px-4 focus:py-2 focus:text-sm focus:font-semibold focus:text-electric-blue focus:shadow-card"
      >
        Skip to content
      </a>
      <header className="flex shrink-0 items-center gap-3 border-b border-edge bg-sidebar px-4 py-2.5 md:hidden">
        <button
          onClick={() => setNavOpen(true)}
          aria-label="Open navigation"
          className="rounded-card border border-line px-2 py-1 text-sm"
        >
          ☰
        </button>
        <span className="truncate text-sm font-semibold">{ws.tenant.name}</span>
      </header>
      <Sidebar open={navOpen} onClose={() => setNavOpen(false)} />
      <CommandPalette />
      <div
        id="main-content"
        tabIndex={-1}
        className="flex min-h-0 min-w-0 flex-1 flex-col bg-canvas focus:outline-none"
      >
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
      <ToastProvider>
        <DialogProvider>
          <Suspense fallback={null}>
            <WorkspaceShell>{children}</WorkspaceShell>
          </Suspense>
        </DialogProvider>
      </ToastProvider>
    </WorkspaceProvider>
  );
}
