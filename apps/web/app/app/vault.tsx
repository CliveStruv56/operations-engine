"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";

type Doc = {
  id: string;
  title: string;
  mime: string | null;
  status: "uploaded" | "parsing" | "embedding" | "ready" | "failed";
  error: string | null;
  created_at: string;
};

const ACCEPT =
  ".pdf,.docx,.xlsx,.pptx,.txt,.md,.csv,application/pdf," +
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document," +
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet," +
  "application/vnd.openxmlformats-officedocument.presentationml.presentation," +
  "text/plain,text/markdown,text/csv";

const EXT_MIMES: Record<string, string> = {
  pdf: "application/pdf",
  docx: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  xlsx: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  pptx: "application/vnd.openxmlformats-officedocument.presentationml.presentation",
  txt: "text/plain",
  md: "text/markdown",
  csv: "text/csv",
};

const STATUS_STYLE: Record<Doc["status"], string> = {
  uploaded: "bg-neutral-100 text-neutral-600",
  parsing: "bg-blue-50 text-blue-700",
  embedding: "bg-blue-50 text-blue-700",
  ready: "bg-green-50 text-green-700",
  failed: "bg-red-50 text-red-700",
};

export default function VaultPanel({ tenantId }: { tenantId: string }) {
  const [docs, setDocs] = useState<Doc[]>([]);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);

  const refresh = useCallback(async () => {
    setDocs(await api<Doc[]>("/documents", {}, tenantId));
  }, [tenantId]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    refresh().catch((e) => setError(String(e)));
  }, [refresh]);

  // Poll while anything is still working its way through the pipeline.
  const active = docs.some((d) => d.status === "parsing" || d.status === "embedding");
  useEffect(() => {
    if (!active) return;
    const t = setInterval(() => refresh().catch(() => {}), 3000);
    return () => clearInterval(t);
  }, [active, refresh]);

  async function upload(files: FileList | File[]) {
    setError(null);
    for (const file of Array.from(files)) {
      const mime = file.type || EXT_MIMES[file.name.split(".").pop()?.toLowerCase() ?? ""];
      if (!mime || !Object.values(EXT_MIMES).includes(mime)) {
        setError(`${file.name}: unsupported file type`);
        continue;
      }
      setBusy(`Uploading ${file.name}…`);
      try {
        const { id, upload_url } = await api<{ id: string; upload_url: string }>(
          "/documents",
          {
            method: "POST",
            body: JSON.stringify({ title: file.name, mime, size_bytes: file.size }),
          },
          tenantId
        );
        const put = await fetch(upload_url, {
          method: "PUT",
          headers: { "Content-Type": mime },
          body: file,
        });
        if (!put.ok) throw new Error(`Upload failed (${put.status})`);
        await api(`/documents/${id}/complete`, { method: "POST" }, tenantId);
      } catch (e) {
        setError(`${file.name}: ${e instanceof Error ? e.message : String(e)}`);
      }
    }
    setBusy(null);
    await refresh().catch(() => {});
  }

  async function remove(doc: Doc) {
    if (!confirm(`Delete "${doc.title}" and its indexed content?`)) return;
    try {
      await api(`/documents/${doc.id}`, { method: "DELETE" }, tenantId);
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  async function reprocess(doc: Doc) {
    try {
      await api(`/documents/${doc.id}/reprocess`, { method: "POST" }, tenantId);
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  return (
    <section className="space-y-3 text-sm">
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          upload(e.dataTransfer.files);
        }}
        onClick={() => fileInput.current?.click()}
        className={`cursor-pointer rounded border-2 border-dashed p-8 text-center transition-colors ${
          dragging ? "border-neutral-900 bg-neutral-50" : "border-neutral-300"
        }`}
      >
        <p className="font-medium">Drop files here or click to upload</p>
        <p className="mt-1 text-neutral-500">PDF, Word, Excel, PowerPoint, text, Markdown or CSV — up to 50 MB</p>
        <input
          ref={fileInput}
          type="file"
          multiple
          accept={ACCEPT}
          className="hidden"
          onChange={(e) => e.target.files && upload(e.target.files)}
        />
      </div>

      {busy && <p className="text-neutral-500">{busy}</p>}
      {error && <p className="text-red-600">{error}</p>}

      {docs.length === 0 && !busy ? (
        <p className="text-neutral-400">No documents yet — add your first file to build the vault.</p>
      ) : (
        <ul className="divide-y divide-neutral-100 rounded border border-neutral-200">
          {docs.map((d) => (
            <li key={d.id} className="flex items-center gap-3 px-4 py-3">
              <div className="min-w-0 flex-1">
                <p className="truncate font-medium">{d.title}</p>
                {d.status === "failed" && d.error && (
                  <p className="truncate text-xs text-red-500">{d.error}</p>
                )}
              </div>
              <span className={`shrink-0 rounded-full px-2 py-0.5 text-xs ${STATUS_STYLE[d.status]}`}>
                {d.status === "parsing" || d.status === "embedding" ? `${d.status}…` : d.status}
              </span>
              {(d.status === "ready" || d.status === "failed") && (
                <button onClick={() => reprocess(d)} className="shrink-0 text-neutral-400 hover:text-neutral-700" title="Reprocess">
                  ↻
                </button>
              )}
              <button onClick={() => remove(d)} className="shrink-0 text-neutral-400 hover:text-red-600" title="Delete">
                ✕
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
