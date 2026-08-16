"use client";

import { useState } from "react";
import {
  DRAFT_LABEL,
  DownloadTicket,
  DraftKind,
  RegistryDoc,
  STAGE_LABEL,
  UploadTicket,
  fmtDate,
  gr,
} from "@/lib/grants";
import { openPresigned } from "@/lib/groundwork";
import { btnGhost, card, input, th } from "../../ui";
import { DraftModal } from "./DraftModal";
import { LoadError, useGrantLoad } from "./load";

const STATUSES = ["required", "drafting", "review", "final", "submitted", "na"];

export function BidPackTab({ id }: { id: string }) {
  const [docs, setDocs] = useState<RegistryDoc[]>([]);
  const [drafting, setDrafting] = useState<DraftKind | null>(null);
  const [error, setError] = useState<string | null>(null);
  const { failed, refresh } = useGrantLoad<RegistryDoc[]>(
    `/grants/applications/${id}/documents`,
    setDocs
  );

  async function setStatus(doc: RegistryDoc, status: string) {
    setError(null);
    try {
      await gr(`/grants/applications/${id}/documents/${doc.id}`, {
        method: "PATCH",
        body: JSON.stringify({ status }),
      });
      refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  async function download(doc: RegistryDoc) {
    const ticket = await gr<DownloadTicket>(
      `/grants/applications/${id}/documents/${doc.id}/download`
    );
    openPresigned(ticket.download_url);
  }

  async function upload(doc: RegistryDoc, file: File) {
    setError(null);
    try {
      const { upload_url, file_key } = await gr<UploadTicket>(
        `/grants/applications/${id}/documents/${doc.id}/upload`,
        {
          method: "POST",
          body: JSON.stringify({ filename: file.name, mime: file.type, size_bytes: file.size }),
        }
      );
      const put = await fetch(upload_url, {
        method: "PUT",
        headers: { "Content-Type": file.type },
        body: file,
      });
      if (!put.ok) throw new Error(`Upload failed (${put.status})`);
      await gr(`/grants/applications/${id}/documents/${doc.id}/upload/complete`, {
        method: "POST",
        body: JSON.stringify({ file_key }),
      });
      refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  return (
    <div>
      <LoadError failed={failed} onRetry={refresh} />
      {error && (
        <p className="mb-3 rounded-card bg-danger-soft px-3 py-2 text-sm text-danger">{error}</p>
      )}

      {/* Every other draft launches from its own registry row. A funder's form
          has none to launch from — which form you are answering is a choice
          made at the time, not a document the spine seeded. */}
      <div className="mb-2 flex justify-end">
        <button onClick={() => setDrafting("application_form")} className={btnGhost}>
          Answer a funder&apos;s form
        </button>
      </div>
      <div className={`overflow-x-auto ${card}`}>
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-line">
              <th className={th}>Document</th>
              <th className={th}>Stage</th>
              <th className={th}>Status</th>
              <th className={th}>Versions</th>
              <th className={th}>Updated</th>
              <th className={th}></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {docs.map((doc) => (
              <tr key={doc.id}>
                <td className="px-4 py-2.5 font-medium">
                  {doc.title}
                  {doc.reporting_period_id && (
                    <span className="stamp ml-2 text-ink-faint">for a reporting period</span>
                  )}
                </td>
                <td className="data px-4 py-2.5 text-ink-faint">
                  {STAGE_LABEL[doc.stage_key] ?? doc.stage_key}
                </td>
                <td className="px-4 py-2.5">
                  <select
                    value={doc.status}
                    onChange={(e) => setStatus(doc, e.target.value)}
                    className={input}
                    title="Marking a document final ticks any gate item that names it"
                  >
                    {STATUSES.map((s) => (
                      <option key={s} value={s}>
                        {s}
                      </option>
                    ))}
                  </select>
                </td>
                <td className="data px-4 py-2.5 text-ink-faint">{doc.versions.length || "—"}</td>
                <td className="data px-4 py-2.5 text-ink-faint">{fmtDate(doc.updated_at)}</td>
                <td className="px-4 py-2.5 text-right">
                  <span className="flex items-center justify-end gap-3">
                    <label className={btnGhost}>
                      Upload
                      <input
                        type="file"
                        accept=".pdf,.docx,.xlsx"
                        className="hidden"
                        onChange={(e) => {
                          const file = e.target.files?.[0];
                          if (file) upload(doc, file);
                          // Re-selecting the same file (a failed PUT, a
                          // corrected copy) must still fire a change event.
                          e.target.value = "";
                        }}
                      />
                    </label>
                    {doc.ai_draftable && (
                      <button
                        onClick={() => setDrafting(doc.doc_type_key as DraftKind)}
                        className={btnGhost}
                      >
                        Draft with AI
                      </button>
                    )}
                    {doc.current_file_key && (
                      <button onClick={() => download(doc)} className={btnGhost}>
                        Download
                      </button>
                    )}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <p className="mt-3 text-xs text-ink-faint">
        Every AI draft is filed at &ldquo;drafting&rdquo; with a DRAFT header and its unresolved
        points marked [TO CONFIRM]. Advancing a document to final or submitted is always a person&rsquo;s
        decision — and it is what ticks the matching gate item.
      </p>

      {drafting && DRAFT_LABEL[drafting] && (
        <DraftModal
          applicationId={id}
          kind={drafting}
          onClose={() => setDrafting(null)}
          onRegistered={refresh}
        />
      )}
    </div>
  );
}
