"use client";

// One facility, any category. The details grid is free key/value pairs with
// per-category suggestions — the API stores short scalars, so "pupils: 68"
// and "nursery: yes" both land as typed values, not prose.

import { useState } from "react";
import { Spinner } from "@/components/activity";
import { btnPrimary as btn, btnQuiet as btnGhost, input } from "@/components/ui/styles";
import {
  ASSET_CATEGORY_LABELS,
  ASSET_CATEGORY_ORDER,
  ASSET_STATUS_LABELS,
  AssetCategory,
  AssetStatus,
  CommunityAsset,
  SUGGESTED_ATTRIBUTES,
  createCommunityAsset,
  updateCommunityAsset,
} from "@/lib/community";

type AttrRow = { key: string; value: string };

function parseAttrValue(raw: string): string | number | boolean {
  const t = raw.trim();
  if (/^-?\d+(\.\d+)?$/.test(t)) return Number(t);
  if (/^(true|yes)$/i.test(t)) return true;
  if (/^(false|no)$/i.test(t)) return false;
  return t;
}

const attrValueLabel = (v: string | number | boolean) =>
  typeof v === "boolean" ? (v ? "yes" : "no") : String(v);

export function AssetEditor({
  existing,
  onCancel,
  onSaved,
}: {
  existing: CommunityAsset | null;
  onCancel: () => void;
  onSaved: () => void;
}) {
  const [category, setCategory] = useState<AssetCategory>(existing?.category ?? "transport");
  const [name, setName] = useState(existing?.name ?? "");
  const [subcategory, setSubcategory] = useState(existing?.subcategory ?? "");
  const [status, setStatus] = useState<AssetStatus>(existing?.status ?? "open");
  const [settlement, setSettlement] = useState(existing?.settlement ?? "");
  const [description, setDescription] = useState(existing?.description ?? "");
  const [contact, setContact] = useState(existing?.contact ?? "");
  const [url, setUrl] = useState(existing?.url ?? "");
  const [attrs, setAttrs] = useState<AttrRow[]>(
    Object.entries(existing?.attributes ?? {}).map(([key, value]) => ({
      key,
      value: attrValueLabel(value),
    })),
  );
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const usedKeys = new Set(attrs.map((a) => a.key.trim()).filter(Boolean));
  const suggestions = SUGGESTED_ATTRIBUTES[category].filter((k) => !usedKeys.has(k));

  function setAttr(index: number, patch: Partial<AttrRow>) {
    setAttrs((rows) => rows.map((r, i) => (i === index ? { ...r, ...patch } : r)));
  }

  async function save() {
    if (!name.trim()) return;
    setBusy(true);
    setError(null);
    const attributes: Record<string, string | number | boolean> = {};
    for (const row of attrs) {
      if (row.key.trim() && row.value.trim()) {
        attributes[row.key.trim()] = parseAttrValue(row.value);
      }
    }
    const body = {
      category,
      name: name.trim(),
      subcategory: subcategory.trim() || null,
      status,
      settlement: settlement.trim() || null,
      description: description.trim() || null,
      contact: contact.trim() || null,
      url: url.trim() || null,
      attributes,
    };
    try {
      if (existing) await updateCommunityAsset(existing.id, body);
      else await createCommunityAsset(body);
      onSaved();
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
          Category
          <select
            value={category}
            onChange={(e) => setCategory(e.target.value as AssetCategory)}
            className={`${input} mt-1`}
          >
            {ASSET_CATEGORY_ORDER.map((c) => (
              <option key={c} value={c}>
                {ASSET_CATEGORY_LABELS[c]}
              </option>
            ))}
          </select>
        </label>
        <label className="block text-sm">
          Name
          <input
            required
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. Sanday Community School"
            className={`${input} mt-1`}
          />
        </label>
        <label className="block text-sm">
          What kind
          <input
            value={subcategory}
            onChange={(e) => setSubcategory(e.target.value)}
            placeholder="e.g. ferry, GP surgery, village hall"
            className={`${input} mt-1`}
          />
        </label>
        <label className="block text-sm">
          Settlement
          <input
            value={settlement}
            onChange={(e) => setSettlement(e.target.value)}
            placeholder="Where the profile has settlements"
            className={`${input} mt-1`}
          />
        </label>
        <label className="block text-sm">
          Status
          <select
            value={status}
            onChange={(e) => setStatus(e.target.value as AssetStatus)}
            className={`${input} mt-1`}
          >
            {(Object.keys(ASSET_STATUS_LABELS) as AssetStatus[]).map((s) => (
              <option key={s} value={s}>
                {ASSET_STATUS_LABELS[s]}
              </option>
            ))}
          </select>
        </label>
        <label className="block text-sm">
          Website or link
          <input
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="https://…"
            className={`${input} mt-1`}
          />
        </label>
      </div>

      <label className="block text-sm">
        Description
        <textarea
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          rows={2}
          className={`${input} mt-1`}
        />
      </label>

      <fieldset className="text-sm">
        <legend>Details</legend>
        <p className="mt-0.5 text-xs text-ink-faint">
          Short facts about this one — numbers and yes/no answers stay usable in reports.
        </p>
        {attrs.map((row, i) => (
          <div key={i} className="mt-1.5 flex items-center gap-2">
            <input
              value={row.key}
              onChange={(e) => setAttr(i, { key: e.target.value })}
              placeholder="detail"
              aria-label="Detail name"
              className={`${input} w-40`}
            />
            <input
              value={row.value}
              onChange={(e) => setAttr(i, { value: e.target.value })}
              placeholder="value"
              aria-label="Detail value"
              className={input}
            />
            <button
              type="button"
              onClick={() => setAttrs((rows) => rows.filter((_, j) => j !== i))}
              aria-label="Remove detail"
              className="text-faint hover:text-ink"
            >
              ×
            </button>
          </div>
        ))}
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={() => setAttrs((rows) => [...rows, { key: "", value: "" }])}
            className="text-xs font-semibold text-electric-blue hover:underline"
          >
            + Add a detail
          </button>
          {suggestions.map((key) => (
            <button
              key={key}
              type="button"
              onClick={() => setAttrs((rows) => [...rows, { key, value: "" }])}
              className="rounded-full border border-edge px-2 py-0.5 text-xs text-ink-muted hover:border-edge-strong"
            >
              {key.replaceAll("_", " ")}
            </button>
          ))}
        </div>
      </fieldset>

      <label className="block text-sm">
        Contact
        <input
          value={contact}
          onChange={(e) => setContact(e.target.value)}
          placeholder="e.g. 01857 600…, or a name"
          className={`${input} mt-1`}
        />
      </label>

      {error && (
        <p className="rounded-card bg-danger-soft px-3 py-2 text-sm text-danger">{error}</p>
      )}

      <div className="flex items-center gap-3">
        <button type="submit" disabled={busy || !name.trim()} className={btn}>
          {busy ? <Spinner /> : existing ? "Save changes" : "Add it"}
        </button>
        <button type="button" onClick={onCancel} className={btnGhost}>
          Cancel
        </button>
      </div>
    </form>
  );
}
