// Whole-workspace archive export: the self-serve backup path.
import { api } from "@/lib/api";
import { tenantId } from "@/lib/groundwork";

const ex = <T,>(path: string, init: RequestInit = {}) =>
  api<T>(path, init, tenantId() ?? undefined);

export type WorkspaceExportJob = {
  id: string;
  kind: string;
  status: "queued" | "running" | "succeeded" | "failed";
  error: string | null;
  /** Presigned GET with a readable filename, present once the worker lands the zip. */
  download_url: string | null;
  created_at: string;
  updated_at: string;
};

export const submitWorkspaceExport = () =>
  ex<WorkspaceExportJob>("/tenants/me/export", { method: "POST" });

export const getWorkspaceExport = (id: string) =>
  ex<WorkspaceExportJob>(`/tenants/me/exports/${id}`);
