"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  PortfolioRow,
  RAG_DOT,
  STAGES,
  STAGE_LABEL,
  fmtDate,
  gw,
  tenantId,
} from "@/lib/groundwork";

const RAG_HINT: Record<string, string> = {
  programme: "Programme: red = a milestone is more than 30 days overdue",
  cost: "Cost: red = forecast exceeds budget by more than 10%",
  risk: "Risk: red = an open risk scores 16+ (likelihood × impact)",
};

function StageStepper({ current }: { current: string }) {
  const idx = STAGES.indexOf(current as (typeof STAGES)[number]);
  return (
    <span className="flex items-center gap-1" title={`Stage: ${STAGE_LABEL[current]}`}>
      {STAGES.map((s, i) => (
        <span
          key={s}
          className={`h-1.5 w-4 rounded-full ${
            i < idx ? "bg-accent/40" : i === idx ? "bg-accent" : "bg-line"
          }`}
        />
      ))}
      <span className="data ml-1 text-ink-muted uppercase">{STAGE_LABEL[current]}</span>
    </span>
  );
}

export function RagDots({ rag }: { rag: PortfolioRow["rag"] }) {
  return (
    <span className="flex items-center gap-1.5">
      {(["programme", "cost", "risk"] as const).map((k) => (
        <span
          key={k}
          title={`${RAG_HINT[k]} — currently ${rag[k]}`}
          className={`h-2.5 w-2.5 rounded-full ${RAG_DOT[rag[k]]}`}
        />
      ))}
    </span>
  );
}

export default function PortfolioPage() {
  const router = useRouter();
  const [rows, setRows] = useState<PortfolioRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!tenantId()) {
      router.push("/app");
      return;
    }
     
    gw<PortfolioRow[]>("/projects/portfolio")
      .then(setRows)
      .catch((e) => setError(e instanceof Error ? e.message : String(e)));
  }, [router]);

  return (
    <main className="mx-auto max-w-6xl p-6">
      <header className="mb-6 flex items-baseline justify-between">
        <div>
          <p className="data text-ink-faint uppercase">
            <Link href="/app" className="hover:text-ink">
              ← Workspace
            </Link>
          </p>
          <h1 className="mt-1 text-xl font-semibold tracking-tight">Development projects</h1>
        </div>
        <Link
          href="/app/projects/new"
          className="rounded-sm bg-accent px-4 py-2 text-sm font-medium text-accent-ink hover:opacity-90"
        >
          New development project
        </Link>
      </header>

      {error && <p className="rounded-sm bg-danger-soft px-3 py-2 text-sm text-danger">{error}</p>}

      {rows && rows.length === 0 && (
        <div className="rounded-md border border-line bg-surface p-10 text-center">
          <p className="text-sm font-medium">
            Track each development scheme from first meeting to occupied homes.
          </p>
          <p className="mt-1 text-sm text-ink-muted">
            A new project starts with the full CLH stage plan, task list, document checklist and
            risk register already in place.
          </p>
        </div>
      )}

      {rows && rows.length > 0 && (
        <div className="overflow-x-auto rounded-md border border-line bg-surface">
          <table className="w-full text-sm">
            <thead>
              <tr className="data border-b border-line text-left text-ink-muted uppercase">
                <th className="px-4 py-2.5">Project</th>
                <th className="px-4 py-2.5">Client</th>
                <th className="px-4 py-2.5">Stage</th>
                <th className="px-4 py-2.5">Health</th>
                <th className="px-4 py-2.5">Next milestone</th>
                <th className="px-4 py-2.5">Pre-comm.</th>
                <th className="px-4 py-2.5">Updated</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {rows.map((r) => {
                const overdue =
                  r.next_milestone && new Date(r.next_milestone.due_date) < new Date();
                return (
                  <tr
                    key={r.id}
                    onClick={() => router.push(`/app/projects/${r.id}`)}
                    className={`cursor-pointer hover:bg-accent-soft ${
                      r.status !== "active" ? "opacity-60" : ""
                    }`}
                  >
                    <td className="px-4 py-3 font-medium">
                      {r.name}
                      {r.status === "dormant" && (
                        <span className="stamp ml-2 text-warn bg-warn-soft">
                          dormant · {r.dormancy_reason}
                        </span>
                      )}
                      {r.status === "complete" && (
                        <span className="stamp ml-2 text-accent bg-accent-soft">complete</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-ink-muted">{r.client_org ?? "—"}</td>
                    <td className="px-4 py-3">
                      <StageStepper current={r.stage_current} />
                    </td>
                    <td className="px-4 py-3">
                      <RagDots rag={r.rag} />
                    </td>
                    <td className={`px-4 py-3 ${overdue ? "text-danger" : "text-ink-muted"}`}>
                      {r.next_milestone
                        ? `${r.next_milestone.title} · ${fmtDate(r.next_milestone.due_date)}`
                        : "—"}
                    </td>
                    <td className="data px-4 py-3">
                      {r.outstanding_pre_commencement > 0 ? (
                        <span className="text-warn">{r.outstanding_pre_commencement} open</span>
                      ) : (
                        "0"
                      )}
                    </td>
                    <td className="data px-4 py-3 text-ink-faint">{fmtDate(r.updated_at)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </main>
  );
}
