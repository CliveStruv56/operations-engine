"use client";

import { useState } from "react";
import { ApiError } from "@/lib/api";
import {
  AdminTenantPatch,
  AdminTenantRow,
  PLANS,
  suspendTenant,
  updateTenant,
} from "@/lib/admin";
import { Panel } from "@/components/Panel";

const input =
  "w-full rounded-[10px] border border-line bg-surface px-3 py-2 text-sm placeholder:text-ink-faint focus:outline-none focus:border-edge-strong";
const label = "data mb-1 block text-ink-muted uppercase";

/** `2026-08-14T00:00:00Z` -> `2026-08-14` for <input type="date">. */
const toDateInput = (iso: string | null) => (iso ? iso.slice(0, 10) : "");

export function EditWorkspace({
  tenant,
  onClose,
  onSaved,
}: {
  tenant: AdminTenantRow;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [name, setName] = useState(tenant.name);
  const [seats, setSeats] = useState(tenant.seats);
  const [plan, setPlan] = useState(tenant.plan);
  const [trialEnds, setTrialEnds] = useState(toDateInput(tenant.trial_ends_at));
  const [accent, setAccent] = useState(String(tenant.brand?.accent ?? ""));
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  /** Only changed fields go to the API — see updateTenant. */
  function patch(): AdminTenantPatch {
    const p: AdminTenantPatch = {};
    if (name !== tenant.name) p.name = name;
    if (seats !== tenant.seats) p.seats = seats;
    if (plan !== tenant.plan) p.plan = plan;
    if (trialEnds !== toDateInput(tenant.trial_ends_at))
      p.trial_ends_at = trialEnds ? `${trialEnds}T00:00:00Z` : null;
    if (accent && accent !== tenant.brand?.accent) p.brand_accent = accent;
    return p;
  }

  const changed = Object.keys(patch()).length > 0;

  async function save(e: React.FormEvent) {
    e.preventDefault();
    if (!changed) return onClose();
    setSaving(true);
    setError(null);
    try {
      await updateTenant(tenant.id, patch());
      onSaved();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not save — try again.");
      setSaving(false);
    }
  }

  return (
    <Panel title={`Edit ${tenant.name}`} onClose={onClose}>
      <form onSubmit={save} className="flex flex-col gap-3">
        {error && (
          <p className="rounded-[10px] bg-danger-soft px-3 py-2 text-sm text-danger">{error}</p>
        )}
        <div>
          <span className={label}>Workspace name</span>
          <input
            required
            autoFocus
            value={name}
            onChange={(e) => setName(e.target.value)}
            className={input}
          />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <span className={label}>Seats</span>
            <input
              type="number"
              min={1}
              max={100}
              value={seats}
              onChange={(e) => setSeats(Number(e.target.value))}
              className={input}
            />
          </div>
          <div>
            <span className={label}>Plan</span>
            <select value={plan} onChange={(e) => setPlan(e.target.value)} className={input}>
              {PLANS.map((p) => (
                <option key={p} value={p}>
                  {p}
                </option>
              ))}
            </select>
          </div>
        </div>
        {seats !== tenant.seats && (
          <p className="rounded-[10px] bg-card px-3 py-2 text-sm text-ink-muted">
            Changing seats also moves this workspace&apos;s fair-use ceiling at the model
            gateway.
          </p>
        )}
        <div>
          <span className={label}>Trial ends</span>
          <input
            type="date"
            value={trialEnds}
            onChange={(e) => setTrialEnds(e.target.value)}
            className={input}
          />
          <p className="mt-1 text-xs text-ink-faint">Clear the date to remove the trial end.</p>
        </div>
        <div>
          <span className={label}>Export accent colour</span>
          <input
            value={accent}
            onChange={(e) => setAccent(e.target.value)}
            placeholder="#1f6d53 — used in exported slides & PDFs"
            pattern="^#[0-9a-fA-F]{6}$"
            className={input}
          />
        </div>
        <div className="mt-1 flex items-center gap-3">
          <button
            type="submit"
            disabled={saving || !changed}
            className="rounded-[10px] bg-accent px-4 py-2 text-sm font-medium text-accent-ink hover:bg-accent-deep disabled:opacity-50"
          >
            {changed ? "Save changes" : "No changes"}
          </button>
          <button
            type="button"
            onClick={onClose}
            className="ml-auto text-xs text-ink-muted underline hover:text-ink"
          >
            Cancel
          </button>
        </div>
      </form>
    </Panel>
  );
}

/** Suspension is reversible and deliberately not deletion — the copy has to
 *  say so, or an operator will expect this to remove the client's data. */
export function SuspendWorkspace({
  tenant,
  onClose,
  onDone,
}: {
  tenant: AdminTenantRow;
  onClose: () => void;
  onDone: () => void;
}) {
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  async function suspend(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      await suspendTenant(tenant.id, reason);
      onDone();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not suspend — try again.");
      setSaving(false);
    }
  }

  return (
    <Panel title={`Suspend ${tenant.name}`} onClose={onClose}>
      <form onSubmit={suspend} className="flex flex-col gap-3">
        {error && (
          <p className="rounded-[10px] bg-danger-soft px-3 py-2 text-sm text-danger">{error}</p>
        )}
        <p className="text-sm text-ink-muted">
          Everyone in this workspace loses access immediately, including chat, and it stops
          being able to spend at the model gateway.{" "}
          <span className="text-ink">Nothing is deleted</span> — documents, chats and projects
          all survive, and resuming restores the workspace exactly as it was.
        </p>
        <div>
          <span className={label}>Reason</span>
          <input
            required
            autoFocus
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="Shown in the console so the workspace is never dark without explanation"
            className={input}
          />
        </div>
        <div className="mt-1 flex items-center gap-3">
          <button
            type="submit"
            disabled={saving || !reason.trim()}
            className="rounded-[10px] bg-danger px-4 py-2 text-sm font-medium text-white hover:opacity-90 disabled:opacity-50"
          >
            Suspend workspace
          </button>
          <button
            type="button"
            onClick={onClose}
            className="ml-auto text-xs text-ink-muted underline hover:text-ink"
          >
            Cancel
          </button>
        </div>
      </form>
    </Panel>
  );
}
