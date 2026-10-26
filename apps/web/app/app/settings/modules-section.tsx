"use client";

// "Your modules": which modules this workspace has and what each adds, so an
// admin can see why a kind is missing from the new-project picker or a tab
// from a project page. Read-only by design — modules are switched on and off
// by the operator (ASSUMPTIONS #22), so there is nothing here to click.

import { useEffect, useState } from "react";
import { Stamp } from "@/components/ui";
import { cardPadded as card } from "@/components/ui/styles";
import { type ModuleEntry, listWorkspaceModules, moduleAdds } from "@/lib/projects";

export default function ModulesSection({ tenantId }: { tenantId: string }) {
  const [modules, setModules] = useState<ModuleEntry[] | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    listWorkspaceModules(tenantId)
      .then(setModules)
      .catch((err) => {
        console.error("Failed to load the workspace's modules", err);
        setFailed(true);
      });
  }, [tenantId]);

  return (
    <section className={card}>
      <h2 className="data mb-1 text-ink-muted uppercase">Your modules</h2>
      <p className="mb-3 text-sm text-ink-muted">
        Every workspace has projects, chat and documents; modules add to them. Your platform
        provider switches modules on and off.
      </p>
      {failed && <p className="text-sm text-danger">Your modules couldn&rsquo;t be loaded.</p>}
      {modules && (
        <ul className="divide-y divide-line">
          {modules.map((m) => {
            const adds = moduleAdds(m);
            return (
              <li key={m.flag} className="flex items-start justify-between gap-3 py-2.5">
                <span className="min-w-0 text-sm">
                  {m.label}
                  {adds && <span className="block text-xs text-ink-muted">{adds}</span>}
                </span>
                {m.enabled ? <Stamp tone="accent">On</Stamp> : <Stamp>Off</Stamp>}
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
