"use client";

// Typing a fact the registers do not publish: insurance, a trading name,
// Northern Ireland charities, a figure from last year's accounts.
//
// Typed claims are confirmed on arrival — the person is asserting the fact.
// Asking them to type it and then tick it would be theatre. The statement is
// generated from the kind's template so a later draft reads the same sentence
// a register import would have produced.

import { useEffect, useMemo, useState } from "react";
import { Spinner } from "@/components/activity";
import {
  CATEGORY_LABELS,
  CATEGORY_ORDER,
  ClaimKind,
  createClaim,
  fillStatement,
  listClaimKinds,
  parseClaimValue,
} from "@/lib/claims";

const btn =
  "rounded-[10px] bg-accent px-4 py-2 text-sm font-medium text-accent-ink hover:bg-accent-deep disabled:opacity-50";
const btnGhost = "text-xs text-ink-muted underline hover:text-ink";
const input = "w-full rounded-[10px] border border-edge bg-card px-3 py-2 text-sm";

export function AddFactPanel({
  onCancel,
  onSaved,
}: {
  onCancel: () => void;
  onSaved: () => void;
}) {
  const [kinds, setKinds] = useState<ClaimKind[] | null>(null);
  const [kindKey, setKindKey] = useState("");
  const [subject, setSubject] = useState("");
  const [period, setPeriod] = useState("");
  const [rawValue, setRawValue] = useState("");
  const [statementEdit, setStatementEdit] = useState<string | null>(null);
  const [expiresOn, setExpiresOn] = useState("");
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listClaimKinds()
      .then((rows) => {
        setKinds(rows);
        if (rows[0]) setKindKey(rows[0].key);
      })
      .catch((e) => setError(e instanceof Error ? e.message : String(e)));
  }, []);

  const kind = kinds?.find((k) => k.key === kindKey) ?? null;
  const grouped = useMemo(() => {
    if (!kinds) return [];
    return CATEGORY_ORDER.map((category) => ({
      category,
      kinds: kinds.filter((k) => k.category === category),
    })).filter((g) => g.kinds.length > 0);
  }, [kinds]);
  const statement =
    statementEdit ??
    (kind ? fillStatement(kind, subject.trim() || null, parseClaimValue(kind, rawValue)) : "");

  async function save() {
    if (!kind) return;
    setBusy(true);
    setError(null);
    try {
      await createClaim({
        kind: kind.key,
        subject: kind.cardinality === "multi" ? subject.trim() || null : null,
        period: kind.periodic ? period.trim() || null : null,
        statement: statement.trim(),
        value: parseClaimValue(kind, rawValue),
        expires_on: expiresOn || null,
        notes: notes.trim() || null,
      });
      onSaved();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  if (kinds === null && !error) {
    return (
      <p className="flex items-center gap-2 text-sm text-ink-muted">
        <Spinner /> Loading the kinds of fact we recognise…
      </p>
    );
  }

  return (
    <form
      className="space-y-3"
      onSubmit={(e) => {
        e.preventDefault();
        void save();
      }}
    >
      <label className="block text-sm">
        What kind of fact
        <select
          value={kindKey}
          onChange={(e) => {
            setKindKey(e.target.value);
            setStatementEdit(null);
            setSubject("");
            setPeriod("");
            setRawValue("");
          }}
          className={`${input} mt-1`}
        >
          {grouped.map((g) => (
            <optgroup key={g.category} label={CATEGORY_LABELS[g.category]}>
              {g.kinds.map((k) => (
                <option key={k.key} value={k.key}>
                  {k.label}
                </option>
              ))}
            </optgroup>
          ))}
        </select>
      </label>

      {kind?.cardinality === "multi" && (
        <label className="block text-sm">
          Which one
          <input
            required
            value={subject}
            onChange={(e) => setSubject(e.target.value)}
            placeholder="e.g. Public liability, a trustee's name"
            className={`${input} mt-1`}
          />
        </label>
      )}

      {kind?.periodic && (
        <label className="block text-sm">
          Period
          <input
            value={period}
            onChange={(e) => setPeriod(e.target.value)}
            placeholder="e.g. 2024/25"
            className={`${input} mt-1`}
          />
        </label>
      )}

      <label className="block text-sm">
        Value
        <input
          required
          type={kind?.value_kind === "date" ? "date" : kind?.value_kind === "number" || kind?.value_kind === "money" ? "number" : "text"}
          value={rawValue}
          onChange={(e) => setRawValue(e.target.value)}
          placeholder={kind?.value_kind === "money" ? "412000" : kind?.unit ?? ""}
          className={`${input} mt-1`}
        />
        {kind?.unit && <span className="mt-0.5 block text-xs text-ink-faint">{kind.unit}</span>}
      </label>

      <label className="block text-sm">
        The sentence drafts will read
        <textarea
          required
          value={statement}
          onChange={(e) => setStatementEdit(e.target.value)}
          rows={2}
          className={`${input} mt-1`}
        />
      </label>

      <label className="block text-sm">
        Expires
        <input
          type="date"
          value={expiresOn}
          onChange={(e) => setExpiresOn(e.target.value)}
          className={`${input} mt-1`}
        />
        <span className="mt-0.5 block text-xs text-ink-faint">
          For cover and certificates. Leave blank if this does not lapse.
        </span>
      </label>

      <label className="block text-sm">
        Where this came from
        <textarea
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          placeholder="e.g. Annual accounts 2024/25, p.4 — or typed because no register covers this."
          rows={2}
          className={`${input} mt-1`}
        />
      </label>

      {error && (
        <p className="rounded-[10px] bg-danger-soft px-3 py-2 text-sm text-danger">{error}</p>
      )}

      <div className="flex items-center gap-3">
        <button
          type="submit"
          // An empty value renders a non-empty statement ("…trades as .")
          // from the template, so the statement check alone is not enough.
          disabled={
            busy ||
            !statement.trim() ||
            !rawValue.trim() ||
            (kind?.cardinality === "multi" && !subject.trim())
          }
          className={btn}
        >
          {busy ? <Spinner /> : "Add this fact"}
        </button>
        <button type="button" onClick={onCancel} className={btnGhost}>
          Cancel
        </button>
      </div>
    </form>
  );
}
