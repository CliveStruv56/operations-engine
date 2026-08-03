"use client";

import Link from "next/link";
import { useWorkspace } from "./workspace";

/**
 * Client-side half of a module's feature gate.
 *
 * The API already 404s every route of a module the tenant has not bought
 * (`app/modules.py::make_feature_gate`), but a page that only handles the
 * happy path renders that 404 as a raw error string — which reads as a bug
 * rather than "you don't have this". The workspace already carries
 * `tenant.features`, so the page can decide before it fetches anything.
 *
 * Returns `undefined` while the workspace is still loading, so callers can
 * tell "not enabled" apart from "don't know yet" and avoid flashing the
 * disabled state at every page load.
 */
export function useModuleEnabled(flag: string): boolean | undefined {
  const ws = useWorkspace();
  if (ws.loading || !ws.tenant) return undefined;
  return ws.tenant.features?.[flag] === true;
}

/**
 * What a member sees where a module they do not have would be. Deliberately
 * plain: this is a workspace that has not bought the module, not an error,
 * and there is nothing for the member to fix — enabling it is an operator
 * action.
 */
export function ModuleDisabled({ title, blurb }: { title: string; blurb: string }) {
  return (
    <main className="min-h-0 flex-1 overflow-y-auto p-8">
      <div className="mx-auto max-w-xl rounded-card border border-edge bg-surface p-6">
        <h1 className="font-display text-[20px] font-medium tracking-[-0.01em]">{title}</h1>
        <p className="mt-2 text-sm text-ink-muted">{blurb}</p>
        <Link href="/app" className="mt-4 inline-block text-sm text-ink-muted underline hover:text-ink">
          Back to your workspace
        </Link>
      </div>
    </main>
  );
}

export const PROJECTS_DISABLED = {
  title: "Development projects aren't switched on",
  blurb:
    "This workspace doesn't have the development projects module. Ask whoever provides your workspace to enable it.",
} as const;
