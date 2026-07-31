"use client";

import { useEffect, useRef, useState } from "react";
import {
  ActivityEntry,
  Detail,
  Funding,
  Risk,
  Task,
  fmtDate,
  fmtMoney,
  getDraftJob,
  gw,
  openPresigned,
  submitHealthCard,
} from "@/lib/groundwork";
import { RagDots } from "../../page";
import { DraftModal } from "./DraftModal";
import { btn } from "./ui";

export function OverviewTab({ id }: { id: string }) {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [funding, setFunding] = useState<Funding[]>([]);
  const [risks, setRisks] = useState<Risk[]>([]);
  const [activity, setActivity] = useState<ActivityEntry[]>([]);
  const [portfolio, setPortfolio] = useState<Detail["rag"] | null>(null);
  const [draftOpen, setDraftOpen] = useState(false);
  const [cardState, setCardState] = useState<"idle" | "working" | "failed">("idle");
  const cardTimer = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(
    () => () => {
      if (cardTimer.current) clearInterval(cardTimer.current);
    },
    []
  );

  async function healthCard() {
    setCardState("working");
    try {
      const job = await submitHealthCard(id);
      cardTimer.current = setInterval(async () => {
        const next = await getDraftJob(job.id).catch(() => null);
        if (!next || next.status === "queued" || next.status === "running") return;
        if (cardTimer.current) clearInterval(cardTimer.current);
        if (next.status === "succeeded" && next.download_url) {
          setCardState("idle");
          openPresigned(next.download_url);
        } else {
          setCardState("failed");
        }
      }, 2000);
    } catch {
      setCardState("failed");
    }
  }

  useEffect(() => {

    gw<Task[]>(`/projects/${id}/tasks?status=todo`).then(setTasks).catch(() => {});
    gw<Funding[]>(`/projects/${id}/funding`).then(setFunding).catch(() => {});
    gw<Risk[]>(`/projects/${id}/risks`).then(setRisks).catch(() => {});
    gw<ActivityEntry[]>(`/projects/${id}/activity`)
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
        <div className="mt-4 flex items-center gap-2">
          <button onClick={() => setDraftOpen(true)} className={btn}>
            Draft monthly report
          </button>
          <button onClick={healthCard} disabled={cardState === "working"} className={btn}>
            {cardState === "working" ? "Generating…" : "Health card (PDF)"}
          </button>
          {cardState === "failed" && (
            <span className="text-xs text-danger">Health card failed — try again.</span>
          )}
        </div>
        {draftOpen && (
          <DraftModal
            projectId={id}
            kind="monthly_report"
            onClose={() => setDraftOpen(false)}
            onRegistered={() => {}}
          />
        )}
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
