"use client";

// Looking a workspace up on a public register.
//
// This is the screen the whole activation argument rests on: one number, and
// the register stops being empty. So it has to be honest about three things —
// which register covers you, what happens when a key is not configured yet,
// and that everything it finds is a question rather than an answer.

import { useState } from "react";
import { Spinner } from "@/components/activity";
import { ApiError } from "@/lib/api";
import { REGISTERS, RegisterImport, importFromRegister } from "@/lib/claims";

import { btnPrimary as btn, btnQuiet as btnGhost, input } from "@/components/ui/styles";

export function ImportPanel({
  onCancel,
  onImported,
}: {
  onCancel: () => void;
  onImported: () => void;
}) {
  const [route, setRoute] = useState<string>(REGISTERS[0].route);
  const [number, setNumber] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // A dissolved company or removed charity still returns complete data, so
  // importing one takes a deliberate second ask rather than a silent accept.
  const [inactive, setInactive] = useState<string | null>(null);
  const [result, setResult] = useState<RegisterImport | null>(null);

  const chosen = REGISTERS.find((r) => r.route === route) ?? REGISTERS[0];

  async function run(allowInactive: boolean) {
    setBusy(true);
    setError(null);
    try {
      const found = await importFromRegister(route, number, allowInactive);
      setResult(found);
      setInactive(null);
      onImported();
    } catch (e) {
      if (e instanceof ApiError && e.code === "register_record_inactive") {
        setInactive(e.message);
      } else {
        setError(e instanceof Error ? e.message : String(e));
      }
    } finally {
      setBusy(false);
    }
  }

  if (result) {
    return (
      <div className="space-y-3 text-sm">
        <p>
          {result.proposed.length > 0
            ? `Found ${result.proposed.length} ${result.proposed.length === 1 ? "fact" : "facts"} — check them below and keep the ones that are right.`
            : "Nothing has changed since the last look-up."}
          {result.unchanged > 0 && ` ${result.unchanged} already matched what you hold.`}
        </p>
        <p className="text-xs text-ink-faint">
          From{" "}
          <a
            href={result.source_url}
            target="_blank"
            rel="noopener noreferrer"
            className="underline"
          >
            the public register
          </a>
          , status “{result.registration_status}”.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div>
        <label className="data mb-1 block text-ink-muted uppercase" htmlFor="register">
          Which register
        </label>
        <select
          id="register"
          value={route}
          onChange={(e) => {
            setRoute(e.target.value);
            setInactive(null);
            setError(null);
          }}
          className={input}
        >
          {REGISTERS.map((r) => (
            <option key={r.route} value={r.route}>
              {r.label}
            </option>
          ))}
        </select>
        <p className="mt-1 text-xs text-ink-faint">{chosen.hint}</p>
      </div>

      <div>
        <label className="data mb-1 block text-ink-muted uppercase" htmlFor="number">
          {chosen.label} number
        </label>
        <input
          id="number"
          value={number}
          onChange={(e) => setNumber(e.target.value)}
          placeholder={chosen.placeholder}
          className={input}
        />
      </div>

      {inactive && (
        <div className="rounded-card bg-warn-soft px-3 py-2 text-xs text-warn">
          <p>{inactive}</p>
          <button
            onClick={() => run(true)}
            disabled={busy}
            className="mt-2 underline hover:text-ink"
          >
            Import it anyway
          </button>
        </div>
      )}

      {error && (
        <p className="rounded-card bg-danger-soft px-3 py-2 text-xs text-danger">{error}</p>
      )}

      <div className="flex items-center gap-3">
        <button onClick={() => run(false)} disabled={busy || !number.trim()} className={btn}>
          {busy ? (
            <span className="flex items-center gap-2">
              <Spinner /> Looking up…
            </span>
          ) : (
            "Look it up"
          )}
        </button>
        <button onClick={onCancel} disabled={busy} className={btnGhost}>
          Cancel
        </button>
      </div>
    </div>
  );
}
