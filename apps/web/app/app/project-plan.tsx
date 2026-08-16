"use client";

import { useEffect, useState } from "react";
import { fmtDate } from "@/lib/groundwork";
import {
  type MemberRow,
  type PlanTask,
  createPlanTask,
  deletePlanTask,
  enableProjectPlan,
  isOverdue,
  listMembers,
  listPlanTasks,
  patchPlanTask,
} from "@/lib/project-plan";
import { useWorkspace } from "./workspace";

const field =
  "rounded-card border border-edge bg-surface px-2 py-1 text-sm disabled:text-faint";

export default function ProjectPlanPanel({
  projectId,
  hasPlan,
  compact = false,
}: {
  projectId: string;
  hasPlan: boolean;
  compact?: boolean;
}) {
  const ws = useWorkspace();
  const tenantId = ws.tenant!.id;
  const [tasks, setTasks] = useState<PlanTask[] | null>(null);
  const [members, setMembers] = useState<MemberRow[]>([]);
  const [expanded, setExpanded] = useState(!compact);
  const [showDone, setShowDone] = useState(false);
  const [title, setTitle] = useState("");
  const [details, setDetails] = useState("");
  const [due, setDue] = useState("");
  const [assignee, setAssignee] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function reload() {
    setTasks(await listPlanTasks(projectId, tenantId));
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

  async function enable() {
    setBusy(true);
    setError(null);
    try {
      await enableProjectPlan(projectId, tenantId);
      await ws.refreshProjects();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  async function add(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await createPlanTask(projectId, tenantId, {
        title,
        details: details.trim() || null,
        due_date: due || null,
        assignee_membership_id: assignee || null,
      });
      setTitle("");
      setDetails("");
      setDue("");
      setAssignee("");
      await reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  async function patch(task: PlanTask, body: Parameters<typeof patchPlanTask>[3]) {
    try {
      await patchPlanTask(projectId, task.id, tenantId, body);
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

  async function move(task: PlanTask, dir: -1 | 1) {
    const open = (tasks ?? []).filter((t) => t.status !== "done");
    const i = open.findIndex((t) => t.id === task.id);
    const swap = open[i + dir];
    if (!swap) return;
    try {
      await patchPlanTask(projectId, task.id, tenantId, { position: swap.position });
      try {
        await patchPlanTask(projectId, swap.id, tenantId, { position: task.position });
      } catch (err) {
        // Undo the half-applied swap or two tasks share a position and the
        // order falls back to the created_at tiebreak.
        await patchPlanTask(projectId, task.id, tenantId, { position: task.position }).catch(
          () => undefined
        );
        throw err;
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      await reload();
    }
  }

  if (!hasPlan) {
    return (
      <div className="rounded-card border border-edge bg-card px-5 py-4 text-left shadow-card">
        {error && <p className="mb-2 text-sm text-danger">{error}</p>}
        <p className="text-sm font-semibold">This project is documents only.</p>
        <p className="mt-1 text-xs text-faint">Add a plan for tasks, people and due dates.</p>
        <button
          type="button"
          disabled={busy}
          onClick={enable}
          className="mt-3 rounded-btn bg-accent px-3 py-1.5 text-sm font-medium text-accent-ink disabled:opacity-50"
        >
          {busy ? "Adding…" : "Add a plan"}
        </button>
      </div>
    );
  }

  const open = (tasks ?? []).filter((t) => t.status !== "done");
  const done = (tasks ?? []).filter((t) => t.status === "done");
  const overdueN = open.filter((t) => isOverdue(t)).length;

  return (
    <div className="w-full rounded-card border border-edge bg-card px-5 py-4 text-left shadow-card">
      <div className="flex items-baseline gap-2">
        <p className="data text-ink-muted uppercase">Plan</p>
        {overdueN > 0 && (
          <span className="text-xs font-bold text-warn">
            {overdueN} overdue
          </span>
        )}
        {compact && (
          <button
            type="button"
            onClick={() => setExpanded((v) => !v)}
            className="ml-auto text-xs font-bold text-electric-blue hover:underline"
          >
            {expanded ? "Hide" : "Edit"}
          </button>
        )}
      </div>
      {error && <p className="mt-2 text-sm text-danger">{error}</p>}
      {tasks === null ? (
        <p className="mt-2 text-sm text-faint">Loading tasks…</p>
      ) : (
        <ul className="mt-3 space-y-2">
          {open.map((t, i) => (
            <TaskRow
              key={t.id}
              task={t}
              members={members}
              compact={compact && !expanded}
              canUp={i > 0}
              canDown={i < open.length - 1}
              onPatch={patch}
              onRemove={remove}
              onMove={move}
            />
          ))}
          {open.length === 0 && (
            <li className="text-sm text-faint">No open tasks — add one below.</li>
          )}
        </ul>
      )}

      {expanded && (
        <form onSubmit={add} className="mt-3 space-y-2">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-end">
            <input
              required
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Task"
              className={`min-w-0 flex-1 ${field}`}
            />
            <input
              type="date"
              value={due}
              onChange={(e) => setDue(e.target.value)}
              className={field}
            />
            <select
              value={assignee}
              onChange={(e) => setAssignee(e.target.value)}
              className={field}
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
              className="rounded-btn bg-accent px-3 py-1.5 text-sm font-medium text-accent-ink"
            >
              Add
            </button>
          </div>
          <input
            value={details}
            onChange={(e) => setDetails(e.target.value)}
            placeholder="Note (optional)"
            className={`w-full ${field}`}
          />
        </form>
      )}

      {done.length > 0 && (
        <div className="mt-3">
          <button
            type="button"
            onClick={() => setShowDone((v) => !v)}
            className="text-xs font-bold text-faint hover:text-ink"
          >
            {done.length} done{showDone ? " ▾" : " ▸"}
          </button>
          {showDone && (
            <ul className="mt-2 space-y-2">
              {done.map((t) => (
                <TaskRow
                  key={t.id}
                  task={t}
                  members={members}
                  compact={compact && !expanded}
                  canUp={false}
                  canDown={false}
                  onPatch={patch}
                  onRemove={remove}
                  onMove={move}
                />
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}

function TaskRow({
  task,
  members,
  compact,
  canUp,
  canDown,
  onPatch,
  onRemove,
  onMove,
}: {
  task: PlanTask;
  members: MemberRow[];
  compact: boolean;
  canUp: boolean;
  canDown: boolean;
  onPatch: (task: PlanTask, body: Parameters<typeof patchPlanTask>[3]) => void;
  onRemove: (task: PlanTask) => void;
  onMove: (task: PlanTask, dir: -1 | 1) => void;
}) {
  const done = task.status === "done";
  const late = isOverdue(task);
  const [noteOpen, setNoteOpen] = useState(Boolean(task.details) && !compact);

  if (compact) {
    return (
      <li className="flex items-center gap-2 text-sm">
        <Tick task={task} onPatch={onPatch} />
        <span className={`min-w-0 flex-1 font-semibold ${done ? "text-faint line-through" : ""}`}>
          {task.title}
        </span>
        {late && <span className="text-xs font-bold text-warn">overdue</span>}
        {task.due_date && !late && (
          <span className="text-xs text-faint">{fmtDate(task.due_date)}</span>
        )}
      </li>
    );
  }

  return (
    <li className="rounded-card border border-edge bg-surface px-2 py-2">
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <Tick task={task} onPatch={onPatch} />
        <input
          defaultValue={task.title}
          disabled={done}
          onBlur={(e) => {
            const next = e.target.value.trim();
            if (next && next !== task.title) onPatch(task, { title: next });
          }}
          className={`min-w-0 flex-1 bg-transparent font-semibold outline-none ${
            done ? "text-faint line-through" : ""
          }`}
        />
        <input
          type="date"
          value={task.due_date ?? ""}
          disabled={done}
          onChange={(e) => onPatch(task, { due_date: e.target.value || null })}
          className={`${field} ${late ? "border-warn text-warn" : ""}`}
        />
        <select
          value={task.assignee_membership_id ?? ""}
          disabled={done}
          onChange={(e) => onPatch(task, { assignee_membership_id: e.target.value || null })}
          className={field}
        >
          <option value="">Unassigned</option>
          {members.map((m) => (
            <option key={m.id} value={m.id}>
              {m.email ?? m.role}
            </option>
          ))}
        </select>
        {!done && (
          <>
            <button
              type="button"
              disabled={!canUp}
              onClick={() => onMove(task, -1)}
              className="text-xs text-faint hover:text-ink disabled:opacity-30"
              aria-label="Move up"
            >
              ↑
            </button>
            <button
              type="button"
              disabled={!canDown}
              onClick={() => onMove(task, 1)}
              className="text-xs text-faint hover:text-ink disabled:opacity-30"
              aria-label="Move down"
            >
              ↓
            </button>
          </>
        )}
        <button
          type="button"
          onClick={() => setNoteOpen((v) => !v)}
          className="text-xs text-faint hover:text-ink"
        >
          Note
        </button>
        <button
          type="button"
          onClick={() => onRemove(task)}
          className="text-xs text-faint hover:text-danger"
        >
          Remove
        </button>
      </div>
      {late && <p className="mt-1 pl-6 text-xs font-bold text-warn">Overdue</p>}
      {noteOpen && (
        <textarea
          defaultValue={task.details ?? ""}
          disabled={done}
          rows={2}
          placeholder="Details"
          onBlur={(e) => {
            const next = e.target.value.trim() || null;
            if (next !== (task.details || null)) onPatch(task, { details: next });
          }}
          className={`mt-2 w-full ${field}`}
        />
      )}
    </li>
  );
}

function Tick({
  task,
  onPatch,
}: {
  task: PlanTask;
  onPatch: (task: PlanTask, body: Parameters<typeof patchPlanTask>[3]) => void;
}) {
  const done = task.status === "done";
  return (
    <button
      type="button"
      onClick={() => onPatch(task, { status: done ? "todo" : "done" })}
      className={`grid h-4 w-4 place-items-center rounded-sm border ${
        done ? "border-grounded bg-grounded text-[10px] text-white" : "border-edge-strong"
      }`}
      aria-label={done ? `Reopen ${task.title}` : `Mark ${task.title} done`}
    >
      {done ? "✓" : null}
    </button>
  );
}
