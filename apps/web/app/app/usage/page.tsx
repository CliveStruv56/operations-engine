"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import { Spinner } from "@/components/activity";
import { useWorkspace } from "../workspace";

type UsageBucket = {
  key: string;
  tokens_in: number;
  tokens_out: number;
  cost_usd: number;
  requests: number;
};

type UsageSummary = {
  month: string;
  tokens_in: number;
  tokens_out: number;
  cost_usd: number;
  requests: number;
  by_user: UsageBucket[];
  by_model: UsageBucket[];
};

type Member = { user_id: string; email: string | null };

// Display-only conversion for the £ column; costs are metered in USD.
const GBP_PER_USD = Number(process.env.NEXT_PUBLIC_GBP_PER_USD ?? "0.79");

const card = "rounded-md border border-line bg-paper p-5";

const num = new Intl.NumberFormat("en-GB");
const usd = (v: number) => `$${v.toFixed(v >= 1 ? 2 : 4)}`;
const gbp = (v: number) => `£${(v * GBP_PER_USD).toFixed(v * GBP_PER_USD >= 1 ? 2 : 4)}`;

function currentMonth(): string {
  return new Date().toISOString().slice(0, 7);
}

function BucketTable({
  title,
  rows,
  label,
}: {
  title: string;
  rows: UsageBucket[];
  label: (key: string) => string;
}) {
  return (
    <section className={card}>
      <h2 className="data mb-3 text-ink-muted uppercase">{title}</h2>
      {rows.length === 0 ? (
        <p className="text-sm text-ink-faint">No usage this month.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="data border-b border-line text-left text-ink-muted uppercase">
                <th scope="col" className="py-1.5 pr-3 font-normal">
                  {title === "By model" ? "Model" : "Member"}
                </th>
                <th scope="col" className="py-1.5 pr-3 text-right font-normal">Requests</th>
                <th scope="col" className="py-1.5 pr-3 text-right font-normal">Tokens in</th>
                <th scope="col" className="py-1.5 pr-3 text-right font-normal">Tokens out</th>
                <th scope="col" className="py-1.5 pr-3 text-right font-normal">Cost $</th>
                <th scope="col" className="py-1.5 text-right font-normal">Cost £</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.key} className="border-b border-line/60 last:border-0">
                  <td className="max-w-56 truncate py-1.5 pr-3" title={label(r.key)}>
                    {label(r.key)}
                  </td>
                  <td className="data py-1.5 pr-3 text-right">{num.format(r.requests)}</td>
                  <td className="data py-1.5 pr-3 text-right">{num.format(r.tokens_in)}</td>
                  <td className="data py-1.5 pr-3 text-right">{num.format(r.tokens_out)}</td>
                  <td className="data py-1.5 pr-3 text-right">{usd(r.cost_usd)}</td>
                  <td className="data py-1.5 text-right">{gbp(r.cost_usd)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

export default function UsagePage() {
  const ws = useWorkspace();
  const tenant = ws.tenant;
  const [month, setMonth] = useState(currentMonth);
  const [summary, setSummary] = useState<UsageSummary | null>(null);
  const [members, setMembers] = useState<Member[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const tenantId = tenant?.id;

  const load = useCallback(async () => {
    if (!tenantId) return;
    setLoading(true);
    setError(null);
    try {
      setSummary(await api<UsageSummary>(`/usage/summary?month=${month}`, {}, tenantId));
    } catch (err) {
      setSummary(null);
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, [tenantId, month]);

  useEffect(() => {
    // Fetch-on-change: setLoading(true) fires before the await by design so
    // switching month shows the spinner immediately.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    load();
  }, [load]);

  useEffect(() => {
    if (!tenantId) return;
    api<Member[]>("/members", {}, tenantId)
      .then(setMembers)
      .catch(() => setMembers([])); // usage still renders with raw ids
  }, [tenantId]);

  const emailByUser = useMemo(
    () => new Map(members.map((m) => [m.user_id, m.email])),
    [members]
  );

  const userLabel = useCallback(
    (key: string) => {
      if (key === "unknown") return "System (ingestion & drafts)";
      return emailByUser.get(key) ?? `${key.slice(0, 8)}…`;
    },
    [emailByUser]
  );

  if (!tenant) return null;

  const tiles = summary
    ? [
        { label: "Requests", value: num.format(summary.requests) },
        { label: "Tokens in", value: num.format(summary.tokens_in) },
        { label: "Tokens out", value: num.format(summary.tokens_out) },
        { label: "Cost", value: `${usd(summary.cost_usd)} · ${gbp(summary.cost_usd)}` },
      ]
    : [];

  return (
    <main className="min-h-0 flex-1 overflow-y-auto">
      <div className="mx-auto max-w-3xl space-y-5 p-6">
        <header className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h1 className="text-xl font-semibold tracking-tight">Usage</h1>
            <p className="mt-0.5 text-sm text-ink-muted">
              Model spend for {tenant.name}. £ shown at {GBP_PER_USD.toFixed(2)}/$ for
              reference — billing is metered in USD.
            </p>
          </div>
          <label className="text-sm">
            <span className="data block text-ink-muted uppercase">Month</span>
            <input
              type="month"
              value={month}
              max={currentMonth()}
              onChange={(e) => e.target.value && setMonth(e.target.value)}
              className="mt-1 rounded-sm border border-line bg-surface px-3 py-2 text-sm"
            />
          </label>
        </header>

        {error && (
          <p role="alert" className="rounded-sm border border-danger/40 bg-danger-soft px-3 py-2 text-sm text-danger">
            {error}
          </p>
        )}

        {loading ? (
          <p className="flex items-center gap-2 text-sm text-ink-muted">
            <Spinner className="text-accent" /> Loading usage…
          </p>
        ) : (
          summary && (
            <>
              <section className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                {tiles.map((t) => (
                  <div key={t.label} className={`${card} !p-4`}>
                    <p className="data text-ink-muted uppercase">{t.label}</p>
                    <p className="data mt-1 truncate text-lg text-ink" title={t.value}>
                      {t.value}
                    </p>
                  </div>
                ))}
              </section>
              <BucketTable title="By model" rows={summary.by_model} label={(k) => k} />
              <BucketTable title="By member" rows={summary.by_user} label={userLabel} />
            </>
          )
        )}
      </div>
    </main>
  );
}
