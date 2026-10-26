"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { Stamp } from "@/components/ui";
import {
  PortfolioRow,
  STATUS_LABEL,
  STATUS_TONE,
  fmtDate,
  fmtMoney,
  gr,
} from "@/lib/grants";
import { btn } from "./ui";

/** The grant applications linked to this project — the Grant funding add-on
 *  (docs/project-types-brief.md §3), shown on every kind of project while the
 *  grants module is on. Applications stay records of their own; this is a
 *  view of the ones whose `project_id` points here. */
export function GrantApplicationsTab({ id }: { id: string }) {
  const [rows, setRows] = useState<PortfolioRow[] | null>(null);
  const [failed, setFailed] = useState(false);

  const refresh = useCallback(async () => {
    try {
      setRows(await gr<PortfolioRow[]>(`/grants/applications?project_id=${id}`));
      setFailed(false);
    } catch (err) {
      console.error("Failed to load the project's grant applications", err);
      setFailed(true);
    }
  }, [id]);

  useEffect(() => {
    // Fetch-on-mount: every setState in refresh happens after an await.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    refresh();
  }, [refresh]);

  return (
    <div>
      <div className="mb-3 flex items-center justify-between gap-3">
        <p className="text-sm text-ink-muted">
          Bids made for this project. Every application also appears in{" "}
          <Link href="/app/grants" className="underline hover:text-ink">
            Grant funding
          </Link>
          .
        </p>
        <Link href={`/app/grants/new?project=${id}`} className={btn}>
          New application for this project
        </Link>
      </div>
      {failed && (
        <p role="alert" className="mb-3 rounded-card bg-danger-soft px-3 py-2 text-sm text-danger">
          Grant applications failed to load.{" "}
          <button onClick={refresh} className="underline">
            Retry
          </button>
        </p>
      )}
      {rows && rows.length === 0 && (
        <p className="text-sm text-ink-muted">No grant applications for this project yet.</p>
      )}
      {rows && rows.length > 0 && (
        <ul className="flex flex-col gap-2">
          {rows.map((r) => (
            <li
              key={r.id}
              className="flex flex-wrap items-center justify-between gap-2 rounded-card border border-edge bg-surface p-3 text-sm"
            >
              <span className="min-w-0">
                <Link
                  href={`/app/grants/${r.id}`}
                  className="font-medium hover:text-electric-blue hover:underline"
                >
                  {r.title}
                </Link>
                <span className="block text-xs text-ink-muted">
                  {r.funder_name ?? "No funder set"} · {fmtMoney(r.amount_requested)} requested
                  {r.deadline ? ` · deadline ${fmtDate(r.deadline)}` : ""}
                </span>
              </span>
              <Stamp tone={STATUS_TONE[r.status]}>{STATUS_LABEL[r.status]}</Stamp>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
