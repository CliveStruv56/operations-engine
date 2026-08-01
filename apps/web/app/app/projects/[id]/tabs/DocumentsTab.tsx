"use client";

import { useState } from "react";
import {
  DownloadTicket,
  DraftKind,
  RegistryDoc,
  UploadTicket,
  fmtDate,
  gw,
  openPresigned,
} from "@/lib/groundwork";
import { DraftModal } from "./DraftModal";
import { LoadError, useGwLoad } from "./load";
import { btnGhost, input } from "./ui";

const DRAFT_KINDS: DraftKind[] = ["monthly_report", "feasibility_study", "funding_bid"];

export function DocumentsTab({ id }: { id: string }) {
  const [docs, setDocs] = useState<RegistryDoc[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [draftKind, setDraftKind] = useState<DraftKind | null>(null);

  const { failed, refresh } = useGwLoad<RegistryDoc[]>(`/projects/${id}/documents`, setDocs);

  async function setStatus(d: RegistryDoc, status: string) {
    await gw(`/projects/${id}/documents/${d.id}`, {
      method: "PATCH",
      body: JSON.stringify({ status }),
    });
    refresh();
  }

  async function upload(d: RegistryDoc, file: File) {
    setError(null);
    try {
      const { upload_url, file_key } = await gw<UploadTicket>(
        `/projects/${id}/documents/${d.id}/upload`,
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
      await gw(`/projects/${id}/documents/${d.id}/upload/complete`, {
        method: "POST",
        body: JSON.stringify({ file_key }),
      });
      refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  async function download(d: RegistryDoc) {
    const { download_url } = await gw<DownloadTicket>(
      `/projects/${id}/documents/${d.id}/download`
    );
    openPresigned(download_url);
  }

  return (
    <div>
      <LoadError failed={failed} onRetry={refresh} />
      {error && <p className="mb-2 rounded-[10px] bg-danger-soft px-3 py-2 text-sm text-danger">{error}</p>}
      <table className="w-full rounded-card border border-edge bg-surface text-sm">
        <thead>
          <tr className="data border-b border-line text-left text-ink-muted uppercase">
            <th className="px-4 py-2">Document</th>
            <th className="px-4 py-2">Stage</th>
            <th className="px-4 py-2">Status</th>
            <th className="px-4 py-2">Versions</th>
            <th className="px-4 py-2">Updated</th>
            <th className="px-4 py-2" />
          </tr>
        </thead>
        <tbody className="divide-y divide-line">
          {docs.map((d) => (
            <tr key={d.id}>
              <td className="px-4 py-2 font-medium">{d.title}</td>
              <td className="data px-4 py-2 text-ink-muted uppercase">{d.stage_key}</td>
              <td className="px-4 py-2">
                <select value={d.status} onChange={(e) => setStatus(d, e.target.value)} className={input}>
                  {["required", "drafting", "review", "final", "submitted", "na"].map((s) => (
                    <option key={s} value={s}>
                      {s}
                    </option>
                  ))}
                </select>
              </td>
              <td className="data px-4 py-2">{d.versions.length}</td>
              <td className="data px-4 py-2 text-ink-faint">{fmtDate(d.updated_at)}</td>
              <td className="px-4 py-2">
                <span className="flex items-center gap-3">
                  <label className={btnGhost}>
                    Upload
                    <input
                      type="file"
                      accept=".pdf,.docx,.xlsx"
                      className="hidden"
                      onChange={(e) => e.target.files?.[0] && upload(d, e.target.files[0])}
                    />
                  </label>
                  {d.current_file_key && (
                    <button onClick={() => download(d)} className={btnGhost}>
                      Download
                    </button>
                  )}
                  {d.ai_draftable && DRAFT_KINDS.includes(d.doc_type_key as DraftKind) && (
                    <button
                      onClick={() => setDraftKind(d.doc_type_key as DraftKind)}
                      className="stamp"
                    >
                      Draft with AI
                    </button>
                  )}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {draftKind && (
        <DraftModal
          projectId={id}
          kind={draftKind}
          onClose={() => setDraftKind(null)}
          onRegistered={refresh}
        />
      )}
    </div>
  );
}
