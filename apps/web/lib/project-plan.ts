import { api } from "@/lib/api";

export type PlanTask = {
  id: string;
  project_id: string;
  title: string;
  details: string | null;
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
  details?: string | null;
  due_date?: string | null;
  assignee_membership_id?: string | null;
};

export type PlanTaskPatch = Partial<{
  title: string;
  details: string | null;
  status: PlanTask["status"];
  due_date: string | null;
  assignee_membership_id: string | null;
  position: number;
}>;

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
  body: PlanTaskPatch
) =>
  api<PlanTask>(
    `/projects/${projectId}/plan-tasks/${taskId}`,
    { method: "PATCH", body: JSON.stringify(body) },
    tenantId
  );

export const deletePlanTask = (projectId: string, taskId: string, tenantId: string) =>
  api<void>(`/projects/${projectId}/plan-tasks/${taskId}`, { method: "DELETE" }, tenantId);

export const listMembers = (tenantId: string) => api<MemberRow[]>("/members", {}, tenantId);

export const enableProjectPlan = (projectId: string, tenantId: string) =>
  api<{ id: string; has_plan: boolean }>(
    `/projects/${projectId}`,
    { method: "PATCH", body: JSON.stringify({ has_plan: true }) },
    tenantId
  );

export function isOverdue(task: PlanTask, today = new Date()): boolean {
  if (task.status === "done" || !task.due_date) return false;
  return task.due_date < today.toISOString().slice(0, 10);
}
