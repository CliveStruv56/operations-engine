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
import { ContactsTab } from "./tabs/ContactsTab";
import { input } from "./tabs/ui";
import { useAsk } from "@/components/ui";
import { useWorkspace } from "../../workspace";
import { ModuleDisabled, PROJECTS_DISABLED, useModuleEnabled } from "../../module-gate";
import { ApiError } from "@/lib/api";

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
  "Contacts", // shown only when the CRM feature flag is on
] as const;

export default function ProjectRoom({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const ws = useWorkspace();
  const ask = useAsk();
  const [detail, setDetail] = useState<Detail | null>(null);
  const [tab, setTab] = useState<(typeof TABS)[number]>("Overview");
  const [error, setError] = useState<string | null>(null);
  const flagOn = useModuleEnabled("projects");
  // The module gate and a missing project both 404 with `not_found`, so the
  // client cannot tell them apart. The flag check below already covers the
  // module case authoritatively, which leaves a stale or mistyped link as by
  // far the likelier cause here — say that rather than blaming the module.
  const [missing, setMissing] = useState(false);
  const tabs = TABS.filter(
    (t) => t !== "Contacts" || ws.tenant?.features?.contacts === true
  );

  const refresh = useCallback(
    () =>
      gw<Detail>(`/projects/${id}/groundwork`)
        .then(setDetail)
        .catch((e) => {
          if (e instanceof ApiError && e.status === 404) setMissing(true);
          else setError(e instanceof Error ? e.message : String(e));
        }),
    [id]
  );
  useEffect(() => {
    if (flagOn !== true) return;
    refresh();
  }, [refresh, flagOn]);

  async function changeStatus(status: string) {
    let dormancy_reason: string | null = null;
    if (status === "dormant") {
      // The old prompt offered "funding_gap, group_capacity" as examples, which
      // are internal enum names the API never required — it takes any string up
      // to 200 characters.
      dormancy_reason = await ask.text({
        title: "Make this project dormant",
        body: "It stays in the portfolio and keeps everything recorded against it; it just stops appearing as live work. You can make it active again at any point.",
        label: "Why is it going dormant?",
        hint: "A short note for whoever picks this up later — a funding gap, no capacity in the group, waiting on a landowner.",
        placeholder: "Waiting on the funding decision in the autumn",
        confirmLabel: "Make dormant",
        maxLength: 200,
      });
      if (!dormancy_reason) return;
    }
    await gw(`/projects/${id}/status`, {
      method: "POST",
      body: JSON.stringify({ status, dormancy_reason }),
    });
    refresh();
  }

  if (flagOn === false) return <ModuleDisabled {...PROJECTS_DISABLED} />;
  if (missing)
    return (
      <main className="min-h-0 flex-1 overflow-y-auto p-8">
        <div className="mx-auto max-w-xl rounded-card border border-edge bg-surface p-6">
          <h1 className="font-display text-[20px] font-medium tracking-[-0.01em]">
            This project isn&rsquo;t here
          </h1>
          <p className="mt-2 text-sm text-ink-muted">
            It may have been deleted, or the link may be wrong.
          </p>
          <Link
            href="/app/projects"
            className="mt-4 inline-block text-sm text-ink-muted underline hover:text-ink"
          >
            Back to development projects
          </Link>
        </div>
      </main>
    );
  if (error)
    return (
      <main className="p-8">
        <p className="rounded-[10px] bg-danger-soft px-3 py-2 text-sm text-danger">{error}</p>
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
          <h1 className="font-display text-[26px] font-medium tracking-[-0.01em]">{detail.name}</h1>
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
        <p className="mb-3 rounded-[10px] bg-warn-soft px-3 py-2 text-sm text-warn">
          Dormant — {detail.dormancy_reason}. Set the project back to Active to resume.
        </p>
      )}
      {hrb && (
        <p className="mb-3 rounded-[10px] bg-warn-soft px-3 py-2 text-sm text-warn">
          Higher-Risk Building — Building Safety Act gateways apply; track them manually for now.
        </p>
      )}

      <nav className="mb-5 flex flex-wrap gap-1 border-b border-line">
        {tabs.map((t) => (
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
      {tab === "Contacts" && <ContactsTab id={id} />}
      </div>
    </main>
  );
}
