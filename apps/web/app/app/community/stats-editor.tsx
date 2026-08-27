"use client";

// One figure about the place. A stat that names a fact kind feeds "Your
// organisation" on every save — the form says so before it happens, because a
// side effect somebody only discovers afterwards reads as a bug.

import { useEffect, useMemo, useState } from "react";
import { Spinner } from "@/components/activity";
import { btnPrimary as btn, btnQuiet as btnGhost, input } from "@/components/ui/styles";
import { ClaimKind, listClaimKinds } from "@/lib/claims";
import { CommunityStat, createCommunityStat, updateCommunityStat } from "@/lib/community";

export function StatsEditor({
  existing,
  onCancel,
  onSaved,
}: {
  existing: CommunityStat | null;
  onCancel: () => void;
  onSaved: (fedRegister: boolean) => void;
}) {
  const [kinds, setKinds] = useState<ClaimKind[]>([]);
  const [label, setLabel] = useState(existing?.label ?? "");
  const [value, setValue] = useState(existing ? String(existing.value) : "");
  const [unit, setUnit] = useState(existing?.unit ?? "");
  const [period, setPeriod] = useState(existing?.period ?? "");
  const [asOf, setAsOf] = useState(existing?.as_of ?? "");
  const [claimKind, setClaimKind] = useState(existing?.claim_kind ?? "");
  const [source, setSource] = useState(existing?.source ?? "");
  const [sourceUrl, setSourceUrl] = useState(existing?.source_url ?? "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listClaimKinds()
      .then(setKinds)
      // The picker degrades to "just a figure"; the form still works.
      .catch((e) => console.error("Failed to load claim kinds", e));
  }, []);

  const communityKinds = useMemo(
    () => kinds.filter((k) => k.category === "community"),
    [kinds],
  );
  const chosenKind = communityKinds.find((k) => k.key === claimKind) ?? null;

  async function save() {
    const n = Number(value.replace(/,/g, ""));
    if (!label.trim() || !Number.isFinite(n)) return;
    setBusy(true);
    setError(null);
    const body = {
      label: label.trim(),
      value: n,
      unit: unit.trim() || null,
      period: period.trim() || null,
      as_of: asOf || null,
      claim_kind: claimKind || null,
      source: source.trim() || null,
      source_url: sourceUrl.trim() || null,
    };
    try {
      const saved = existing
        ? await updateCommunityStat(existing.id, body)
        : await createCommunityStat(body);
      onSaved(saved.claim_id !== null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form
      className="space-y-3"
      onSubmit={(e) => {
        e.preventDefault();
        void save();
      }}
    >
      <div className="grid gap-3 sm:grid-cols-2">
        <label className="block text-sm">
          What it measures
          <input
            required
            value={label}
            onChange={(e) => setLabel(e.target.value)}
            placeholder="e.g. Usual residents"
            className={`${input} mt-1`}
          />
        </label>
        <label className="block text-sm">
          Value
          <input
            required
            type="number"
            step="any"
            value={value}
            onChange={(e) => setValue(e.target.value)}
            placeholder="494"
            className={`${input} mt-1`}
          />
        </label>
        <label className="block text-sm">
          Unit
          <input
            value={unit}
            onChange={(e) => setUnit(e.target.value)}
            placeholder="e.g. people, households, %"
            className={`${input} mt-1`}
          />
        </label>
        <label className="block text-sm">
          Period
          <input
            value={period}
            onChange={(e) => setPeriod(e.target.value)}
            placeholder="e.g. 2022"
            className={`${input} mt-1`}
          />
        </label>
        <label className="block text-sm">
          As of
          <input
            type="date"
            value={asOf}
            onChange={(e) => setAsOf(e.target.value)}
            className={`${input} mt-1`}
          />
        </label>
        <label className="block text-sm">
          Feeds a fact
          <select
            value={claimKind}
            onChange={(e) => setClaimKind(e.target.value)}
            className={`${input} mt-1`}
          >
            <option value="">— just a figure here</option>
            {communityKinds.map((k) => (
              <option key={k.key} value={k.key}>
                {k.label}
              </option>
            ))}
          </select>
        </label>
      </div>
      {chosenKind && (
        <p className="rounded-card bg-accent-soft px-3 py-2 text-xs">
          Each save asserts this in Your organisation as “{chosenKind.label}”, so drafts and
          funder forms read the current figure.
        </p>
      )}

      <div className="grid gap-3 sm:grid-cols-2">
        <label className="block text-sm">
          Source
          <input
            value={source}
            onChange={(e) => setSource(e.target.value)}
            placeholder="e.g. Scotland's Census 2022"
            className={`${input} mt-1`}
          />
        </label>
        <label className="block text-sm">
          Source link
          <input
            value={sourceUrl}
            onChange={(e) => setSourceUrl(e.target.value)}
            placeholder="https://…"
            className={`${input} mt-1`}
          />
        </label>
      </div>

      {error && (
        <p className="rounded-card bg-danger-soft px-3 py-2 text-sm text-danger">{error}</p>
      )}

      <div className="flex items-center gap-3">
        <button type="submit" disabled={busy || !label.trim() || !value.trim()} className={btn}>
          {busy ? <Spinner /> : existing ? "Save changes" : "Add the figure"}
        </button>
        <button type="button" onClick={onCancel} className={btnGhost}>
          Cancel
        </button>
      </div>
    </form>
  );
}
