"use client";

// The self-serve backup: everything the workspace holds, as one ZIP.
//
// "Your documents and records are yours" has been on the security page since
// launch; this is the button that makes it true without anyone having to
// email support. An archive can take minutes when the vault is full, so the
// button polls the job like every other export.

import { useState } from "react";
import { Spinner } from "@/components/activity";
import { btnPrimary as btn, cardPadded as card } from "@/components/ui/styles";
import { getWorkspaceExport, submitWorkspaceExport } from "@/lib/export";
import { openPresigned } from "@/lib/groundwork";

export default function ExportSection() {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function exportWorkspace() {
    setBusy(true);
    setError(null);
    try {
      const job = await submitWorkspaceExport();
      for (;;) {
        await new Promise((r) => setTimeout(r, 2000));
        const next = await getWorkspaceExport(job.id);
        if (next.status === "succeeded" && next.download_url) {
          openPresigned(next.download_url);
          break;
        }
        if (next.status === "failed") throw new Error(next.error ?? "Export failed");
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className={card}>
      <h2 className="data mb-3 text-ink-muted uppercase">Your data</h2>
      <p className="text-sm text-ink-muted">
        Your documents and records are yours. Download the whole workspace as one archive:
        every vault document, everything Flowgrid produced for you, and every register —
        as spreadsheets and as a complete machine-readable copy. Take one whenever you want
        your own backup.
      </p>
      <p className="mt-2 text-xs text-ink-faint">
        Private conversations belonging to other members are not included — only shared
        conversations and your own.
      </p>
      <div className="mt-4 flex items-center gap-3">
        <button onClick={() => void exportWorkspace()} disabled={busy} className={btn}>
          {busy ? <Spinner /> : "Export workspace"}
        </button>
        {busy && (
          <span className="text-xs text-ink-faint">
            Gathering everything — a full vault can take a few minutes. The download opens
            when it is ready.
          </span>
        )}
      </div>
      {error && <p className="mt-2 text-sm text-danger">{error}</p>}
    </section>
  );
}
