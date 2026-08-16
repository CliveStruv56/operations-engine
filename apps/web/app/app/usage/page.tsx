"use client";

// The reference screen for Hearth's second pass.
//
// It was four identical tiles and two identical tables on one unbroken run of
// white-on-cream, with the month's spend — the only number anyone opens this
// page for — set in the 11px label voice at the same weight as "Tokens in".
//
// What changed, and why, since the same moves apply to the other screens:
//   - The figure that matters is the lead, in Fraunces with tabular figures.
//     The other three totals stay, quieter, as context for it.
//   - The tables sit in a tinted band. Hearth ships a second surface and the
//     app only ever used it for the sidebar, so every screen was one long
//     scroll of identical cards.
//   - Numbers are tabular and right-aligned, so a column of costs can be
//     compared by eye rather than read one row at a time.
//   - Loading is a skeleton in the shape of the answer, not a line of text
//     that gets replaced by a layout twice its height.

import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import {
  Band,
  Button,
  Card,
  EmptyState,
  ErrorNote,
  LoadingRegion,
  Section,
  Skeleton,
  Table,
  Td,
  Th,
  Tr,
} from "@/components/ui";
import { inputInline } from "@/components/ui/styles";
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

// What each internal routing alias does, in the reader's terms.
const MODEL_LABELS: Record<string, string> = {
  workhorse: "Chat",
  drafter: "Drafting",
  reasoner: "Reasoning",
  longdoc: "Long documents",
  embedder: "Document indexing",
  exa: "Web search",
};

const num = new Intl.NumberFormat("en-GB");
const usd = (v: number) => `$${v.toFixed(v >= 1 ? 2 : 4)}`;
const gbp = (v: number) => `£${(v * GBP_PER_USD).toFixed(v * GBP_PER_USD >= 1 ? 2 : 4)}`;

function currentMonth(): string {
  return new Date().toISOString().slice(0, 7);
}

/** "2026-08" -> "August 2026", for a heading a human would write. */
function monthName(month: string): string {
  const [y, m] = month.split("-").map(Number);
  if (!y || !m) return month;
  return new Date(y, m - 1, 1).toLocaleDateString("en-GB", { month: "long", year: "numeric" });
}

function BucketTable({
  title,
  rows,
  columnLabel,
  label,
}: {
  title: string;
  rows: UsageBucket[];
  columnLabel: string;
  label: (key: string) => string;
}) {
  return (
    <Card padded={false}>
      <h3 className="data border-b border-edge px-4 py-3 text-subtle uppercase">{title}</h3>
      {rows.length === 0 ? (
        <p className="px-4 py-6 text-center text-sm text-subtle">
          Nothing recorded against {title.toLowerCase()} this month.
        </p>
      ) : (
        <Table label={title}>
          <thead>
            <tr className="border-b border-edge">
              <Th>{columnLabel}</Th>
              <Th numeric>Requests</Th>
              <Th numeric>Tokens in</Th>
              <Th numeric>Tokens out</Th>
              <Th numeric>Cost $</Th>
              <Th numeric>Cost £</Th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <Tr key={r.key}>
                <Td className="max-w-56 truncate" title={label(r.key)}>
                  {label(r.key)}
                </Td>
                <Td numeric>{num.format(r.requests)}</Td>
                <Td numeric>{num.format(r.tokens_in)}</Td>
                <Td numeric>{num.format(r.tokens_out)}</Td>
                <Td numeric>{usd(r.cost_usd)}</Td>
                <Td numeric>{gbp(r.cost_usd)}</Td>
              </Tr>
            ))}
          </tbody>
        </Table>
      )}
    </Card>
  );
}

/** The month's spend, given the room it earns. Everything else on the page is
 *  the working behind this number. */
function SpendLead({ summary }: { summary: UsageSummary }) {
  const context = [
    { label: "Requests", value: num.format(summary.requests) },
    { label: "Tokens in", value: num.format(summary.tokens_in) },
    { label: "Tokens out", value: num.format(summary.tokens_out) },
  ];

  return (
    <div className="grid gap-3 sm:grid-cols-3">
      {/* Centred: the row's height comes from the three stacked tiles beside
          it, so left-aligning to the top leaves the figure floating in space. */}
      <Card className="flex flex-col justify-center sm:col-span-2">
        <p className="data text-electric-blue uppercase">{monthName(summary.month)}</p>
        <p className="figure mt-1.5 text-[34px] leading-none text-ink">
          {gbp(summary.cost_usd)}
        </p>
        <p className="mt-2 text-sm text-subtle">
          {usd(summary.cost_usd)} metered ·{" "}
          {summary.requests === 0
            ? "no calls yet"
            : `${num.format(summary.requests)} call${summary.requests === 1 ? "" : "s"}`}
        </p>
      </Card>
      <div className="grid gap-3">
        {context.map((c) => (
          <div key={c.label} className="rounded-card border border-edge bg-card px-4 py-2.5">
            <p className="data text-subtle uppercase">{c.label}</p>
            <p className="tnum mt-0.5 truncate text-sm font-semibold text-ink" title={c.value}>
              {c.value}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}

/** Placeholders in the shape of what is coming — the lead figure, its three
 *  context tiles, then a table — so nothing moves when the data lands. */
function UsageSkeleton() {
  return (
    <LoadingRegion label="Loading usage">
      <div className="grid gap-3 sm:grid-cols-3">
        <Card className="sm:col-span-2">
          <Skeleton className="h-3 w-24" />
          <Skeleton className="mt-3 h-8 w-40" />
          <Skeleton className="mt-3 h-3 w-52" />
        </Card>
        <div className="grid gap-3">
          {[0, 1, 2].map((i) => (
            <div key={i} className="rounded-card border border-edge bg-card px-4 py-3">
              <Skeleton className="h-3 w-20" />
              <Skeleton className="mt-2 h-3 w-14" />
            </div>
          ))}
        </div>
      </div>
      <Card padded={false} className="mt-4 overflow-hidden">
        <div className="border-b border-edge px-4 py-3">
          <Skeleton className="h-3 w-20" />
        </div>
        {[0, 1, 2].map((i) => (
          <div key={i} className="flex items-center justify-between px-4 py-3">
            <Skeleton className="h-3 w-32" />
            <Skeleton className="h-3 w-16" />
          </div>
        ))}
      </Card>
    </LoadingRegion>
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
    // switching month shows the skeleton immediately.
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

  // Routing aliases (app/routing.py) in words a client would use. Chat rows
  // may carry the provider's own model id instead — those show as they are.
  const modelLabel = (key: string) => MODEL_LABELS[key] ?? key;

  if (!tenant) return null;

  const nothingYet = summary !== null && summary.requests === 0;

  return (
    <main className="min-h-0 flex-1 overflow-y-auto">
      <div className="mx-auto max-w-3xl px-6 pt-6 pb-7">
        <header className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <h1 className="font-display text-hearth-page leading-tight font-medium tracking-[-0.01em]">
              Usage
            </h1>
            <p className="mt-1 max-w-[60ch] text-sm text-subtle">
              Model spend for {tenant.name}. Billing is metered in US dollars; £ is shown at{" "}
              {GBP_PER_USD.toFixed(2)} to the dollar for reference.
            </p>
          </div>
          <label className="text-sm">
            <span className="data mb-1 block text-subtle uppercase">Month</span>
            <input
              type="month"
              value={month}
              max={currentMonth()}
              onChange={(e) => e.target.value && setMonth(e.target.value)}
              className={inputInline}
            />
          </label>
        </header>

        {error && (
          <ErrorNote
            className="mt-4"
            action={
              <Button variant="secondary" onClick={load}>
                Try again
              </Button>
            }
          >
            {error}
          </ErrorNote>
        )}

        {loading ? (
          <div className="mt-5">
            <UsageSkeleton />
          </div>
        ) : (
          summary && !nothingYet && <div className="mt-5">
            <SpendLead summary={summary} />
          </div>
        )}
      </div>

      {!loading && nothingYet && (
        <div className="mx-auto max-w-3xl px-6 pb-7">
          <EmptyState title={`Nothing metered in ${monthName(month)}`}>
            Every model call this workspace makes is costed and lands here — chat answers,
            document indexing, drafts and web searches. Ask something in chat, or pick a
            different month.
          </EmptyState>
        </div>
      )}

      {/* The band is the point: two tables that answer the same question from
          different angles read as one section, and the page stops being a
          single unbroken column of white cards. */}
      {!loading && summary && !nothingYet && (
        <Band className="mt-2">
          <Section
            title="Where it went"
            kicker="Breakdown"
            description="The same spend split two ways — by what the workspace asked for, and by who asked."
          >
            <div className="space-y-4">
              <BucketTable
                title="By model"
                columnLabel="Model"
                rows={summary.by_model}
                label={modelLabel}
              />
              <BucketTable
                title="By member"
                columnLabel="Member"
                rows={summary.by_user}
                label={userLabel}
              />
            </div>
          </Section>
        </Band>
      )}
    </main>
  );
}
