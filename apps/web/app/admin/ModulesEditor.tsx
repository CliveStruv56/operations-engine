"use client";

import { useEffect, useState } from "react";
import { ApiError } from "@/lib/api";
import {
  AdminModule,
  AdminTenantRow,
  FALLBACK_MODULES,
  listModules,
  moduleAdds,
  updateFeatures,
} from "@/lib/admin";
import { Panel } from "@/components/Panel";

/** Turn modules on or off for a live workspace. Only the flags that actually
 *  changed are sent — the API merges, so an untouched module is never
 *  disturbed by a stale copy of the row. */
export function ModulesEditor({
  tenant,
  onClose,
  onSaved,
}: {
  tenant: AdminTenantRow;
  onClose: () => void;
  onSaved: () => void;
}) {
  // Only the boxes the operator has touched; the rest read the tenant's row.
  const [flags, setFlags] = useState<Record<string, boolean>>({});
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [modules, setModules] = useState<AdminModule[]>(FALLBACK_MODULES);

  useEffect(() => {
    listModules()
      .then((m) => setModules(m))
      .catch(() => setModules(FALLBACK_MODULES));
  }, []);

  // Driven by the API's module list, not the hand-mirrored FEATURE_FLAGS, so
  // a module the console has never heard of is still saved and warned about.
  const isOn = (flag: string) => flags[flag] ?? tenant.features[flag] === true;
  const changed = modules.filter((m) => isOn(m.flag) !== (tenant.features[m.flag] === true));

  async function save() {
    if (!changed.length) return onClose();
    setSaving(true);
    setError(null);
    try {
      await updateFeatures(
        tenant.id,
        Object.fromEntries(changed.map((m) => [m.flag, isOn(m.flag)])),
      );
      onSaved();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not save — try again.");
      setSaving(false);
    }
  }

  const withdrawn = changed.filter((m) => !isOn(m.flag));
  // What happens to the workspace's projects, said in numbers: a module that
  // supplies a kind leaves its projects in the list as general projects.
  const fallbackNotes = withdrawn.flatMap((m) =>
    m.kinds.map((k) => {
      const n = tenant.project_counts?.[k.key] ?? 0;
      return `${n} ${k.label.toLowerCase()}${n === 1 ? "" : "s"} will stay in the Projects list as general projects, with ${m.label} parts hidden`;
    }),
  );

  return (
    <Panel title={`Modules — ${tenant.name}`} onClose={onClose}>
      <div className="flex flex-col gap-3">
        {error && (
          <p className="rounded-card bg-danger-soft px-3 py-2 text-sm text-danger">{error}</p>
        )}
        <div className="flex flex-col gap-1.5">
          {modules.map((m) => {
            const adds = moduleAdds(m);
            return (
              <label key={m.flag} className="flex items-start gap-2 text-sm">
                <input
                  type="checkbox"
                  className="mt-1"
                  checked={isOn(m.flag)}
                  onChange={(e) => setFlags({ ...flags, [m.flag]: e.target.checked })}
                />
                <span>
                  {m.label}
                  {adds && <span className="block text-xs text-ink-muted">{adds}</span>}
                </span>
              </label>
            );
          })}
        </div>
        {withdrawn.length > 0 && (
          <p className="rounded-card bg-card px-3 py-2 text-sm text-ink-muted">
            Switching off {withdrawn.map((m) => m.label).join(" and ")} takes effect
            immediately.{" "}
            {fallbackNotes.length > 0 && <>{fallbackNotes.join("; ")}. </>}
            Nothing is deleted — everything returns if you switch it back on.
          </p>
        )}
        <div className="mt-1 flex items-center gap-3">
          <button
            onClick={save}
            disabled={saving || !changed.length}
            className="rounded-btn bg-accent px-4 py-2 text-sm font-medium text-accent-ink hover:bg-accent-deep disabled:opacity-50"
          >
            {changed.length ? "Save modules" : "No changes"}
          </button>
          <button
            onClick={onClose}
            className="ml-auto text-xs text-ink-muted underline hover:text-ink"
          >
            Cancel
          </button>
        </div>
      </div>
    </Panel>
  );
}
