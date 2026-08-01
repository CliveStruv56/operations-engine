"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { Spinner } from "@/components/activity";
import type { Project } from "./workspace";

type Doc = {
  id: string;
  title: string;
  mime: string | null;
  project_id: string | null;
  is_primary: boolean;
  summary: string | null;
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

const MIME_LABEL: Record<string, string> = {
  "application/pdf": "PDF",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "DOC",
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "XLS",
  "application/vnd.openxmlformats-officedocument.presentationml.presentation": "PPT",
  "text/plain": "TXT",
  "text/markdown": "MD",
  "text/csv": "CSV",
};

const STATUS_LABEL: Record<Doc["status"], string> = {
  uploaded: "queued",
  parsing: "reading",
  embedding: "indexing",
  ready: "ready",
  failed: "failed",
};

const STATUS_STYLE: Record<Doc["status"], string> = {
  uploaded: "text-ink-muted",
  parsing: "text-warn bg-warn-soft",
  embedding: "text-warn bg-warn-soft",
  ready: "text-accent bg-accent-soft",
  failed: "text-danger bg-danger-soft",
};

export default function VaultPanel({
  tenantId,
  projects,
  activeProjectId,
  onProjectsChanged,
}: {
  tenantId: string;
  projects: Project[];
  activeProjectId: string | null;
  onProjectsChanged: () => void;
}) {
  const [docs, setDocs] = useState<Doc[]>([]);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const [confirmingId, setConfirmingId] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  const activeProject = projects.find((p) => p.id === activeProjectId) ?? null;

  const refresh = useCallback(async () => {
    setDocs(await api<Doc[]>("/documents", {}, tenantId));
  }, [tenantId]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    refresh().catch((e) => setError(String(e)));
  }, [refresh]);

  // Poll while anything is still working its way through the pipeline.
  const active = docs.some(
    (d) => d.status === "uploaded" || d.status === "parsing" || d.status === "embedding"
  );
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
        setError(`${file.name}: this file type isn't supported`);
        continue;
      }
      setBusy(`Uploading ${file.name}…`);
      try {
        const { id, upload_url } = await api<{ id: string; upload_url: string }>(
          "/documents",
          {
            method: "POST",
            body: JSON.stringify({
              title: file.name,
              mime,
              size_bytes: file.size,
              project_id: activeProjectId,
            }),
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
    await refresh().catch((e) => setError(String(e)));
  }

  async function remove(doc: Doc) {
    setConfirmingId(null);
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

  async function patchDoc(doc: Doc, patch: { project_id?: string | null; is_primary?: boolean }) {
    try {
      await api(`/documents/${doc.id}`, { method: "PATCH", body: JSON.stringify(patch) }, tenantId);
      await refresh();
      onProjectsChanged();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  const visible = activeProjectId ? docs.filter((d) => d.project_id === activeProjectId) : docs;
  const readyCount = visible.filter((d) => d.status === "ready").length;

  return (
    <section className="flex min-h-0 flex-1 flex-col">
      <header className="flex items-baseline justify-between border-b border-line px-6 py-4">
        <div>
          <h2 className="text-lg font-semibold tracking-tight">
            {activeProject ? `Vault — ${activeProject.name}` : "Vault"}
          </h2>
          <p className="mt-0.5 text-sm text-ink-muted">
            {activeProject
              ? "This project's documents. Chat in this project prefers these; ★ marks its primary sources."
              : "Everything here is read, indexed, and used to answer your questions."}
          </p>
        </div>
        <p className="data text-ink-muted uppercase">
          {visible.length} documents · {readyCount} ready
        </p>
      </header>

      <div className="min-h-0 flex-1 overflow-y-auto p-6">
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
          className={`cursor-pointer rounded-md border border-dashed px-8 py-10 text-center transition-colors ${
            dragging
              ? "border-accent bg-accent-soft"
              : "border-line bg-paper hover:border-ink-faint"
          }`}
        >
          <p className="text-sm font-medium">Drop files here, or click to choose</p>
          <p className="data mt-2 text-ink-faint uppercase">
            PDF · Word · Excel · PowerPoint · Text · Markdown · CSV — up to 50 MB
          </p>
          <input
            ref={fileInput}
            type="file"
            multiple
            accept={ACCEPT}
            className="hidden"
            onChange={(e) => e.target.files && upload(e.target.files)}
          />
        </div>

        {busy && (
          <p className="data mt-3 flex items-center gap-2 text-ink-muted">
            <Spinner className="text-accent" />
            {busy}
          </p>
        )}
        {error && (
          <p className="mt-3 rounded-sm bg-danger-soft px-3 py-2 text-sm text-danger">{error}</p>
        )}

        {visible.length === 0 && !busy ? (
          <p className="mt-8 text-center text-sm text-ink-faint">
            {activeProject
              ? "No documents in this project yet. Upload here, or assign existing documents from Everything."
              : "No documents yet. Add your staff handbook, policies, or price lists — anything your team asks questions about."}
          </p>
        ) : (
          <ul className="mt-6 divide-y divide-line border-y border-line">
            {visible.map((d) => (
              <li key={d.id} className="py-3">
                <div className="flex items-center gap-4">
                  <span className="data w-9 shrink-0 text-ink-faint">
                    {MIME_LABEL[d.mime ?? ""] ?? "—"}
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium">
                      {d.is_primary && (
                        <span className="mr-1 text-accent" title="Primary document for its project">
                          ★
                        </span>
                      )}
                      {d.title}
                    </p>
                    {d.status === "failed" && d.error ? (
                      <p className="mt-0.5 truncate text-xs text-danger">{d.error}</p>
                    ) : (
                      <p className="data mt-0.5 text-ink-faint">
                        Added {new Date(d.created_at).toLocaleDateString("en-GB")}
                        {!activeProjectId && d.project_id && (
                          <> · {projects.find((p) => p.id === d.project_id)?.name ?? "project"}</>
                        )}
                      </p>
                    )}
                  </div>
                  <span className={`stamp shrink-0 ${STATUS_STYLE[d.status]}`}>
                    {STATUS_LABEL[d.status]}
                  </span>
                  <span className="flex shrink-0 items-center gap-3 text-xs">
                    {d.summary && (
                      <button
                        onClick={() => setExpandedId(expandedId === d.id ? null : d.id)}
                        className="text-ink-muted underline hover:text-ink"
                      >
                        {expandedId === d.id ? "Hide summary" : "Summary"}
                      </button>
                    )}
                    {projects.length > 0 && confirmingId !== d.id && (
                      <select
                        value={d.project_id ?? ""}
                        onChange={(e) =>
                          patchDoc(d, { project_id: e.target.value || null })
                        }
                        className="max-w-28 rounded-sm border border-line bg-surface px-1 py-0.5 text-xs text-ink-muted"
                        title="Assign to a project"
                      >
                        <option value="">No project</option>
                        {projects
                          .filter((p) => !p.archived)
                          .map((p) => (
                            <option key={p.id} value={p.id}>
                              {p.name}
                            </option>
                          ))}
                      </select>
                    )}
                    {d.project_id && confirmingId !== d.id && (
                      <button
                        onClick={() => patchDoc(d, { is_primary: !d.is_primary })}
                        className={d.is_primary ? "text-accent" : "text-ink-faint hover:text-accent"}
                        title={d.is_primary ? "Unmark as primary" : "Mark as a primary document"}
                      >
                        ★
                      </button>
                    )}
                    {(d.status === "ready" || d.status === "failed") &&
                      confirmingId !== d.id && (
                        <button
                          onClick={() => reprocess(d)}
                          className="text-ink-muted underline hover:text-ink"
                        >
                          Re-index
                        </button>
                      )}
                    {confirmingId === d.id ? (
                      <>
                        <button
                          onClick={() => remove(d)}
                          className="font-medium text-danger underline"
                        >
                          Delete for good
                        </button>
                        <button
                          onClick={() => setConfirmingId(null)}
                          className="text-ink-muted underline hover:text-ink"
                        >
                          Keep
                        </button>
                      </>
                    ) : (
                      <button
                        onClick={() => setConfirmingId(d.id)}
                        className="text-ink-muted underline hover:text-danger"
                      >
                        Delete
                      </button>
                    )}
                  </span>
                </div>
                {expandedId === d.id && d.summary && (
                  <p className="mt-2 ml-13 rounded-sm border border-line bg-paper px-3 py-2 text-xs leading-relaxed text-ink-muted">
                    {d.summary}
                  </p>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}
