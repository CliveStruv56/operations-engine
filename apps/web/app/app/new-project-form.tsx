"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { fmtDate } from "@/lib/groundwork";
import { listMembers, type MemberRow, type PlanTaskSeed } from "@/lib/project-plan";
import { GENERAL_KIND, SETUP_PATHS } from "@/lib/projects";
import { useWorkspace } from "./workspace";

export default function NewProjectForm({
  onCreated,
  onCancel,
  onLeave,
}: {
  onCreated: (projectId: string) => void;
  onCancel: () => void;
  /** Called when the form hands over to another page (a setup kind), so the
   *  mobile sidebar it sits in closes too. */
  onLeave?: () => void;
}) {
  const ws = useWorkspace();
  const router = useRouter();
  const [name, setName] = useState("");
  // Only kinds this workspace has, and only ones the form can reach: inline
  // kinds, or setup kinds whose page the web knows (lib/projects.ts).
  const kinds = ws.projectKinds.kinds.filter(
    (k) => k.available && (k.create === "inline" || SETUP_PATHS[k.key])
  );
  const [kindKey, setKindKey] = useState(GENERAL_KIND.key);
  const kind = kinds.find((k) => k.key === kindKey) ?? GENERAL_KIND;
  const [withPlan, setWithPlan] = useState(false);
  const planning = kind.create === "inline" && withPlan;
  const [members, setMembers] = useState<MemberRow[]>([]);
  const [taskTitle, setTaskTitle] = useState("");
  const [taskDue, setTaskDue] = useState("");
  const [taskAssignee, setTaskAssignee] = useState("");
  const [seeds, setSeeds] = useState<PlanTaskSeed[]>([]);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!ws.tenant || !planning) return;
    listMembers(ws.tenant.id).then(setMembers).catch(() => setMembers([]));
  }, [planning, ws.tenant]);

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
    if (kind.create === "setup") {
      // A module kind is set up on its own page, which creates the project.
      router.push(`${SETUP_PATHS[kind.key]}?name=${encodeURIComponent(name)}`);
      onCancel();
      onLeave?.();
      return;
    }
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
      withPlan: planning,
      tasks: planning ? [...seeds, ...pending] : undefined,
    });
    setBusy(false);
    if (created) onCreated(created.id);
  }


  return (
    <form
      onSubmit={submit}
      className="mt-1 space-y-2 rounded-card border border-edge bg-card p-2"
      onClick={(e) => e.stopPropagation()}
    >
      <input
        autoFocus
        required
        value={name}
        onChange={(e) => setName(e.target.value)}
        placeholder="Project name"
        className="w-full rounded-card border border-edge bg-surface px-3 py-1.5 text-sm placeholder:text-faint focus:outline-none"
      />
      {kinds.length > 1 && (
        <div role="radiogroup" aria-label="Kind of project" className="grid gap-1.5">
          {kinds.map((k) => (
            <button
              key={k.key}
              type="button"
              role="radio"
              aria-checked={kind.key === k.key}
              onClick={() => setKindKey(k.key)}
              className={`rounded-card border px-3 py-2 text-left ${
                kind.key === k.key ? "border-deep-violet bg-accent-soft" : "border-edge bg-card"
              }`}
            >
              <span className="block text-[13px] font-bold">{k.label}</span>
              <span className="block text-xs text-faint">{k.description}</span>
            </button>
          ))}
        </div>
      )}
      {kind.create === "inline" ? (
        <label className="flex items-start gap-2 text-xs text-subtle">
          <input
            type="checkbox"
            checked={withPlan}
            onChange={(e) => setWithPlan(e.target.checked)}
            className="mt-0.5"
          />
          <span>
            <span className="font-semibold text-ink">Add a plan</span> — tasks, people, dates
          </span>
        </label>
      ) : (
        <p className="text-xs text-subtle">You&rsquo;ll set it up on the next page.</p>
      )}
      {planning && (
        <div className="space-y-1.5">
          {seeds.map((s, i) => (
            <p key={`${s.title}-${i}`} className="truncate text-xs text-subtle">
              {s.title}
              {s.due_date ? ` · ${fmtDate(s.due_date)}` : ""}
            </p>
          ))}
          <input
            value={taskTitle}
            onChange={(e) => setTaskTitle(e.target.value)}
            placeholder="First task (optional)"
            className="w-full rounded-card border border-edge bg-surface px-3 py-1.5 text-sm"
          />
          <div className="flex gap-1">
            <input
              type="date"
              value={taskDue}
              onChange={(e) => setTaskDue(e.target.value)}
              className="min-w-0 flex-1 rounded-card border border-edge bg-surface px-2 py-1 text-xs"
            />
            <select
              value={taskAssignee}
              onChange={(e) => setTaskAssignee(e.target.value)}
              className="min-w-0 flex-1 rounded-card border border-edge bg-surface px-2 py-1 text-xs"
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
            className="text-xs font-bold text-electric-blue hover:underline disabled:text-faint"
          >
            Add task
          </button>
        </div>
      )}
      <div className="flex gap-2">
        <button
          type="submit"
          disabled={busy}
          className="flex-1 rounded-btn bg-accent px-3 py-1.5 text-xs font-bold text-accent-ink disabled:opacity-50"
        >
          {busy ? "Creating…" : kind.create === "setup" ? "Continue" : "Create"}
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
