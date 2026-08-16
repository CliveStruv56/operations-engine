"use client";

import { use, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { ApiError } from "@/lib/api";
import {
  Application,
  ApplicationStatus,
  CatalogueRow,
  STAGES,
  STAGE_LABEL,
  STATUS_LABEL,
  catalogueWarning,
  fmtDate,
  fmtMoney,
  gr,
} from "@/lib/grants";
import { useAsk } from "@/components/ui";
import { GRANTS_DISABLED, ModuleDisabled, useModuleEnabled } from "../../module-gate";
import { card, input } from "../ui";
import { EditApplicationPanel } from "./EditApplicationPanel";
import { BidPackTab } from "./tabs/BidPackTab";
import { ConditionsTab } from "./tabs/ConditionsTab";
import { ImpactTab } from "./tabs/ImpactTab";
import { ReportingTab } from "./tabs/ReportingTab";
import { StagesTab } from "./tabs/StagesTab";
import { TasksTab } from "./tabs/TasksTab";

const TABS = [
  "Stages & gates",
  "Tasks",
  "Bid pack",
  "Conditions",
  "Reporting",
  "Impact",
] as const;

const STATUSES: ApplicationStatus[] = [
  "pipeline",
  "drafting",
  "submitted",
  "awarded",
  "declined",
  "withdrawn",
  "complete",
];

export default function ApplicationRoom({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const ask = useAsk();
  const [detail, setDetail] = useState<Application | null>(null);
  const [catalogue, setCatalogue] = useState<CatalogueRow | null>(null);
  const [tab, setTab] = useState<(typeof TABS)[number]>("Stages & gates");
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);
  const [harvestNote, setHarvestNote] = useState<"queued" | "failed" | null>(null);
  const flagOn = useModuleEnabled("grants");
  // The module gate and a missing application both 404 with `not_found`, so
  // the client cannot tell them apart. The flag check below covers the module
  // case authoritatively, which leaves a stale link as the likelier cause.
  const [missing, setMissing] = useState(false);

  const refresh = useCallback(
    () =>
      gr<Application>(`/grants/applications/${id}`)
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

  useEffect(() => {
    if (!detail?.programme_key) return;
    gr<CatalogueRow[]>("/grants/funder-catalogue")
      .then((rows) => setCatalogue(rows.find((r) => r.key === detail.programme_key) ?? null))
      .catch(() => setCatalogue(null));
  }, [detail?.programme_key]);

  async function changeStatus(status: ApplicationStatus) {
    let amount_awarded: string | null = null;
    if (status === "awarded" && !detail?.amount_awarded) {
      amount_awarded = await ask.text({
        title: "Record the award",
        body: "The offer, not what you asked for — the two often differ, and the portfolio totals follow this figure.",
        label: "Amount offered (£)",
        inputType: "number",
        placeholder: "25000",
        confirmLabel: "Mark as awarded",
      });
      if (!amount_awarded) return;
    }
    try {
      const next = await gr<Application>(`/grants/applications/${id}/status`, {
        method: "POST",
        body: JSON.stringify({ status, amount_awarded }),
      });
      setDetail(next);
      if (status === "submitted") {
        setHarvestNote(next.harvest_queued === false ? "failed" : "queued");
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  if (flagOn === false) return <ModuleDisabled {...GRANTS_DISABLED} />;
  if (missing)
    return (
      <main className="min-h-0 flex-1 overflow-y-auto p-8">
        <div className={`mx-auto max-w-xl ${card} p-6`}>
          <h1 className="font-display text-[20px] font-medium tracking-[-0.01em]">
            This application isn&rsquo;t here
          </h1>
          <p className="mt-2 text-sm text-ink-muted">
            It may have been deleted, or the link may be wrong.
          </p>
          <Link
            href="/app/grants"
            className="mt-4 inline-block text-sm text-ink-muted underline hover:text-ink"
          >
            Back to grant funding
          </Link>
        </div>
      </main>
    );
  if (error)
    return (
      <main className="p-8">
        <p className="rounded-card bg-danger-soft px-3 py-2 text-sm text-danger">{error}</p>
      </main>
    );
  if (!detail) return <main className="data p-8 text-ink-faint">Loading application…</main>;

  const warning = catalogue ? catalogueWarning(catalogue) : null;

  return (
    <main className="min-h-0 flex-1 overflow-y-auto">
      <div className="mx-auto max-w-6xl p-6">
        <p className="data text-ink-faint uppercase">
          <Link href="/app/grants" className="hover:text-ink">
            ← Grant funding
          </Link>
        </p>
        <header className="mt-1 mb-4 flex flex-wrap items-end justify-between gap-3">
          <div>
            <h1 className="font-display text-[26px] font-medium tracking-[-0.01em]">
              {detail.title}
            </h1>
            <p className="mt-0.5 text-sm text-ink-muted">
              {detail.funder_name ?? "No funder chosen yet"}
              {" · "}
              {detail.status === "awarded" || detail.status === "complete"
                ? `${fmtMoney(detail.amount_awarded)} awarded`
                : `${fmtMoney(detail.amount_requested)} requested`}
              {detail.deadline ? ` · deadline ${fmtDate(detail.deadline)}` : ""}
              {!detail.restricted ? " · unrestricted" : ""}
            </p>
            {detail.project_name && (
              <p className="mt-0.5 text-xs text-ink-faint">
                Funds the project &ldquo;{detail.project_name}&rdquo; — its documents are drawn on
                first when drafting.
              </p>
            )}
          </div>
          <div className="flex items-center gap-3">
            <span className="flex items-center gap-1">
              {STAGES.map((s) => (
                <button
                  key={s}
                  onClick={() => setTab("Stages & gates")}
                  className={`stamp ${
                    s === detail.stage_current
                      ? "bg-deep-violet text-on-ink border-deep-violet"
                      : "text-ink-faint"
                  }`}
                >
                  {STAGE_LABEL[s]}
                </button>
              ))}
            </span>
            <select
              value={detail.status}
              onChange={(e) => changeStatus(e.target.value as ApplicationStatus)}
              className={input}
              title="Application status"
            >
              {STATUSES.map((s) => (
                <option key={s} value={s}>
                  {STATUS_LABEL[s]}
                </option>
              ))}
            </select>
            <button
              onClick={() => setEditing((open) => !open)}
              className="text-xs text-ink-muted underline hover:text-ink"
            >
              {editing ? "Close" : "Edit"}
            </button>
          </div>
        </header>

        {editing && (
          <EditApplicationPanel
            detail={detail}
            onCancel={() => setEditing(false)}
            onSaved={(next) => {
              setDetail(next);
              setEditing(false);
            }}
          />
        )}

        {harvestNote === "queued" && (
          <p className="mb-3 rounded-card bg-accent-soft px-3 py-2 text-sm">
            We&apos;ll look through the answers you sent for facts to add to{" "}
            <Link href="/app/claims" className="underline hover:text-ink">
              Your organisation
            </Link>
            . They arrive as proposals, for someone to confirm.
          </p>
        )}
        {harvestNote === "failed" && (
          <p className="mb-3 rounded-card bg-warn-soft px-3 py-2 text-sm text-warn">
            The application is marked submitted, but we could not queue a scan of it for new
            facts. You can add them by hand on{" "}
            <Link href="/app/claims" className="underline hover:text-ink">
              Your organisation
            </Link>
            .
          </p>
        )}

        {warning && (
          <p className="mb-3 rounded-card bg-warn-soft px-3 py-2 text-sm text-warn">
            Funder catalogue entry &ldquo;{catalogue?.name}&rdquo; is {warning}. Any application
            drafted from it carries the same warning on its first page.
          </p>
        )}

        <nav className="mb-5 flex flex-wrap gap-1 border-b border-line">
          {TABS.map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`px-3 py-2 text-sm ${
                tab === t
                  ? "border-b-2 border-deep-violet font-medium text-deep-violet"
                  : "text-ink-muted hover:text-ink"
              }`}
            >
              {t}
            </button>
          ))}
        </nav>

        {tab === "Stages & gates" && <StagesTab id={id} onAdvanced={refresh} />}
        {tab === "Tasks" && <TasksTab id={id} />}
        {tab === "Bid pack" && <BidPackTab id={id} />}
        {tab === "Conditions" && <ConditionsTab id={id} />}
        {tab === "Reporting" && <ReportingTab id={id} />}
        {tab === "Impact" && <ImpactTab id={id} />}
      </div>
    </main>
  );
}
