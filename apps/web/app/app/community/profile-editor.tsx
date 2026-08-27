"use client";

// The place itself, edited whole: PUT is an upsert, so first save and later
// corrections are the same form.

import { useState } from "react";
import { Spinner } from "@/components/activity";
import { btnPrimary as btn, btnQuiet as btnGhost, input } from "@/components/ui/styles";
import { CommunityProfile, putCommunityProfile } from "@/lib/community";

export function ProfileEditor({
  existing,
  onCancel,
  onSaved,
}: {
  existing: CommunityProfile | null;
  onCancel: () => void;
  onSaved: () => void;
}) {
  const [placeName, setPlaceName] = useState(existing?.place_name ?? "");
  const [councilArea, setCouncilArea] = useState(existing?.council_area ?? "");
  const [settlements, setSettlements] = useState((existing?.settlements ?? []).join(", "));
  const [description, setDescription] = useState(existing?.description ?? "");
  const [geographyNote, setGeographyNote] = useState(existing?.geography_note ?? "");
  const [sourcesNote, setSourcesNote] = useState(existing?.data_sources_note ?? "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function save() {
    if (!placeName.trim()) return;
    setBusy(true);
    setError(null);
    try {
      await putCommunityProfile({
        place_name: placeName.trim(),
        council_area: councilArea.trim() || null,
        settlements: settlements
          .split(",")
          .map((s) => s.trim())
          .filter(Boolean),
        description: description.trim() || null,
        geography_note: geographyNote.trim() || null,
        data_sources_note: sourcesNote.trim() || null,
        // Not on the form yet (the census import is a later phase), but a
        // whole-row PUT must not silently wipe what an operator recorded.
        census_area_codes: existing?.census_area_codes ?? [],
      });
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
          Place name
          <input
            required
            value={placeName}
            onChange={(e) => setPlaceName(e.target.value)}
            placeholder="e.g. Sanday"
            className={`${input} mt-1`}
          />
        </label>
        <label className="block text-sm">
          Council area
          <input
            value={councilArea}
            onChange={(e) => setCouncilArea(e.target.value)}
            placeholder="e.g. Orkney Islands Council"
            className={`${input} mt-1`}
          />
        </label>
      </div>

      <label className="block text-sm">
        Settlements
        <input
          value={settlements}
          onChange={(e) => setSettlements(e.target.value)}
          placeholder="e.g. Lady Village, Kettletoft"
          className={`${input} mt-1`}
        />
        <span className="mt-0.5 block text-xs text-ink-faint">
          Comma-separated. Facilities can then be tagged with the settlement they are in.
        </span>
      </label>

      <label className="block text-sm">
        About the place
        <textarea
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="A short introduction — what somebody reading a report about this community should know first."
          rows={3}
          className={`${input} mt-1`}
        />
      </label>

      <label className="block text-sm">
        Geography
        <textarea
          value={geographyNote}
          onChange={(e) => setGeographyNote(e.target.value)}
          placeholder="e.g. 20 miles north-east of Kirkwall; 80 minutes by ferry."
          rows={2}
          className={`${input} mt-1`}
        />
      </label>

      <label className="block text-sm">
        Where the data comes from
        <textarea
          value={sourcesNote}
          onChange={(e) => setSourcesNote(e.target.value)}
          placeholder="e.g. Scotland's Census 2022; school roll from the council, Sep 2026."
          rows={2}
          className={`${input} mt-1`}
        />
      </label>

      {error && (
        <p className="rounded-card bg-danger-soft px-3 py-2 text-sm text-danger">{error}</p>
      )}

      <div className="flex items-center gap-3">
        <button type="submit" disabled={busy || !placeName.trim()} className={btn}>
          {busy ? <Spinner /> : "Save the profile"}
        </button>
        <button type="button" onClick={onCancel} className={btnGhost}>
          Cancel
        </button>
      </div>
    </form>
  );
}
