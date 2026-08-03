"use client";

import { useState } from "react";
import { STAGES, STAGE_LABEL, Task, fmtDate, gr } from "@/lib/grants";
import { btnGhost, card, input } from "../../ui";
import { LoadError, useGrantLoad } from "./load";

const NEXT_STATUS: Record<string, string> = { todo: "doing", doing: "done", done: "todo" };

export function TasksTab({ id }: { id: string }) {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [stageFilter, setStageFilter] = useState("");
  const [adding, setAdding] = useState(false);
  const [draft, setDraft] = useState({ title: "", stage_key: "case", due_date: "" });
  const { failed, refresh } = useGrantLoad<Task[]>(`/grants/applications/${id}/tasks`, setTasks);

  const shown = stageFilter ? tasks.filter((t) => t.stage_key === stageFilter) : tasks;
  const open = tasks.filter((t) => t.status === "todo" || t.status === "doing").length;

  async function cycle(task: Task) {
    await gr(`/grants/applications/${id}/tasks/${task.id}`, {
      method: "PATCH",
      body: JSON.stringify({ status: NEXT_STATUS[task.status] ?? "todo" }),
    });
    refresh();
  }

  async function add(e: React.FormEvent) {
    e.preventDefault();
    if (!draft.title.trim()) return;
    await gr(`/grants/applications/${id}/tasks`, {
      method: "POST",
      body: JSON.stringify({
        title: draft.title.trim(),
        stage_key: draft.stage_key,
        due_date: draft.due_date || null,
      }),
    });
    setDraft({ title: "", stage_key: draft.stage_key, due_date: "" });
    setAdding(false);
    refresh();
  }

  return (
    <div>
      <LoadError failed={failed} onRetry={refresh} />
      <div className="mb-3 flex flex-wrap items-center gap-3">
        <select
          value={stageFilter}
          onChange={(e) => setStageFilter(e.target.value)}
          className={input}
        >
          <option value="">All stages</option>
          {STAGES.map((s) => (
            <option key={s} value={s}>
              {STAGE_LABEL[s]}
            </option>
          ))}
        </select>
        <span className="text-sm text-ink-muted">{open} open</span>
        <button onClick={() => setAdding((v) => !v)} className={`${btnGhost} ml-auto`}>
          {adding ? "Cancel" : "Add a task"}
        </button>
      </div>

      {adding && (
        <form onSubmit={add} className={`${card} mb-3 flex flex-wrap gap-2 p-3`}>
          <input
            autoFocus
            value={draft.title}
            onChange={(e) => setDraft({ ...draft, title: e.target.value })}
            placeholder="What needs doing"
            className={`${input} flex-1`}
          />
          <select
            value={draft.stage_key}
            onChange={(e) => setDraft({ ...draft, stage_key: e.target.value })}
            className={input}
          >
            {STAGES.map((s) => (
              <option key={s} value={s}>
                {STAGE_LABEL[s]}
              </option>
            ))}
          </select>
          <input
            type="date"
            value={draft.due_date}
            onChange={(e) => setDraft({ ...draft, due_date: e.target.value })}
            className={input}
          />
          <button type="submit" className={input}>
            Add
          </button>
        </form>
      )}

      <div className={`divide-y divide-line ${card}`}>
        {shown.map((task) => {
          const overdue =
            task.due_date &&
            new Date(task.due_date) < new Date() &&
            task.status !== "done" &&
            task.status !== "na";
          return (
            <div key={task.id} className="flex items-start gap-3 px-4 py-2.5 text-sm">
              <button
                onClick={() => cycle(task)}
                className="data mt-0.5 w-14 shrink-0 text-left uppercase text-ink-muted hover:text-ink"
                title="Click to advance"
              >
                {task.status}
              </button>
              <span className="flex-1">
                <span className={task.status === "done" ? "text-ink-muted line-through" : ""}>
                  {task.title}
                </span>
                {task.is_milestone && (
                  <span className="stamp ml-2 text-accent bg-accent-soft">milestone</span>
                )}
                {task.details && (
                  <span className="mt-0.5 block text-xs text-ink-faint">{task.details}</span>
                )}
              </span>
              <span className="data w-24 shrink-0 text-ink-faint">
                {STAGE_LABEL[task.stage_key]}
              </span>
              <span className={`data w-20 shrink-0 ${overdue ? "text-danger" : "text-ink-faint"}`}>
                {fmtDate(task.due_date)}
              </span>
            </div>
          );
        })}
        {shown.length === 0 && (
          <p className="px-4 py-6 text-center text-sm text-ink-muted">No tasks at this stage.</p>
        )}
      </div>
    </div>
  );
}
