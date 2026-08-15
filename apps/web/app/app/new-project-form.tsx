"use client";

import { useEffect, useState } from "react";
import { fmtDate } from "@/lib/groundwork";
import { listMembers, type MemberRow, type PlanTaskSeed } from "@/lib/project-plan";
import { useWorkspace } from "./workspace";

type Kind = "blank" | "planned";

export default function NewProjectForm({
  onCreated,
  onCancel,
}: {
  onCreated: (projectId: string) => void;
  onCancel: () => void;
}) {
  const ws = useWorkspace();
  const [name, setName] = useState("");
  const [kind, setKind] = useState<Kind>("blank");
  const [members, setMembers] = useState<MemberRow[]>([]);
  const [taskTitle, setTaskTitle] = useState("");
  const [taskDue, setTaskDue] = useState("");
  const [taskAssignee, setTaskAssignee] = useState("");
  const [seeds, setSeeds] = useState<PlanTaskSeed[]>([]);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!ws.tenant || kind !== "planned") return;
    listMembers(ws.tenant.id).then(setMembers).catch(() => setMembers([]));
  }, [kind, ws.tenant]);

  function addSeed() {
    if (!taskTitle.trim()) return;
    setSeeds((s) => [
      ...s,
      {
        title: taskTitle.trim(),
        due_date: taskDue || null,
        assignee_membership_id: taskAssignee || null,
      },
    ]);
    setTaskTitle("");
    setTaskDue("");
    setTaskAssignee("");
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    // A task typed but not yet added with the button still counts — Create
    // must not silently discard it.
    const pending = taskTitle.trim()
      ? [
          {
            title: taskTitle.trim(),
            due_date: taskDue || null,
            assignee_membership_id: taskAssignee || null,
          },
        ]
      : [];
    const created = await ws.createProject(name, {
      kind,
      tasks: kind === "planned" ? [...seeds, ...pending] : undefined,
    });
    setBusy(false);
    if (created) onCreated(created.id);
  }

  const card = (k: Kind, title: string, hint: string) => (
    <button
      type="button"
      onClick={() => setKind(k)}
      className={`rounded-[10px] border px-3 py-2 text-left ${
        kind === k ? "border-accent bg-accent-soft" : "border-edge bg-card"
      }`}
    >
      <span className="block text-[13px] font-bold">{title}</span>
      <span className="block text-[11px] text-faint">{hint}</span>
    </button>
  );

  return (
    <form
      onSubmit={submit}
      className="mt-1 space-y-2 rounded-[10px] border border-edge bg-card p-2"
      onClick={(e) => e.stopPropagation()}
    >
      <input
        autoFocus
        required
        value={name}
        onChange={(e) => setName(e.target.value)}
        placeholder="Project name"
        className="w-full rounded-[10px] border border-edge bg-surface px-3 py-1.5 text-sm placeholder:text-faint focus:outline-none"
      />
      <div className="grid grid-cols-2 gap-1.5">
        {card("blank", "Documents", "Vault and chat only")}
        {card("planned", "With a plan", "Tasks, people, dates")}
      </div>
      {kind === "planned" && (
        <div className="space-y-1.5">
          {seeds.map((s, i) => (
            <p key={`${s.title}-${i}`} className="truncate text-[11px] text-subtle">
              {s.title}
              {s.due_date ? ` · ${fmtDate(s.due_date)}` : ""}
            </p>
          ))}
          <input
            value={taskTitle}
            onChange={(e) => setTaskTitle(e.target.value)}
            placeholder="First task (optional)"
            className="w-full rounded-[10px] border border-edge bg-surface px-3 py-1.5 text-sm"
          />
          <div className="flex gap-1">
            <input
              type="date"
              value={taskDue}
              onChange={(e) => setTaskDue(e.target.value)}
              className="min-w-0 flex-1 rounded-[10px] border border-edge bg-surface px-2 py-1 text-xs"
            />
            <select
              value={taskAssignee}
              onChange={(e) => setTaskAssignee(e.target.value)}
              className="min-w-0 flex-1 rounded-[10px] border border-edge bg-surface px-2 py-1 text-xs"
            >
              <option value="">Anyone</option>
              {members.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.email ?? m.role}
                </option>
              ))}
            </select>
          </div>
          <button
            type="button"
            onClick={addSeed}
            disabled={!taskTitle.trim()}
            className="text-[11px] font-bold text-accent-deep hover:underline disabled:text-faint"
          >
            Add task
          </button>
        </div>
      )}
      <div className="flex gap-2">
        <button
          type="submit"
          disabled={busy}
          className="flex-1 rounded-[10px] bg-accent px-3 py-1.5 text-xs font-bold text-accent-ink disabled:opacity-50"
        >
          {busy ? "Creating…" : "Create"}
        </button>
        <button
          type="button"
          onClick={onCancel}
          className="text-xs font-bold text-faint hover:text-ink"
        >
          Cancel
        </button>
      </div>
    </form>
  );
}
