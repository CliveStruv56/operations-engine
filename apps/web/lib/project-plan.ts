import { api } from "@/lib/api";

export type PlanTask = {
  id: string;
  project_id: string;
  title: string;
  status: "todo" | "doing" | "done";
  due_date: string | null;
  assignee_membership_id: string | null;
  assignee_email: string | null;
  position: number;
  completed_at: string | null;
  created_at: string;
};

export type PlanTaskSeed = {
  title: string;
  due_date?: string | null;
  assignee_membership_id?: string | null;
};

export type MemberRow = {
  id: string;
  email: string | null;
  role: string;
};

export const listPlanTasks = (projectId: string, tenantId: string) =>
  api<PlanTask[]>(`/projects/${projectId}/plan-tasks`, {}, tenantId);

export const createPlanTask = (projectId: string, tenantId: string, body: PlanTaskSeed) =>
  api<PlanTask>(
    `/projects/${projectId}/plan-tasks`,
    { method: "POST", body: JSON.stringify(body) },
    tenantId
  );

export const patchPlanTask = (
  projectId: string,
  taskId: string,
  tenantId: string,
  body: Partial<{ title: string; status: PlanTask["status"]; due_date: string | null; assignee_membership_id: string | null }>
) =>
  api<PlanTask>(
    `/projects/${projectId}/plan-tasks/${taskId}`,
    { method: "PATCH", body: JSON.stringify(body) },
    tenantId
  );

export const deletePlanTask = (projectId: string, taskId: string, tenantId: string) =>
  api<void>(`/projects/${projectId}/plan-tasks/${taskId}`, { method: "DELETE" }, tenantId);

export const listMembers = (tenantId: string) => api<MemberRow[]>("/members", {}, tenantId);
