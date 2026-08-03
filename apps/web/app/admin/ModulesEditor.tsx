"use client";

import { useState } from "react";
import { ApiError } from "@/lib/api";
import { AdminTenantRow, FEATURE_FLAGS, updateFeatures } from "@/lib/admin";
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
  const [flags, setFlags] = useState<Record<string, boolean>>(
    Object.fromEntries(FEATURE_FLAGS.map((f) => [f.key, tenant.features[f.key] === true])),
  );
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const changed = FEATURE_FLAGS.filter((f) => flags[f.key] !== (tenant.features[f.key] === true));

  async function save() {
    if (!changed.length) return onClose();
    setSaving(true);
    setError(null);
    try {
      await updateFeatures(
        tenant.id,
        Object.fromEntries(changed.map((f) => [f.key, flags[f.key]])),
      );
      onSaved();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not save — try again.");
      setSaving(false);
    }
  }

  const withdrawn = changed.filter((f) => !flags[f.key]);

  return (
    <Panel title={`Modules — ${tenant.name}`} onClose={onClose}>
      <div className="flex flex-col gap-3">
        {error && (
          <p className="rounded-[10px] bg-danger-soft px-3 py-2 text-sm text-danger">{error}</p>
        )}
        <div className="flex flex-col gap-1.5">
          {FEATURE_FLAGS.map((f) => (
            <label key={f.key} className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={flags[f.key]}
                onChange={(e) => setFlags({ ...flags, [f.key]: e.target.checked })}
              />
              {f.label}
            </label>
          ))}
        </div>
        {withdrawn.length > 0 && (
          <p className="rounded-[10px] bg-card px-3 py-2 text-sm text-ink-muted">
            Switching off {withdrawn.map((f) => f.label).join(" and ")} hides it from the
            workspace immediately. Nothing is deleted — their data returns if you switch it
            back on.
          </p>
        )}
        <div className="mt-1 flex items-center gap-3">
          <button
            onClick={save}
            disabled={saving || !changed.length}
            className="rounded-[10px] bg-accent px-4 py-2 text-sm font-medium text-accent-ink hover:bg-accent-deep disabled:opacity-50"
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
