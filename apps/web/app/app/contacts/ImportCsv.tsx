"use client";

import { useRef, useState } from "react";
import { ApiError } from "@/lib/api";
import { crm } from "@/lib/crm";

type ImportOut = {
  created: number;
  updated: number;
  skipped: number;
  companies_created: number;
  errors: { line: number; reason: string }[];
};

/** "Import CSV" button + result banner. Reads the file in the browser and
 *  posts its text; expected columns: name (or first/last name), email,
 *  phone, mobile, job title, company, address, notes, tags. */
export function ImportCsv({ onDone }: { onDone: () => void }) {
  const fileRef = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<ImportOut | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function onFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = ""; // allow re-importing the same file
    if (!file) return;
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      const csv = await file.text();
      const out = await crm<ImportOut>("/contacts/import", {
        method: "POST",
        body: JSON.stringify({ csv }),
      });
      setResult(out);
      onDone();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Import failed — try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <input ref={fileRef} type="file" accept=".csv,text/csv" onChange={onFile} hidden />
      <button
        onClick={() => fileRef.current?.click()}
        disabled={busy}
        title="Columns: name (or first/last name), email, phone, mobile, job title, company, address, notes, tags"
        className="rounded-card border border-edge bg-surface px-4 py-2 text-sm font-medium text-ink-muted hover:border-edge-strong hover:text-ink disabled:opacity-50"
      >
        {busy ? "Importing…" : "Import CSV"}
      </button>
      {(result || error) && (
        <div className="w-full">
          {error && (
            <p className="rounded-card bg-danger-soft px-3 py-2 text-sm text-danger">{error}</p>
          )}
          {result && (
            <div className="rounded-card border border-edge bg-surface px-3 py-2 text-sm">
              <span className="font-medium">
                {result.created} added · {result.updated} updated · {result.skipped} skipped
              </span>
              {result.companies_created > 0 && (
                <span className="text-ink-muted">
                  {" "}
                  · {result.companies_created} new compan
                  {result.companies_created === 1 ? "y" : "ies"}
                </span>
              )}
              {result.errors.length > 0 && (
                <ul className="data mt-1 text-ink-muted">
                  {result.errors.map((e) => (
                    <li key={`${e.line}-${e.reason}`}>
                      line {e.line}: {e.reason}
                    </li>
                  ))}
                </ul>
              )}
              <button
                onClick={() => setResult(null)}
                className="ml-2 text-xs text-ink-muted underline hover:text-ink"
              >
                Dismiss
              </button>
            </div>
          )}
        </div>
      )}
    </>
  );
}
