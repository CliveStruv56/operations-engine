"use client";

import { useState } from "react";
import { ApiError } from "@/lib/api";
import { AdminTenantCreated, FEATURE_FLAGS, admin, inviteUrl } from "@/lib/admin";
import { Panel } from "@/components/Panel";

const input =
  "w-full rounded-[10px] border border-line bg-surface px-3 py-2 text-sm placeholder:text-ink-faint focus:outline-none focus:border-edge-strong";
const label = "data mb-1 block text-ink-muted uppercase";

export function NewWorkspace({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: (t: AdminTenantCreated) => void;
}) {
  const [name, setName] = useState("");
  const [ownerEmail, setOwnerEmail] = useState("");
  const [seats, setSeats] = useState(3);
  const [trialDays, setTrialDays] = useState(14);
  const [flags, setFlags] = useState<Record<string, boolean>>({});
  const [accent, setAccent] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  async function create(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      const created = await admin<AdminTenantCreated>("/admin/tenants", {
        method: "POST",
        body: JSON.stringify({
          name,
          owner_email: ownerEmail,
          seats,
          trial_days: trialDays,
          features: flags,
          brand_accent: accent || null,
        }),
      });
      onCreated(created);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong — try again.");
      setSaving(false);
    }
  }

  return (
    <Panel title="New client workspace" onClose={onClose}>
      <form onSubmit={create} className="flex flex-col gap-3">
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
            placeholder="Client organisation name"
            className={input}
          />
        </div>
        <div>
          <span className={label}>Owner email</span>
          <input
            required
            type="email"
            value={ownerEmail}
            onChange={(e) => setOwnerEmail(e.target.value)}
            placeholder="The client contact who will own the workspace"
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
            <span className={label}>Trial days</span>
            <input
              type="number"
              min={1}
              max={365}
              value={trialDays}
              onChange={(e) => setTrialDays(Number(e.target.value))}
              className={input}
            />
          </div>
        </div>
        <div>
          <span className={label}>Modules</span>
          <div className="flex flex-col gap-1.5">
            {FEATURE_FLAGS.map((f) => (
              <label key={f.key} className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={flags[f.key] === true}
                  onChange={(e) => setFlags({ ...flags, [f.key]: e.target.checked })}
                />
                {f.label}
              </label>
            ))}
          </div>
        </div>
        <div>
          <span className={label}>Export accent colour (optional)</span>
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
            disabled={saving}
            className="rounded-[10px] bg-accent px-4 py-2 text-sm font-medium text-accent-ink hover:bg-accent-deep disabled:opacity-50"
          >
            Create workspace
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

/** Post-create handoff: the invite link to send to the client. */
export function InviteLink({ invite, onDone }: { invite: AdminTenantCreated; onDone: () => void }) {
  const url = inviteUrl(invite.invite.token);
  const [copied, setCopied] = useState(false);
  return (
    <Panel title={`${invite.name} is ready`} onClose={onDone}>
      <p className="text-sm text-ink-muted">
        Send this invite link to <span className="font-medium text-ink">{invite.invite.email}</span>
        {" "}— accepting it makes them the workspace owner. The link expires{" "}
        {new Date(invite.invite.expires_at).toLocaleDateString("en-GB")}.
      </p>
      <div className="mt-3 flex items-center gap-2">
        <code className="data min-w-0 flex-1 truncate rounded-[10px] border border-edge bg-card px-3 py-2">
          {url}
        </code>
        <button
          onClick={() => {
            navigator.clipboard.writeText(url);
            setCopied(true);
          }}
          className="shrink-0 rounded-[10px] bg-accent px-3 py-2 text-sm font-medium text-accent-ink hover:bg-accent-deep"
        >
          {copied ? "Copied" : "Copy"}
        </button>
      </div>
    </Panel>
  );
}
