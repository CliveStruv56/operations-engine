"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  PortfolioRow,
  STAGE_LABEL,
  fmtDate,
  gw,
} from "@/lib/groundwork";
import { DocIcon, PenIcon } from "@/components/icons";
import ActivityCard from "./activity-card";
import ProjectPlanPanel from "./project-plan";
import { RagDots } from "./projects/page";
import type { Project } from "./workspace";

/** Slim view of DocumentOut — everything the hero needs from GET /documents. */
export type DocMeta = {
  id: string;
  title: string;
  project_id: string | null;
  /** Set when the file was dropped into a chat — the composer's chips. */
  conversation_id: string | null;
  is_primary: boolean;
  status: string;
  error: string | null;
  summary: string | null;
};

export type Suggestion = { text: string; mode?: string; icon: "doc" | "pen" };

function greeting(): string {
  const h = new Date().getHours();
  if (h < 12) return "Good morning.";
  if (h < 18) return "Good afternoon.";
  return "Good evening.";
}

const shorten = (t: string, max = 40) => (t.length > max ? `${t.slice(0, max - 1)}…` : t);

/** Context-dependent starter prompts. Only ever suggests questions the vault
 * can actually ground — Groundwork structured data (tasks, stages) is not
 * retrievable by chat, so those facts render in the status card instead. */
function buildSuggestions(project: Project | null, projectDocs: DocMeta[]): Suggestion[] {
  const ready = projectDocs.filter((d) => d.status === "ready");
  const lead = ready.find((d) => d.is_primary) ?? ready[0];

  if (!project) {
    const generic: Suggestion[] = [
      { text: "Summarise our health and safety procedures", icon: "doc" },
      { text: "What are our standard payment terms?", icon: "doc" },
      { text: "Draft a letter quoting for a new client", icon: "pen" },
      { text: "Give me a one-page status report", mode: "report", icon: "pen" },
    ];
    if (lead) generic[0] = { text: `Summarise the key points of ${shorten(lead.title)}`, icon: "doc" };
    return generic;
  }

  const cards: Suggestion[] = [];
  if (lead) {
    cards.push({ text: `Summarise the key points of ${shorten(lead.title)}`, icon: "doc" });
  }
  if (ready.length >= 2) {
    cards.push({ text: "What are the key dates and actions across these documents?", icon: "doc" });
  }
  if (project.is_development) {
    cards.push({ text: "Draft a status update for the client", mode: "report", icon: "pen" });
  }
  cards.push({
    text: `Draft a one-page summary of ${shorten(project.name, 30)}`,
    mode: "report",
    icon: "pen",
  });
  if (cards.length < 4) {
    cards.push({ text: "Turn these documents into a slide deck", mode: "slides", icon: "pen" });
  }
  return cards.slice(0, 4);
}

/** Live Groundwork status for a selected development project. Hidden entirely
 * when the fetch fails (e.g. tenant without the projects feature). */
function DevStatusCard({ projectId }: { projectId: string }) {
  const [row, setRow] = useState<PortfolioRow | null>(null);

  useEffect(() => {
    let stale = false;
    gw<PortfolioRow[]>("/projects/portfolio")
      .then((rows) => {
        if (!stale) setRow(rows.find((r) => r.id === projectId) ?? null);
      })
      .catch((err) => {
        console.error("Portfolio fetch failed", err);
        if (!stale) setRow(null);
      });
    return () => {
      stale = true;
    };
  }, [projectId]);

  if (!row) return null;
  const overdueMilestone =
    row.next_milestone?.due_date && new Date(row.next_milestone.due_date) < new Date();

  return (
    <div className="mt-7 w-full max-w-[620px] rounded-card border border-edge bg-card px-5 py-4 text-left shadow-card">
      <div className="flex flex-wrap items-center gap-3">
        <span className="text-[13.5px] font-bold">{STAGE_LABEL[row.stage_current] ?? row.stage_current}</span>
        <RagDots rag={row.rag} />
        <span className="text-xs font-semibold text-faint">
          {row.overdue_tasks > 0 ? `${row.overdue_tasks} overdue task${row.overdue_tasks === 1 ? "" : "s"}` : "no overdue tasks"}
          {" · "}
          {row.open_risks} open risk{row.open_risks === 1 ? "" : "s"}
        </span>
        <Link
          href={`/app/projects/${projectId}`}
          className="ml-auto text-xs font-bold text-accent-deep hover:underline"
        >
          Open project room ↗
        </Link>
      </div>
      {row.next_milestone && (
        <p className="mt-2 text-[13px] font-semibold text-subtle">
          Next milestone: {row.next_milestone.title}
          <span className={`ml-2 text-xs font-bold ${overdueMilestone ? "text-danger" : "text-faint"}`}>
            {fmtDate(row.next_milestone.due_date)}
            {overdueMilestone && " — overdue"}
          </span>
        </p>
      )}
    </div>
  );
}

export default function EmptyHero({
  activeProject,
  docs,
  devProjectsEnabled,
  onPick,
}: {
  activeProject: Project | null;
  docs: DocMeta[] | null;
  devProjectsEnabled: boolean;
  onPick: (s: Suggestion) => void;
}) {
  const projectDocs = docs?.filter((d) => !activeProject || d.project_id === activeProject.id) ?? [];
  const readyCount = projectDocs.filter((d) => d.status === "ready").length;
  const suggestions = buildSuggestions(activeProject, projectDocs);
  const emptyProject = activeProject !== null && docs !== null && readyCount === 0;

  return (
    <div className="flex flex-1 flex-col items-center justify-center py-8 text-center">
      {emptyProject ? (
        <span className="inline-flex items-center gap-2 rounded-full bg-sidebar px-[15px] py-[7px] text-xs font-bold text-subtle">
          No documents in this project yet
        </span>
      ) : (
        <span className="inline-flex items-center gap-2 rounded-full bg-grounded-tint px-[15px] py-[7px] text-xs font-bold text-grounded">
          <i className="h-[7px] w-[7px] rounded-full bg-grounded" />
          {docs === null
            ? "Vault connected"
            : activeProject
              ? `${shorten(activeProject.name, 30)} — ${readyCount} document${readyCount === 1 ? "" : "s"} indexed`
              : `Vault connected — ${readyCount} document${readyCount === 1 ? "" : "s"} indexed`}
        </span>
      )}

      <h2 className="mt-5 font-display text-[34px] leading-tight font-medium tracking-[-0.01em] sm:text-[42px]">
        {greeting()}
      </h2>
      <p className="mt-2.5 max-w-[52ch] text-[15px] leading-relaxed text-subtle">
        {activeProject
          ? `Ask about ${activeProject.name} — answers will prefer this project's documents, with the rest of your vault behind them.`
          : "Ask anything about your business — policies, prices, procedures — or draft something new. Answers come with their sources attached."}
      </p>

      {activeProject?.is_development && devProjectsEnabled && (
        <DevStatusCard projectId={activeProject.id} />
      )}
      {activeProject && !activeProject.is_development && (
        <div className="mt-7 w-full max-w-[620px]">
          <ProjectPlanPanel projectId={activeProject.id} hasPlan={activeProject.has_plan} />
        </div>
      )}

      {emptyProject ? (
        <Link
          href={`/app?view=vault&project=${activeProject!.id}`}
          className="mt-7 flex w-full max-w-[420px] items-center justify-center gap-3 rounded-[14px] border border-edge bg-card px-4 py-3.5 text-[13.5px] font-semibold text-accent-deep shadow-card hover:border-edge-strong"
        >
          <span className="grid h-8 w-8 flex-none place-items-center rounded-[9px] bg-accent-tint text-accent-deep">
            <DocIcon className="h-[15px] w-[15px]" />
          </span>
          Add documents to {shorten(activeProject!.name, 30)} →
        </Link>
      ) : (
        <div className="mt-7 grid w-full max-w-[620px] grid-cols-1 gap-3 sm:grid-cols-2">
          {suggestions.map((s) => (
            <button
              key={s.text}
              onClick={() => onPick(s)}
              className="relative flex items-center gap-3 rounded-[14px] border border-edge bg-card px-4 py-3.5 text-left text-[13.5px] font-semibold text-ink shadow-card hover:border-edge-strong"
            >
              <span className="grid h-8 w-8 flex-none place-items-center rounded-[9px] bg-accent-tint text-accent-deep">
                {s.icon === "pen" ? (
                  <PenIcon className="h-[15px] w-[15px]" />
                ) : (
                  <DocIcon className="h-[15px] w-[15px]" />
                )}
              </span>
              {s.text}
              {s.mode && (
                <span className="absolute -top-[9px] right-3 rounded-full border border-edge-strong bg-accent-tint px-2 py-[3px] text-[10px] font-extrabold text-accent-deep">
                  → {s.mode === "report" ? "Report" : s.mode === "slides" ? "Slide deck" : s.mode}
                </span>
              )}
            </button>
          ))}
        </div>
      )}

      <ActivityCard />

      <p className="mt-4 text-xs font-semibold text-faint">
        Answers cite your documents — verify anything critical.
      </p>
    </div>
  );
}
