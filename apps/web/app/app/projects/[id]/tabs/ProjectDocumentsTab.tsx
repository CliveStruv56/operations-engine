"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { Stamp } from "@/components/ui";
import { useWorkspace } from "../../../workspace";
import { href } from "../../../sidebar-chats";
import { btn } from "./ui";

type ProjectDoc = {
  id: string;
  title: string;
  project_id: string | null;
  is_primary: boolean;
  status: "uploaded" | "parsing" | "embedding" | "ready" | "failed";
};

const STATUS_NOTE: Record<ProjectDoc["status"], string> = {
  uploaded: "Waiting to be read",
  parsing: "Being read",
  embedding: "Being indexed",
  ready: "Ready",
  failed: "Failed",
};

/** A core project's documents: what its chat prefers when answering. Adding
 *  and managing them stays in Documents, which already does uploads well —
 *  this tab lists them and links there. (A development project's room has
 *  its own document checklist instead.) */
export function ProjectDocumentsTab({ id }: { id: string }) {
  const ws = useWorkspace();
  const tenantId = ws.tenant?.id;
  const [docs, setDocs] = useState<ProjectDoc[] | null>(null);
  const [failed, setFailed] = useState(false);

  const refresh = useCallback(async () => {
    if (!tenantId) return;
    try {
      const all = await api<ProjectDoc[]>("/documents", {}, tenantId);
      setDocs(all.filter((d) => d.project_id === id));
      setFailed(false);
    } catch (err) {
      console.error("Failed to load the project's documents", err);
      setFailed(true);
    }
  }, [id, tenantId]);

  useEffect(() => {
    // Fetch-on-mount: every setState in refresh happens after an await.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    refresh();
  }, [refresh]);

  return (
    <div>
      <div className="mb-3 flex items-center justify-between gap-3">
        <p className="text-sm text-ink-muted">
          Chat in this project prefers these documents. ★ marks its primary sources.
        </p>
        <Link href={href({ view: "vault", project: id })} className={btn}>
          Add or manage documents
        </Link>
      </div>
      {failed && (
        <p role="alert" className="mb-3 rounded-card bg-danger-soft px-3 py-2 text-sm text-danger">
          Documents failed to load.{" "}
          <button onClick={refresh} className="underline">
            Retry
          </button>
        </p>
      )}
      {docs && docs.length === 0 && (
        <p className="text-sm text-ink-muted">No documents in this project yet.</p>
      )}
      {docs && docs.length > 0 && (
        <ul className="flex flex-col divide-y divide-line rounded-card border border-edge bg-surface">
          {docs.map((d) => (
            <li key={d.id} className="flex items-center justify-between gap-2 px-3 py-2 text-sm">
              <span className="min-w-0 truncate">
                {d.is_primary && (
                  <span aria-label="Primary source" title="Primary source">
                    ★{" "}
                  </span>
                )}
                {d.title}
              </span>
              <Stamp tone={d.status === "failed" ? "danger" : "neutral"}>
                {STATUS_NOTE[d.status]}
              </Stamp>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
