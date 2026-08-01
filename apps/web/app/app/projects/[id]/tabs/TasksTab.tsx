"use client";

import { useState } from "react";
import { STAGE_LABEL, STAGES, Task, gw } from "@/lib/groundwork";
import { LoadError, useGwLoad } from "./load";
import { btn, input } from "./ui";

export function TasksTab({ id }: { id: string }) {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [stage, setStage] = useState("");
  const [status, setStatus] = useState("");
  const [overdue, setOverdue] = useState(false);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [newTitle, setNewTitle] = useState("");
  const [newStage, setNewStage] = useState("group");
  const [newDue, setNewDue] = useState("");
  const [newMilestone, setNewMilestone] = useState(false);

  const q = new URLSearchParams();
  if (stage) q.set("stage_key", stage);
  if (status) q.set("status", status);
  if (overdue) q.set("overdue", "true");
  const { failed, refresh } = useGwLoad<Task[]>(`/projects/${id}/tasks?${q}`, setTasks);

  async function add(e: React.FormEvent) {
    e.preventDefault();
    await gw(`/projects/${id}/tasks`, {
      method: "POST",
      body: JSON.stringify({
        stage_key: newStage,
        title: newTitle,
        due_date: newDue || null,
        is_milestone: newMilestone,
      }),
    });
    setNewTitle("");
    setNewDue("");
    setNewMilestone(false);
    refresh();
  }

  async function patch(t: Task, body: object) {
    await gw(`/projects/${id}/tasks/${t.id}`, { method: "PATCH", body: JSON.stringify(body) });
    refresh();
  }

  async function bulkComplete() {
    await gw(`/projects/${id}/tasks/bulk-complete`, {
      method: "POST",
      body: JSON.stringify({ ids: [...selected] }),
    });
    setSelected(new Set());
    refresh();
  }

  return (
    <div>
      <LoadError failed={failed} onRetry={refresh} />
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <select value={stage} onChange={(e) => setStage(e.target.value)} className={input}>
          <option value="">All stages</option>
          {STAGES.map((s) => (
            <option key={s} value={s}>
              {STAGE_LABEL[s]}
            </option>
          ))}
        </select>
        <select value={status} onChange={(e) => setStatus(e.target.value)} className={input}>
          <option value="">All statuses</option>
          <option value="todo">To do</option>
          <option value="doing">Doing</option>
          <option value="done">Done</option>
          <option value="na">N/A</option>
        </select>
        <label className="flex items-center gap-1.5 text-sm text-ink-muted">
          <input type="checkbox" checked={overdue} onChange={(e) => setOverdue(e.target.checked)} className="accent-(--accent)" />
          Overdue only
        </label>
        {selected.size > 0 && (
          <button onClick={bulkComplete} className={btn}>
            Mark {selected.size} done
          </button>
        )}
      </div>

      <ul className="divide-y divide-line rounded-card border border-edge bg-surface">
        {tasks.map((t) => (
          <li key={t.id} className="flex items-center gap-3 px-4 py-2.5 text-sm">
            <input
              type="checkbox"
              checked={selected.has(t.id)}
              onChange={(e) => {
                const next = new Set(selected);
                if (e.target.checked) next.add(t.id);
                else next.delete(t.id);
                setSelected(next);
              }}
              className="accent-(--accent)"
            />
            <span className="data w-12 shrink-0 text-ink-faint uppercase">{t.stage_key}</span>
            <span className={`min-w-0 flex-1 truncate ${t.status === "done" ? "text-ink-faint line-through" : ""}`} title={t.details ?? undefined}>
              {t.is_milestone && <span title="Milestone">⚑ </span>}
              {t.title}
              {t.tags.length > 0 && (
                <span className="data ml-1.5 text-ink-faint">{t.tags.join(" · ")}</span>
              )}
            </span>
            <input
              type="date"
              defaultValue={t.due_date ?? ""}
              onBlur={(e) => e.target.value !== (t.due_date ?? "") && patch(t, { due_date: e.target.value || null })}
              className={`${input} ${t.due_date && new Date(t.due_date) < new Date() && t.status !== "done" ? "text-danger" : ""}`}
            />
            <select value={t.status} onChange={(e) => patch(t, { status: e.target.value })} className={input}>
              <option value="todo">To do</option>
              <option value="doing">Doing</option>
              <option value="done">Done</option>
              <option value="na">N/A</option>
            </select>
          </li>
        ))}
      </ul>

      <form onSubmit={add} className="mt-3 flex flex-wrap items-center gap-2">
        <select value={newStage} onChange={(e) => setNewStage(e.target.value)} className={input}>
          {STAGES.map((s) => (
            <option key={s} value={s}>
              {STAGE_LABEL[s]}
            </option>
          ))}
        </select>
        <input required value={newTitle} onChange={(e) => setNewTitle(e.target.value)} placeholder="Add a task…" className={`min-w-0 flex-1 ${input}`} />
        <input type="date" value={newDue} onChange={(e) => setNewDue(e.target.value)} className={input} />
        <label className="flex items-center gap-1 text-sm text-ink-muted">
          <input type="checkbox" checked={newMilestone} onChange={(e) => setNewMilestone(e.target.checked)} className="accent-(--accent)" />
          Milestone
        </label>
        <button type="submit" className={btn}>
          Add
        </button>
      </form>
    </div>
  );
}
