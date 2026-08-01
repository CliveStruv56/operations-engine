"use client";

import { use, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { Detail, STAGE_LABEL, STAGES, gw } from "@/lib/groundwork";
import { OverviewTab } from "./tabs/OverviewTab";
import { StagesTab } from "./tabs/StagesTab";
import { TasksTab } from "./tabs/TasksTab";
import { DocumentsTab } from "./tabs/DocumentsTab";
import { FundingTab } from "./tabs/FundingTab";
import { BudgetTab } from "./tabs/BudgetTab";
import { RisksTab } from "./tabs/RisksTab";
import { ConditionsTab } from "./tabs/ConditionsTab";
import { StakeholdersTab } from "./tabs/StakeholdersTab";
import { input } from "./tabs/ui";

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
    <main className="min-h-0 flex-1 overflow-y-auto">
      <div className="mx-auto max-w-6xl p-6">
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
      </div>
    </main>
  );
}
