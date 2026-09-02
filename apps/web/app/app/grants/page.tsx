"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ApiError } from "@/lib/api";
import { Stamp } from "@/components/ui";
import {
  CalendarRow,
  PortfolioRow,
  RAG_DOT,
  STATUS_LABEL,
  STATUS_TONE,
  fmtDate,
  fmtMoney,
  gr,
} from "@/lib/grants";
import { tenantId } from "@/lib/groundwork";
import { GRANTS_DISABLED, ModuleDisabled, useModuleEnabled } from "../module-gate";
import { card, th } from "./ui";
import { PRODUCT_LANGUAGE } from "@/lib/product-language";

const LIVE: string[] = ["pipeline", "drafting", "submitted"];

function Money({ rows }: { rows: PortfolioRow[] }) {
  const pipeline = rows
    .filter((r) => LIVE.includes(r.status))
    .reduce((sum, r) => sum + r.weighted_value, 0);
  const secured = rows
    .filter((r) => r.status === "awarded" || r.status === "complete")
    .reduce((sum, r) => sum + (Number(r.amount_awarded ?? 0) || 0), 0);
  const overdue = rows.reduce((sum, r) => sum + r.overdue_returns, 0);

  return (
    <div className="mb-5 grid gap-3 sm:grid-cols-3">
      <div className={`${card} p-4`}>
        <p className="data text-ink-muted uppercase">Pipeline, weighted</p>
        <p className="mt-1 font-display text-[22px]">{fmtMoney(pipeline)}</p>
        <p className="mt-0.5 text-xs text-ink-faint">
          Live bids discounted by the stage each has reached — a planning figure, not a forecast.
        </p>
      </div>
      <div className={`${card} p-4`}>
        <p className="data text-ink-muted uppercase">Secured</p>
        <p className="mt-1 font-display text-[22px]">{fmtMoney(secured)}</p>
        <p className="mt-0.5 text-xs text-ink-faint">Awarded and in delivery.</p>
      </div>
      <div className={`${card} p-4`}>
        <p className="data text-ink-muted uppercase">Returns overdue</p>
        <p className={`mt-1 font-display text-[22px] ${overdue ? "text-danger" : ""}`}>{overdue}</p>
        <p className="mt-0.5 text-xs text-ink-faint">
          {overdue ? "Past the funder's date." : "Nothing past its date."}
        </p>
      </div>
    </div>
  );
}

function Calendar({ rows }: { rows: CalendarRow[] }) {
  if (rows.length === 0)
    return (
      <p className="px-4 py-6 text-center text-sm text-ink-muted">
        No monitoring returns are outstanding.
      </p>
    );
  return (
    <table className="w-full text-sm">
      <thead>
        <tr className="border-b border-line">
          <th className={th}>Due</th>
          <th className={th}>Return</th>
          <th className={th}>Application</th>
          <th className={th}>Funder</th>
          <th className={th}>Status</th>
        </tr>
      </thead>
      <tbody className="divide-y divide-line">
        {rows.map((r) => (
          <tr key={r.id}>
            <td className="data px-4 py-3">
              <span className="flex items-center gap-2">
                <span className={`h-2.5 w-2.5 rounded-full ${RAG_DOT[r.rag]}`} />
                <span className={r.overdue ? "text-danger" : ""}>{fmtDate(r.due_date)}</span>
              </span>
            </td>
            <td className="px-4 py-3">
              <Link href={`/app/grants/${r.application_id}`} className="hover:underline">
                {r.label}
              </Link>
            </td>
            <td className="px-4 py-3 text-ink-muted">{r.application_title}</td>
            <td className="px-4 py-3 text-ink-muted">{r.funder_name ?? "—"}</td>
            <td className="data px-4 py-3 text-ink-faint">{r.status}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export default function GrantsPage() {
  const router = useRouter();
  const [rows, setRows] = useState<PortfolioRow[] | null>(null);
  const [calendar, setCalendar] = useState<CalendarRow[] | null>(null);
  const [view, setView] = useState<"applications" | "calendar">("applications");
  const [error, setError] = useState<string | null>(null);
  const flagOn = useModuleEnabled("grants");
  // The flag is checked server-side too; a 404 here means it was switched off
  // after this session loaded its workspace.
  const [gone, setGone] = useState(false);

  useEffect(() => {
    if (!tenantId()) {
      router.push("/app");
      return;
    }
    if (flagOn !== true) return;
    Promise.all([
      gr<PortfolioRow[]>("/grants/applications"),
      gr<CalendarRow[]>("/grants/reporting-calendar"),
    ])
      .then(([applications, obligations]) => {
        setRows(applications);
        setCalendar(obligations);
      })
      .catch((e) => {
        if (e instanceof ApiError && e.status === 404) setGone(true);
        else setError(e instanceof Error ? e.message : String(e));
      });
  }, [router, flagOn]);

  if (flagOn === false || gone) return <ModuleDisabled {...GRANTS_DISABLED} />;

  const overdue = calendar?.filter((r) => r.overdue).length ?? 0;

  return (
    <main className="min-h-0 flex-1 overflow-y-auto">
      <div className="mx-auto max-w-6xl p-6">
        <header className="mb-6 flex items-baseline justify-between">
          <h1 className="mt-1 font-display text-[26px] font-medium tracking-[-0.01em]">
            {PRODUCT_LANGUAGE.grantwork.combined}
          </h1>
          <Link
            href="/app/grants/new"
            className="rounded-btn bg-accent px-4 py-2 text-sm font-medium text-accent-ink hover:bg-accent-deep"
          >
            New application
          </Link>
        </header>

        {error && (
          <p className="rounded-card bg-danger-soft px-3 py-2 text-sm text-danger">{error}</p>
        )}

        {rows && rows.length > 0 && <Money rows={rows} />}

        <nav className="mb-4 flex gap-1 border-b border-line">
          {(["applications", "calendar"] as const).map((v) => (
            <button
              key={v}
              onClick={() => setView(v)}
              className={`px-3 py-2 text-sm capitalize ${
                view === v
                  ? "border-b-2 border-deep-violet font-medium text-deep-violet"
                  : "text-ink-muted hover:text-ink"
              }`}
            >
              {v === "calendar" ? "Reporting calendar" : "Applications"}
              {v === "calendar" && overdue > 0 && (
                <span className="stamp ml-2 bg-danger-soft text-danger">{overdue} overdue</span>
              )}
            </button>
          ))}
        </nav>

        {rows && rows.length === 0 && view === "applications" && (
          <div className={`${card} p-10 text-center`}>
            <p className="text-sm font-medium">
              Track every bid from case for support to final evaluation.
            </p>
            <p className="mt-1 text-sm text-ink-muted">
              A new application starts with the full stage plan, task list and document checklist
              already in place — and once its outcomes are recorded, the funder&rsquo;s monitoring
              return assembles itself.
            </p>
          </div>
        )}

        {view === "applications" && rows && rows.length > 0 && (
          <div className={`overflow-x-auto ${card}`}>
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-line">
                  <th className={th}>Application</th>
                  <th className={th}>Funder</th>
                  <th className={th}>Status</th>
                  <th className={th}>Requested</th>
                  <th className={th}>Awarded</th>
                  <th className={th}>Next return</th>
                  <th className={th}>Conditions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {rows.map((r) => (
                  <tr
                    key={r.id}
                    onClick={() => router.push(`/app/grants/${r.id}`)}
                    className={`cursor-pointer hover:bg-accent-soft ${
                      ["declined", "withdrawn"].includes(r.status) ? "opacity-60" : ""
                    }`}
                  >
                    <td className="px-4 py-3 font-medium">
                      {r.title}
                      {!r.restricted && (
                        <span className="stamp ml-2 text-ink-muted">unrestricted</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-ink-muted">{r.funder_name ?? "—"}</td>
                    <td className="px-4 py-3">
                      <Stamp tone={STATUS_TONE[r.status]}>{STATUS_LABEL[r.status]}</Stamp>
                    </td>
                    <td className="data px-4 py-3">{fmtMoney(r.amount_requested)}</td>
                    <td className="data px-4 py-3">{fmtMoney(r.amount_awarded)}</td>
                    <td
                      className={`data px-4 py-3 ${
                        r.overdue_returns > 0 ? "text-danger" : "text-ink-muted"
                      }`}
                    >
                      {fmtDate(r.next_return_due)}
                      {r.overdue_returns > 0 && ` · ${r.overdue_returns} overdue`}
                    </td>
                    <td className="data px-4 py-3">
                      {r.open_conditions > 0 ? (
                        <span className="text-warn">{r.open_conditions} open</span>
                      ) : (
                        "0"
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {view === "calendar" && calendar && (
          <div className={`overflow-x-auto ${card}`}>
            <Calendar rows={calendar} />
          </div>
        )}
      </div>
    </main>
  );
}
