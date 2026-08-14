"use client";

import { useEffect, useState } from "react";
import {
  type MemberRow,
  type PlanTask,
  createPlanTask,
  deletePlanTask,
  listMembers,
  listPlanTasks,
  patchPlanTask,
} from "@/lib/project-plan";
import { useWorkspace } from "./workspace";

export default function ProjectPlanPanel({ projectId }: { projectId: string }) {
  const ws = useWorkspace();
  const tenantId = ws.tenant!.id;
  const [tasks, setTasks] = useState<PlanTask[] | null>(null);
  const [members, setMembers] = useState<MemberRow[]>([]);
  const [title, setTitle] = useState("");
  const [due, setDue] = useState("");
  const [assignee, setAssignee] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function reload() {
    const rows = await listPlanTasks(projectId, tenantId);
    setTasks(rows);
    await ws.refreshProjects();
  }

  useEffect(() => {
    let stale = false;
    Promise.all([listPlanTasks(projectId, tenantId), listMembers(tenantId)])
      .then(([rows, people]) => {
        if (stale) return;
        setTasks(rows);
        setMembers(people);
      })
      .catch((err) => {
        if (!stale) setError(err instanceof Error ? err.message : String(err));
      });
    return () => {
      stale = true;
    };
  }, [projectId, tenantId]);

  async function add(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await createPlanTask(projectId, tenantId, {
        title,
        due_date: due || null,
        assignee_membership_id: assignee || null,
      });
      setTitle("");
      setDue("");
      setAssignee("");
      await reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  async function setStatus(task: PlanTask, status: PlanTask["status"]) {
    try {
      await patchPlanTask(projectId, task.id, tenantId, { status });
      await reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  async function remove(task: PlanTask) {
    try {
      await deletePlanTask(projectId, task.id, tenantId);
      await reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  const open = tasks?.filter((t) => t.status !== "done") ?? [];
  const done = tasks?.filter((t) => t.status === "done") ?? [];

  return (
    <div className="mt-7 w-full max-w-[620px] rounded-card border border-edge bg-card px-5 py-4 text-left shadow-card">
      <p className="data text-ink-muted uppercase">Plan</p>
      {error && <p className="mt-2 text-sm text-danger">{error}</p>}
      {tasks === null ? (
        <p className="mt-2 text-sm text-faint">Loading tasks…</p>
      ) : (
        <ul className="mt-3 space-y-2">
          {open.map((t) => (
            <li key={t.id} className="flex flex-wrap items-center gap-2 text-sm">
              <button
                type="button"
                onClick={() => setStatus(t, "done")}
                className="h-4 w-4 rounded-sm border border-edge-strong"
                aria-label={`Mark ${t.title} done`}
              />
              <span className="min-w-0 flex-1 font-semibold">{t.title}</span>
              {t.assignee_email && (
                <span className="text-xs text-faint">{t.assignee_email}</span>
              )}
              {t.due_date && (
                <span className="text-xs text-faint">{t.due_date}</span>
              )}
              <button
                type="button"
                onClick={() => remove(t)}
                className="text-xs text-faint hover:text-danger"
              >
                Remove
              </button>
            </li>
          ))}
          {open.length === 0 && (
            <li className="text-sm text-faint">No open tasks — add one below.</li>
          )}
        </ul>
      )}
      <form onSubmit={add} className="mt-3 flex flex-col gap-2 sm:flex-row sm:items-end">
        <input
          required
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="Task"
          className="min-w-0 flex-1 rounded-[10px] border border-edge bg-surface px-3 py-1.5 text-sm"
        />
        <input
          type="date"
          value={due}
          onChange={(e) => setDue(e.target.value)}
          className="rounded-[10px] border border-edge bg-surface px-3 py-1.5 text-sm"
        />
        <select
          value={assignee}
          onChange={(e) => setAssignee(e.target.value)}
          className="rounded-[10px] border border-edge bg-surface px-3 py-1.5 text-sm"
        >
          <option value="">Unassigned</option>
          {members.map((m) => (
            <option key={m.id} value={m.id}>
              {m.email ?? m.role}
            </option>
          ))}
        </select>
        <button
          type="submit"
          className="rounded-[10px] bg-accent px-3 py-1.5 text-sm font-medium text-accent-ink"
        >
          Add
        </button>
      </form>
      {done.length > 0 && (
        <p className="mt-3 text-xs text-faint">{done.length} done</p>
      )}
    </div>
  );
}
