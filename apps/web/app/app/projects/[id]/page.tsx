"use client";

import { use, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  BudgetLine,
  Condition,
  Detail,
  Funding,
  Programme,
  RegistryDoc,
  Risk,
  Stage,
  Stakeholder,
  STAGE_LABEL,
  STAGES,
  Task,
  fmtDate,
  fmtMoney,
  gw,
  openPresigned,
} from "@/lib/groundwork";
import { RagDots } from "../page";

const TABS = [
  "Overview",
  "Stages & gates",
  "Tasks",
  "Documents",
  "Funding",
  "Budget",
  "Risks",
  "Conditions",
  "Stakeholders",
] as const;

const input = "rounded-sm border border-line bg-surface px-2 py-1 text-sm";
const btn = "rounded-sm bg-accent px-3 py-1.5 text-sm font-medium text-accent-ink hover:opacity-90 disabled:opacity-50";
const btnGhost = "text-xs text-ink-muted underline hover:text-ink";

export default function ProjectRoom({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [detail, setDetail] = useState<Detail | null>(null);
  const [tab, setTab] = useState<(typeof TABS)[number]>("Overview");
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(
    () =>
      gw<Detail>(`/projects/${id}/groundwork`)
        .then(setDetail)
        .catch((e) => setError(e instanceof Error ? e.message : String(e))),
    [id]
  );
  useEffect(() => {
     
    refresh();
  }, [refresh]);

  async function changeStatus(status: string) {
    let dormancy_reason: string | null = null;
    if (status === "dormant") {
      dormancy_reason = window.prompt(
        "Why is this project going dormant? (e.g. funding_gap, group_capacity)"
      );
      if (!dormancy_reason) return;
    }
    await gw(`/projects/${id}/status`, {
      method: "POST",
      body: JSON.stringify({ status, dormancy_reason }),
    });
    refresh();
  }

  if (error)
    return (
      <main className="p-8">
        <p className="rounded-sm bg-danger-soft px-3 py-2 text-sm text-danger">{error}</p>
      </main>
    );
  if (!detail) return <main className="p-8 data text-ink-faint">Loading project…</main>;

  const hrb = detail.applicability?.hrb;

  return (
    <main className="mx-auto max-w-6xl p-6">
      <p className="data text-ink-faint uppercase">
        <Link href="/app/projects" className="hover:text-ink">
          ← Development projects
        </Link>
      </p>
      <header className="mt-1 mb-4 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">{detail.name}</h1>
          <p className="mt-0.5 text-sm text-ink-muted">
            {detail.client_org ?? "No client group set"}
            {detail.homes_planned ? ` · ${detail.homes_planned} homes` : ""}
            {detail.site_address ? ` · ${detail.site_address}` : ""}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <span className="flex items-center gap-1">
            {STAGES.map((s) => (
              <button
                key={s}
                onClick={() => setTab("Stages & gates")}
                className={`stamp ${
                  s === detail.stage_current
                    ? "bg-accent text-accent-ink border-accent"
                    : "text-ink-faint"
                }`}
              >
                {STAGE_LABEL[s]}
              </button>
            ))}
          </span>
          <select
            value={detail.status}
            onChange={(e) => changeStatus(e.target.value)}
            className={input}
            title="Project status"
          >
            <option value="active">Active</option>
            <option value="dormant">Dormant…</option>
            <option value="complete">Complete</option>
            <option value="archived">Archived</option>
          </select>
        </div>
      </header>

      {detail.status === "dormant" && (
        <p className="mb-3 rounded-sm bg-warn-soft px-3 py-2 text-sm text-warn">
          Dormant — {detail.dormancy_reason}. Set the project back to Active to resume.
        </p>
      )}
      {hrb && (
        <p className="mb-3 rounded-sm bg-warn-soft px-3 py-2 text-sm text-warn">
          Higher-Risk Building — Building Safety Act gateways apply; track them manually for now.
        </p>
      )}

      <nav className="mb-5 flex flex-wrap gap-1 border-b border-line">
        {TABS.map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-3 py-2 text-sm ${
              tab === t
                ? "border-b-2 border-accent font-medium"
                : "text-ink-muted hover:text-ink"
            }`}
          >
            {t}
          </button>
        ))}
      </nav>

      {tab === "Overview" && <OverviewTab id={id} />}
      {tab === "Stages & gates" && <StagesTab id={id} onAdvanced={refresh} />}
      {tab === "Tasks" && <TasksTab id={id} />}
      {tab === "Documents" && <DocumentsTab id={id} />}
      {tab === "Funding" && <FundingTab id={id} />}
      {tab === "Budget" && <BudgetTab id={id} />}
      {tab === "Risks" && <RisksTab id={id} />}
      {tab === "Conditions" && <ConditionsTab id={id} />}
      {tab === "Stakeholders" && <StakeholdersTab id={id} />}
    </main>
  );
}

// ---------------------------------------------------------------- Overview

function OverviewTab({ id }: { id: string }) {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [funding, setFunding] = useState<Funding[]>([]);
  const [risks, setRisks] = useState<Risk[]>([]);
  const [activity, setActivity] = useState<{ action: string; created_at: string }[]>([]);
  const [portfolio, setPortfolio] = useState<Detail["rag"] | null>(null);

  useEffect(() => {
     
    gw<Task[]>(`/projects/${id}/tasks?status=todo`).then(setTasks).catch(() => {});
    gw<Funding[]>(`/projects/${id}/funding`).then(setFunding).catch(() => {});
    gw<Risk[]>(`/projects/${id}/risks`).then(setRisks).catch(() => {});
    gw<{ action: string; created_at: string }[]>(`/projects/${id}/activity`)
      .then(setActivity)
      .catch(() => {});
    gw<{ id: string; rag: Detail["rag"] }[]>("/projects/portfolio")
      .then((rows) => setPortfolio(rows.find((r) => r.id === id)?.rag ?? null))
      .catch(() => {});
  }, [id]);

  const milestones = tasks
    .filter((t) => t.is_milestone && t.due_date)
    .sort((a, b) => (a.due_date! < b.due_date! ? -1 : 1))
    .slice(0, 5);
  const sought = funding.reduce((s, f) => s + (f.amount_sought ?? 0), 0);
  const secured = funding.reduce((s, f) => s + (f.amount_secured ?? 0), 0);
  const topRisks = risks.filter((r) => r.status === "open").slice(0, 3);

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
      <section className="rounded-md border border-line bg-surface p-4">
        <h3 className="data mb-2 text-ink-muted uppercase">Health</h3>
        {portfolio ? <RagDots rag={portfolio} /> : <p className="data text-ink-faint">…</p>}
        <p className="mt-2 text-xs text-ink-faint">
          Programme · Cost · Risk — hover each dot for what drives it.
        </p>
        <div className="mt-4 flex gap-2">
          <button disabled title="Arrives with drafting in week 3" className={`${btn} opacity-40`}>
            Draft monthly report
          </button>
          <button disabled title="Arrives in week 4" className={`${btn} opacity-40`}>
            Health card (PDF)
          </button>
        </div>
      </section>

      <section className="rounded-md border border-line bg-surface p-4">
        <h3 className="data mb-2 text-ink-muted uppercase">Funding position</h3>
        <p className="text-sm">
          Sought {fmtMoney(sought)} · Secured{" "}
          <span className="font-medium text-accent">{fmtMoney(secured)}</span>
        </p>
        <p className="mt-1 text-xs text-ink-faint">{funding.length} source(s) in the stack</p>
      </section>

      <section className="rounded-md border border-line bg-surface p-4">
        <h3 className="data mb-2 text-ink-muted uppercase">Next milestones</h3>
        {milestones.length === 0 && (
          <p className="text-sm text-ink-faint">No dated milestones yet — add due dates in Tasks.</p>
        )}
        <ul className="space-y-1.5">
          {milestones.map((m) => (
            <li key={m.id} className="flex justify-between text-sm">
              <span>⚑ {m.title}</span>
              <span
                className={`data ${
                  new Date(m.due_date!) < new Date() ? "text-danger" : "text-ink-muted"
                }`}
              >
                {fmtDate(m.due_date)}
              </span>
            </li>
          ))}
        </ul>
      </section>

      <section className="rounded-md border border-line bg-surface p-4">
        <h3 className="data mb-2 text-ink-muted uppercase">Top open risks</h3>
        {topRisks.length === 0 && <p className="text-sm text-ink-faint">No open risks.</p>}
        <ul className="space-y-1.5">
          {topRisks.map((r) => (
            <li key={r.id} className="flex justify-between gap-2 text-sm">
              <span className="truncate">{r.description}</span>
              <span className="data shrink-0 text-ink-muted">
                {r.likelihood}×{r.impact}={r.likelihood * r.impact}
              </span>
            </li>
          ))}
        </ul>
      </section>

      <section className="rounded-md border border-line bg-surface p-4 lg:col-span-2">
        <h3 className="data mb-2 text-ink-muted uppercase">Recent activity</h3>
        <ul className="space-y-1">
          {activity.map((a, i) => (
            <li key={i} className="data text-ink-muted">
              {fmtDate(a.created_at)} · {a.action.replace("projects.", "").replaceAll("_", " ")}
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}

// ---------------------------------------------------------- Stages & gates

function StagesTab({ id, onAdvanced }: { id: string; onAdvanced: () => void }) {
  const [stages, setStages] = useState<Stage[]>([]);
  const [open, setOpen] = useState<string | null>(null);
  const [exceptions, setExceptions] = useState("");
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(
    () => gw<Stage[]>(`/projects/${id}/stages`).then(setStages).catch(() => {}),
    [id]
  );
  useEffect(() => {
     
    refresh();
  }, [refresh]);

  async function toggle(stage: Stage, itemId: string) {
    try {
      await gw(`/projects/${id}/stages/${stage.id}/gate/${itemId}/toggle`, { method: "POST" });
      refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  async function signoff(stage: Stage) {
    setError(null);
    try {
      await gw(`/projects/${id}/stages/${stage.id}/signoff`, {
        method: "POST",
        body: JSON.stringify({ exceptions: exceptions || null }),
      });
      setExceptions("");
      refresh();
      onAdvanced();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  async function setDate(stage: Stage, field: string, value: string) {
    await gw(`/projects/${id}/stages/${stage.id}`, {
      method: "PATCH",
      body: JSON.stringify({ [field]: value || null }),
    });
    refresh();
  }

  return (
    <div className="space-y-3">
      {error && <p className="rounded-sm bg-danger-soft px-3 py-2 text-sm text-danger">{error}</p>}
      {stages.map((s) => {
        const outstanding = s.gate.filter((g) => !g.done).length;
        const expanded = open === s.id;
        return (
          <section key={s.id} className="rounded-md border border-line bg-surface">
            <button
              onClick={() => setOpen(expanded ? null : s.id)}
              className="flex w-full items-center justify-between px-4 py-3 text-left"
            >
              <span className="flex items-center gap-3">
                <span className="font-medium">{s.label}</span>
                {s.riba_ref && <span className="data text-ink-faint">{s.riba_ref}</span>}
                <span
                  className={`stamp ${
                    s.status === "passed"
                      ? "text-accent bg-accent-soft"
                      : s.status === "active"
                        ? "text-warn bg-warn-soft"
                        : s.status === "regressed"
                          ? "text-danger bg-danger-soft"
                          : "text-ink-faint"
                  }`}
                >
                  {s.status}
                </span>
              </span>
              <span className="data text-ink-muted">
                {s.gate_signed_off_at
                  ? `signed off ${fmtDate(s.gate_signed_off_at)}`
                  : `${s.gate.length - outstanding}/${s.gate.length} gate items`}
              </span>
            </button>
            {expanded && (
              <div className="border-t border-line px-4 py-3">
                <div className="mb-3 grid grid-cols-2 gap-2 sm:grid-cols-3">
                  {(
                    [
                      ["planned_start", "Planned start"],
                      ["planned_end", "Planned end"],
                      ["forecast_start", "Forecast start"],
                      ["forecast_end", "Forecast end"],
                      ["actual_start", "Actual start"],
                      ["actual_end", "Actual end"],
                    ] as const
                  ).map(([field, label]) => (
                    <label key={field} className="text-xs text-ink-muted">
                      {label}
                      <input
                        type="date"
                        defaultValue={(s[field] as string | null) ?? ""}
                        onBlur={(e) => setDate(s, field, e.target.value)}
                        className={`mt-0.5 block w-full ${input}`}
                      />
                    </label>
                  ))}
                </div>
                <ul className="space-y-1.5">
                  {s.gate.map((g) => (
                    <li key={g.id} className="flex items-center gap-2 text-sm">
                      {g.kind === "manual" ? (
                        <input
                          type="checkbox"
                          checked={g.done}
                          onChange={() => toggle(s, g.id)}
                          disabled={!!s.gate_signed_off_at}
                          className="accent-(--accent)"
                        />
                      ) : (
                        <span
                          title="Follows the document registry — reaches done when the linked document is final or submitted"
                          className={`data ${g.done ? "text-accent" : "text-ink-faint"}`}
                        >
                          {g.done ? "▣" : "▢"}
                        </span>
                      )}
                      <span className={g.done ? "text-ink-muted line-through" : ""}>
                        {g.criterion}
                      </span>
                      {g.kind === "doc" && (
                        <span className="data text-ink-faint">from registry: {g.ref}</span>
                      )}
                    </li>
                  ))}
                </ul>
                {s.gate_exceptions && (
                  <p className="mt-3 rounded-sm bg-warn-soft px-3 py-2 text-xs whitespace-pre-wrap text-warn">
                    Exceptions & notes: {s.gate_exceptions}
                  </p>
                )}
                {!s.gate_signed_off_at && (
                  <div className="mt-3 flex items-center gap-2">
                    {outstanding > 0 && (
                      <input
                        value={exceptions}
                        onChange={(e) => setExceptions(e.target.value)}
                        placeholder={`${outstanding} item(s) outstanding — record exceptions to sign off anyway`}
                        className={`min-w-0 flex-1 ${input}`}
                      />
                    )}
                    <button
                      onClick={() => signoff(s)}
                      disabled={outstanding > 0 && !exceptions}
                      className={btn}
                    >
                      Sign off gate
                    </button>
                  </div>
                )}
              </div>
            )}
          </section>
        );
      })}
    </div>
  );
}

// ------------------------------------------------------------------- Tasks

function TasksTab({ id }: { id: string }) {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [stage, setStage] = useState("");
  const [status, setStatus] = useState("");
  const [overdue, setOverdue] = useState(false);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [newTitle, setNewTitle] = useState("");
  const [newStage, setNewStage] = useState("group");
  const [newDue, setNewDue] = useState("");
  const [newMilestone, setNewMilestone] = useState(false);

  const refresh = useCallback(() => {
    const q = new URLSearchParams();
    if (stage) q.set("stage_key", stage);
    if (status) q.set("status", status);
    if (overdue) q.set("overdue", "true");
    return gw<Task[]>(`/projects/${id}/tasks?${q}`).then(setTasks).catch(() => {});
  }, [id, stage, status, overdue]);
  useEffect(() => {
     
    refresh();
  }, [refresh]);

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

      <ul className="divide-y divide-line rounded-md border border-line bg-surface">
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

// --------------------------------------------------------------- Documents

function DocumentsTab({ id }: { id: string }) {
  const [docs, setDocs] = useState<RegistryDoc[]>([]);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(
    () => gw<RegistryDoc[]>(`/projects/${id}/documents`).then(setDocs).catch(() => {}),
    [id]
  );
  useEffect(() => {
     
    refresh();
  }, [refresh]);

  async function setStatus(d: RegistryDoc, status: string) {
    await gw(`/projects/${id}/documents/${d.id}`, {
      method: "PATCH",
      body: JSON.stringify({ status }),
    });
    refresh();
  }

  async function upload(d: RegistryDoc, file: File) {
    setError(null);
    try {
      const { upload_url, file_key } = await gw<{ upload_url: string; file_key: string }>(
        `/projects/${id}/documents/${d.id}/upload`,
        {
          method: "POST",
          body: JSON.stringify({ filename: file.name, mime: file.type, size_bytes: file.size }),
        }
      );
      const put = await fetch(upload_url, {
        method: "PUT",
        headers: { "Content-Type": file.type },
        body: file,
      });
      if (!put.ok) throw new Error(`Upload failed (${put.status})`);
      await gw(`/projects/${id}/documents/${d.id}/upload/complete`, {
        method: "POST",
        body: JSON.stringify({ file_key }),
      });
      refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  async function download(d: RegistryDoc) {
    const { download_url } = await gw<{ download_url: string }>(
      `/projects/${id}/documents/${d.id}/download`
    );
    openPresigned(download_url);
  }

  return (
    <div>
      {error && <p className="mb-2 rounded-sm bg-danger-soft px-3 py-2 text-sm text-danger">{error}</p>}
      <table className="w-full rounded-md border border-line bg-surface text-sm">
        <thead>
          <tr className="data border-b border-line text-left text-ink-muted uppercase">
            <th className="px-4 py-2">Document</th>
            <th className="px-4 py-2">Stage</th>
            <th className="px-4 py-2">Status</th>
            <th className="px-4 py-2">Versions</th>
            <th className="px-4 py-2">Updated</th>
            <th className="px-4 py-2" />
          </tr>
        </thead>
        <tbody className="divide-y divide-line">
          {docs.map((d) => (
            <tr key={d.id}>
              <td className="px-4 py-2 font-medium">{d.title}</td>
              <td className="data px-4 py-2 text-ink-muted uppercase">{d.stage_key}</td>
              <td className="px-4 py-2">
                <select value={d.status} onChange={(e) => setStatus(d, e.target.value)} className={input}>
                  {["required", "drafting", "review", "final", "submitted", "na"].map((s) => (
                    <option key={s} value={s}>
                      {s}
                    </option>
                  ))}
                </select>
              </td>
              <td className="data px-4 py-2">{d.versions.length}</td>
              <td className="data px-4 py-2 text-ink-faint">{fmtDate(d.updated_at)}</td>
              <td className="px-4 py-2">
                <span className="flex items-center gap-3">
                  <label className={btnGhost}>
                    Upload
                    <input
                      type="file"
                      accept=".pdf,.docx,.xlsx"
                      className="hidden"
                      onChange={(e) => e.target.files?.[0] && upload(d, e.target.files[0])}
                    />
                  </label>
                  {d.current_file_key && (
                    <button onClick={() => download(d)} className={btnGhost}>
                      Download
                    </button>
                  )}
                  {d.ai_draftable && (
                    <button disabled title="Drafting arrives in week 3" className="stamp opacity-40">
                      Draft with AI
                    </button>
                  )}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ----------------------------------------------------------------- Funding

function FundingTab({ id }: { id: string }) {
  const [stack, setStack] = useState<Funding[]>([]);
  const [browse, setBrowse] = useState(false);
  const [programmes, setProgrammes] = useState<Programme[]>([]);
  const [nation, setNation] = useState("");
  const [expanded, setExpanded] = useState<string | null>(null);

  const refresh = useCallback(
    () => gw<Funding[]>(`/projects/${id}/funding`).then(setStack).catch(() => {}),
    [id]
  );
  useEffect(() => {
     
    refresh();
  }, [refresh]);
  useEffect(() => {
    if (!browse) return;
    const q = nation ? `?nation=${nation}` : "";
     
    gw<Programme[]>(`/projects/funding-programmes${q}`).then(setProgrammes).catch(() => {});
  }, [browse, nation]);

  async function addFromCatalogue(p: Programme) {
    await gw(`/projects/${id}/funding`, {
      method: "POST",
      body: JSON.stringify({ programme_key: p.key, name: p.name, funder: p.funder, kind: p.kind === "capital" || p.kind === "revenue" || p.kind === "advice" ? "grant" : p.kind === "equity_match" ? "equity_match" : "loan" }),
    });
    refresh();
  }

  async function patch(f: Funding, body: object) {
    await gw(`/projects/${id}/funding/${f.id}`, { method: "PATCH", body: JSON.stringify(body) });
    refresh();
  }

  return (
    <div className="flex gap-4">
      <div className="min-w-0 flex-1">
        <div className="mb-3 flex justify-between">
          <p className="text-sm text-ink-muted">The funding stack for this project.</p>
          <button onClick={() => setBrowse(!browse)} className={btn}>
            {browse ? "Close programmes" : "Browse programmes"}
          </button>
        </div>
        <table className="w-full rounded-md border border-line bg-surface text-sm">
          <thead>
            <tr className="data border-b border-line text-left text-ink-muted uppercase">
              <th className="px-3 py-2">Source</th>
              <th className="px-3 py-2">Kind</th>
              <th className="px-3 py-2">Sought</th>
              <th className="px-3 py-2">Secured</th>
              <th className="px-3 py-2">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {stack.map((f) => (
              <>
                <tr key={f.id} onClick={() => setExpanded(expanded === f.id ? null : f.id)} className="cursor-pointer hover:bg-accent-soft">
                  <td className="px-3 py-2 font-medium">
                    {f.name}
                    {f.funder && <span className="block text-xs font-normal text-ink-faint">{f.funder}</span>}
                  </td>
                  <td className="data px-3 py-2">{f.kind}</td>
                  <td className="px-3 py-2">
                    <input
                      type="number"
                      defaultValue={f.amount_sought ?? ""}
                      onClick={(e) => e.stopPropagation()}
                      onBlur={(e) => patch(f, { amount_sought: e.target.value ? Number(e.target.value) : null })}
                      className={`w-28 ${input}`}
                    />
                  </td>
                  <td className="px-3 py-2">
                    <input
                      type="number"
                      defaultValue={f.amount_secured ?? ""}
                      onClick={(e) => e.stopPropagation()}
                      onBlur={(e) => patch(f, { amount_secured: e.target.value ? Number(e.target.value) : null })}
                      className={`w-28 ${input}`}
                    />
                  </td>
                  <td className="px-3 py-2">
                    <select value={f.status} onClick={(e) => e.stopPropagation()} onChange={(e) => patch(f, { status: e.target.value })} className={input}>
                      {["identified", "applying", "offered", "secured", "drawing", "complete", "declined"].map((s) => (
                        <option key={s} value={s}>
                          {s}
                        </option>
                      ))}
                    </select>
                  </td>
                </tr>
                {expanded === f.id && (
                  <tr>
                    <td colSpan={5} className="bg-paper px-3 py-2">
                      <p className="data mb-1 text-ink-muted uppercase">Drawdown schedule</p>
                      {f.drawdown_schedule.length === 0 ? (
                        <p className="text-xs text-ink-faint">No drawdowns planned yet.</p>
                      ) : (
                        <ul className="space-y-0.5 text-xs">
                          {f.drawdown_schedule.map((dd, i) => (
                            <li key={i} className="flex justify-between">
                              <span>{dd.label}</span>
                              <span className="data">
                                {fmtDate(dd.due_date)} · {fmtMoney(dd.amount ?? null)} · {dd.status}
                              </span>
                            </li>
                          ))}
                        </ul>
                      )}
                    </td>
                  </tr>
                )}
              </>
            ))}
          </tbody>
        </table>
      </div>

      {browse && (
        <aside className="w-96 shrink-0 rounded-md border border-line bg-surface p-3">
          <select value={nation} onChange={(e) => setNation(e.target.value)} className={`mb-2 w-full ${input}`}>
            <option value="">All nations</option>
            <option value="england">England</option>
            <option value="scotland">Scotland</option>
            <option value="wales">Wales</option>
          </select>
          <ul className="max-h-130 space-y-2 overflow-y-auto">
            {programmes.map((p) => (
              <li key={p.key} className="rounded-sm border border-line p-2 text-sm">
                <p className="font-medium">
                  {p.name}
                  {p.stale && (
                    <span className="stamp ml-1 text-warn bg-warn-soft" title={`Facts last verified ${fmtDate(p.last_verified)} — due a review`}>
                      verify
                    </span>
                  )}
                </p>
                <p className="data mt-0.5 text-ink-muted">
                  {p.funder} · {p.kind} · {p.status}
                </p>
                {p.amount_note && <p className="mt-0.5 text-xs text-ink-muted">{p.amount_note}</p>}
                <p className="mt-0.5 text-xs text-ink-faint">{p.eligibility}</p>
                <button onClick={() => addFromCatalogue(p)} className={`mt-1.5 ${btnGhost}`}>
                  Add to project
                </button>
              </li>
            ))}
          </ul>
        </aside>
      )}
    </div>
  );
}

// ------------------------------------------------------------------ Budget

const CATEGORIES = ["land", "construction", "externals", "abnormals", "fees", "statutory", "contingency", "finance", "other"];

function BudgetTab({ id }: { id: string }) {
  const [lines, setLines] = useState<BudgetLine[]>([]);
  const [dirty, setDirty] = useState(false);

  useEffect(() => {
     
    gw<{ lines: BudgetLine[] }>(`/projects/${id}/budget`)
      .then((b) => setLines(b.lines))
      .catch(() => {});
  }, [id]);

  const update = (i: number, patch: Partial<BudgetLine>) => {
    setLines((ls) => ls.map((l, j) => (j === i ? { ...l, ...patch } : l)));
    setDirty(true);
  };

  async function save() {
    await gw(`/projects/${id}/budget`, { method: "PUT", body: JSON.stringify(lines) });
    setDirty(false);
  }

  const total = (k: "budget" | "forecast" | "actual") => lines.reduce((s, l) => s + (Number(l[k]) || 0), 0);
  const variance = total("forecast") - total("budget");

  return (
    <div>
      <table className="w-full rounded-md border border-line bg-surface text-sm">
        <thead>
          <tr className="data border-b border-line text-left text-ink-muted uppercase">
            <th className="px-3 py-2">Category</th>
            <th className="px-3 py-2">Line</th>
            <th className="px-3 py-2">Budget</th>
            <th className="px-3 py-2">Forecast</th>
            <th className="px-3 py-2">Actual</th>
            <th className="px-3 py-2" />
          </tr>
        </thead>
        <tbody className="divide-y divide-line">
          {lines.map((l, i) => (
            <tr key={i}>
              <td className="px-3 py-1.5">
                <select value={l.category} onChange={(e) => update(i, { category: e.target.value })} className={input}>
                  {CATEGORIES.map((c) => (
                    <option key={c} value={c}>
                      {c}
                    </option>
                  ))}
                </select>
              </td>
              <td className="px-3 py-1.5">
                <input value={l.label} onChange={(e) => update(i, { label: e.target.value })} className={`w-full ${input}`} />
              </td>
              {(["budget", "forecast", "actual"] as const).map((k) => (
                <td key={k} className="px-3 py-1.5">
                  <input type="number" value={l[k]} onChange={(e) => update(i, { [k]: Number(e.target.value) })} className={`w-28 ${input}`} />
                </td>
              ))}
              <td className="px-3 py-1.5">
                <button onClick={() => { setLines((ls) => ls.filter((_, j) => j !== i)); setDirty(true); }} className={btnGhost}>
                  Remove
                </button>
              </td>
            </tr>
          ))}
        </tbody>
        <tfoot>
          <tr className="border-t border-line font-medium">
            <td className="px-3 py-2" colSpan={2}>
              Totals
            </td>
            <td className="px-3 py-2">{fmtMoney(total("budget"))}</td>
            <td className={`px-3 py-2 ${variance > 0 ? "text-danger" : ""}`}>{fmtMoney(total("forecast"))}</td>
            <td className="px-3 py-2">{fmtMoney(total("actual"))}</td>
            <td className={`data px-3 py-2 ${variance > 0 ? "text-danger" : "text-accent"}`}>
              {variance > 0 ? "+" : ""}
              {fmtMoney(variance)} var.
            </td>
          </tr>
        </tfoot>
      </table>
      <div className="mt-3 flex gap-2">
        <button onClick={() => { setLines((ls) => [...ls, { category: "other", label: "", budget: 0, forecast: 0, actual: 0 }]); setDirty(true); }} className={btnGhost}>
          + Add line
        </button>
        {dirty && (
          <button onClick={save} className={btn}>
            Save budget
          </button>
        )}
      </div>
    </div>
  );
}

// ------------------------------------------------------------------- Risks

function RisksTab({ id }: { id: string }) {
  const [risks, setRisks] = useState<Risk[]>([]);
  const [desc, setDesc] = useState("");
  const [likelihood, setLikelihood] = useState(3);
  const [impact, setImpact] = useState(3);

  const refresh = useCallback(
    () => gw<Risk[]>(`/projects/${id}/risks`).then(setRisks).catch(() => {}),
    [id]
  );
  useEffect(() => {
     
    refresh();
  }, [refresh]);

  async function add(e: React.FormEvent) {
    e.preventDefault();
    await gw(`/projects/${id}/risks`, {
      method: "POST",
      body: JSON.stringify({ category: "manual", description: desc, likelihood, impact }),
    });
    setDesc("");
    refresh();
  }

  async function patch(r: Risk, body: object) {
    await gw(`/projects/${id}/risks/${r.id}`, { method: "PATCH", body: JSON.stringify(body) });
    refresh();
  }

  return (
    <div>
      <table className="w-full rounded-md border border-line bg-surface text-sm">
        <thead>
          <tr className="data border-b border-line text-left text-ink-muted uppercase">
            <th className="px-3 py-2">Risk</th>
            <th className="px-3 py-2">L</th>
            <th className="px-3 py-2">I</th>
            <th className="px-3 py-2">Score</th>
            <th className="px-3 py-2">Mitigation</th>
            <th className="px-3 py-2">Status</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-line">
          {risks.map((r) => (
            <tr key={r.id} className={r.status === "closed" ? "opacity-50" : ""}>
              <td className="max-w-60 px-3 py-2">{r.description}</td>
              {(["likelihood", "impact"] as const).map((k) => (
                <td key={k} className="px-3 py-2">
                  <select value={r[k]} onChange={(e) => patch(r, { [k]: Number(e.target.value) })} className={input}>
                    {[1, 2, 3, 4, 5].map((n) => (
                      <option key={n} value={n}>
                        {n}
                      </option>
                    ))}
                  </select>
                </td>
              ))}
              <td className={`data px-3 py-2 ${r.likelihood * r.impact >= 16 ? "text-danger" : r.likelihood * r.impact >= 9 ? "text-warn" : ""}`}>
                {r.likelihood * r.impact}
              </td>
              <td className="max-w-60 px-3 py-2 text-xs text-ink-muted">{r.mitigation}</td>
              <td className="px-3 py-2">
                <select value={r.status} onChange={(e) => patch(r, { status: e.target.value })} className={input}>
                  <option value="open">open</option>
                  <option value="monitoring">monitoring</option>
                  <option value="closed">closed</option>
                </select>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <form onSubmit={add} className="mt-3 flex flex-wrap items-center gap-2">
        <input required value={desc} onChange={(e) => setDesc(e.target.value)} placeholder="Describe a new risk…" className={`min-w-0 flex-1 ${input}`} />
        <label className="text-sm text-ink-muted">
          L{" "}
          <select value={likelihood} onChange={(e) => setLikelihood(Number(e.target.value))} className={input}>
            {[1, 2, 3, 4, 5].map((n) => (
              <option key={n}>{n}</option>
            ))}
          </select>
        </label>
        <label className="text-sm text-ink-muted">
          I{" "}
          <select value={impact} onChange={(e) => setImpact(Number(e.target.value))} className={input}>
            {[1, 2, 3, 4, 5].map((n) => (
              <option key={n}>{n}</option>
            ))}
          </select>
        </label>
        <button type="submit" className={btn}>
          Add risk
        </button>
      </form>
    </div>
  );
}

// -------------------------------------------------------------- Conditions

function ConditionsTab({ id }: { id: string }) {
  const [conditions, setConditions] = useState<Condition[]>([]);
  const [form, setForm] = useState({ application_ref: "", number: "", description: "", pre: false });

  const refresh = useCallback(
    () => gw<Condition[]>(`/projects/${id}/conditions`).then(setConditions).catch(() => {}),
    [id]
  );
  useEffect(() => {
     
    refresh();
  }, [refresh]);

  async function add(e: React.FormEvent) {
    e.preventDefault();
    await gw(`/projects/${id}/conditions`, {
      method: "POST",
      body: JSON.stringify({
        application_ref: form.application_ref || null,
        number: form.number,
        description: form.description,
        pre_commencement: form.pre,
      }),
    });
    setForm({ application_ref: "", number: "", description: "", pre: false });
    refresh();
  }

  async function setStatus(c: Condition, status: string) {
    await gw(`/projects/${id}/conditions/${c.id}`, {
      method: "PATCH",
      body: JSON.stringify({ status }),
    });
    refresh();
  }

  return (
    <div>
      <table className="w-full rounded-md border border-line bg-surface text-sm">
        <thead>
          <tr className="data border-b border-line text-left text-ink-muted uppercase">
            <th className="px-3 py-2">No.</th>
            <th className="px-3 py-2">Condition</th>
            <th className="px-3 py-2">Application</th>
            <th className="px-3 py-2">Status</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-line">
          {conditions.map((c) => (
            <tr key={c.id}>
              <td className="data px-3 py-2">
                {c.number}
                {c.pre_commencement && (
                  <span className="stamp ml-1.5 text-warn bg-warn-soft" title="Must be discharged before works start">
                    pre-comm.
                  </span>
                )}
              </td>
              <td className="px-3 py-2">{c.description}</td>
              <td className="data px-3 py-2 text-ink-muted">{c.application_ref ?? "—"}</td>
              <td className="px-3 py-2">
                <select value={c.status} onChange={(e) => setStatus(c, e.target.value)} className={input}>
                  {["outstanding", "submitted", "discharged", "partially_discharged", "na"].map((s) => (
                    <option key={s} value={s}>
                      {s.replaceAll("_", " ")}
                    </option>
                  ))}
                </select>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <form onSubmit={add} className="mt-3 flex flex-wrap items-center gap-2">
        <input value={form.application_ref} onChange={(e) => setForm({ ...form, application_ref: e.target.value })} placeholder="LPA ref" className={`w-32 ${input}`} />
        <input required value={form.number} onChange={(e) => setForm({ ...form, number: e.target.value })} placeholder="No." className={`w-16 ${input}`} />
        <input required value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} placeholder="Condition wording…" className={`min-w-0 flex-1 ${input}`} />
        <label className="flex items-center gap-1 text-sm text-ink-muted">
          <input type="checkbox" checked={form.pre} onChange={(e) => setForm({ ...form, pre: e.target.checked })} className="accent-(--accent)" />
          Pre-commencement
        </label>
        <button type="submit" className={btn}>
          Add
        </button>
      </form>
    </div>
  );
}

// ------------------------------------------------------------ Stakeholders

function StakeholdersTab({ id }: { id: string }) {
  const [people, setPeople] = useState<Stakeholder[]>([]);
  const [form, setForm] = useState({ name: "", org: "", role: "community", email: "" });

  const refresh = useCallback(
    () => gw<Stakeholder[]>(`/projects/${id}/stakeholders`).then(setPeople).catch(() => {}),
    [id]
  );
  useEffect(() => {
     
    refresh();
  }, [refresh]);

  async function add(e: React.FormEvent) {
    e.preventDefault();
    await gw(`/projects/${id}/stakeholders`, {
      method: "POST",
      body: JSON.stringify({
        name: form.name,
        org: form.org || null,
        role: form.role,
        email: form.email || null,
      }),
    });
    setForm({ name: "", org: "", role: "community", email: "" });
    refresh();
  }

  return (
    <div>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {people.map((p) => (
          <div key={p.id} className="rounded-md border border-line bg-surface p-3 text-sm">
            <p className="font-medium">{p.name}</p>
            <p className="data mt-0.5 text-ink-muted uppercase">
              {p.role}
              {p.org ? ` · ${p.org}` : ""}
            </p>
            {p.email && <p className="mt-1 text-xs text-ink-muted">{p.email}</p>}
            {p.last_contact && (
              <p className="data mt-1 text-ink-faint">Last contact {fmtDate(p.last_contact)}</p>
            )}
          </div>
        ))}
      </div>
      <form onSubmit={add} className="mt-3 flex flex-wrap items-center gap-2">
        <input required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="Name" className={input} />
        <input value={form.org} onChange={(e) => setForm({ ...form, org: e.target.value })} placeholder="Organisation" className={input} />
        <select value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })} className={input}>
          {["lpa", "landowner", "funder", "contractor", "consultant", "community", "other"].map((r) => (
            <option key={r} value={r}>
              {r}
            </option>
          ))}
        </select>
        <input type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} placeholder="Email" className={input} />
        <button type="submit" className={btn}>
          Add
        </button>
      </form>
    </div>
  );
}
