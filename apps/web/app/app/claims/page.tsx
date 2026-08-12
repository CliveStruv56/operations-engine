"use client";

// The claims register: the facts this workspace asserts about itself, each
// with a date on it and something behind it.
//
// It is a register, not a dashboard — dull on purpose. The one thing it does
// insist on is the difference between a fact somebody has confirmed and a
// proposal still waiting for them, because everything downstream depends on
// that line holding.

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { Spinner } from "@/components/activity";
import {
  CATEGORY_LABELS,
  CATEGORY_ORDER,
  Claim,
  claimNote,
  deleteClaim,
  listClaims,
  sourceLabel,
  updateClaim,
} from "@/lib/claims";
import { useWorkspace } from "../workspace";
import { ImportPanel } from "./import-panel";

const card = "rounded-card border border-edge bg-card p-5 shadow-card";
const btn =
  "rounded-[10px] bg-accent px-4 py-2 text-sm font-medium text-accent-ink hover:bg-accent-deep disabled:opacity-50";
const btnGhost = "text-xs text-ink-muted underline hover:text-ink";

function ClaimRow({ claim, onChanged }: { claim: Claim; onChanged: () => void }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const note = claimNote(claim);
  const proposed = claim.status === "proposed";

  async function act(fn: () => Promise<unknown>) {
    setBusy(true);
    setError(null);
    try {
      await fn();
      onChanged();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <li className="border-t border-edge py-3 first:border-t-0">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <div className="min-w-0">
          <p className={proposed ? "text-ink" : "font-medium"}>{claim.statement}</p>
          <p className="mt-0.5 flex flex-wrap items-center gap-2 text-xs text-ink-faint">
            <span className="stamp text-ink-faint">{claim.label}</span>
            {claim.period && <span>{claim.period}</span>}
            <span>{sourceLabel(claim)}</span>
            {claim.source_ref && (
              <a
                href={claim.source_ref}
                target="_blank"
                rel="noopener noreferrer"
                className="underline"
              >
                check it
              </a>
            )}
            {!proposed && claim.next_review && !claim.stale && (
              <span>review by {claim.next_review}</span>
            )}
          </p>
        </div>

        <div className="flex shrink-0 items-center gap-3">
          {proposed ? (
            <>
              <button
                onClick={() => act(() => updateClaim(claim.id, { status: "confirmed" }))}
                disabled={busy}
                className={btn}
              >
                That&apos;s right
              </button>
              <button
                onClick={() => act(() => updateClaim(claim.id, { status: "rejected" }))}
                disabled={busy}
                className={btnGhost}
              >
                Not this
              </button>
            </>
          ) : (
            <>
              {(claim.stale || !claim.last_verified) && (
                <button
                  onClick={() => act(() => updateClaim(claim.id, { verified: true }))}
                  disabled={busy}
                  className={btnGhost}
                >
                  I have checked this
                </button>
              )}
              <button
                onClick={() => act(() => deleteClaim(claim.id))}
                disabled={busy}
                className={btnGhost}
              >
                Remove
              </button>
            </>
          )}
        </div>
      </div>

      {note && (
        <p className="mt-2 rounded-[10px] bg-warn-soft px-3 py-2 text-xs text-warn">{note}</p>
      )}
      {error && (
        <p className="mt-2 rounded-[10px] bg-danger-soft px-3 py-2 text-xs text-danger">{error}</p>
      )}
    </li>
  );
}

export default function ClaimsPage() {
  const ws = useWorkspace();
  const [claims, setClaims] = useState<Claim[] | null>(null);
  const [importing, setImporting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Confirming a proposal or checking a stale fact changes the sidebar count,
  // and this is the screen where that happens — a badge still claiming four
  // after somebody has just cleared all four is the fastest way to teach them
  // to ignore it.
  const refreshSummary = ws.refreshClaimSummary;
  const refresh = useCallback(() => {
    listClaims()
      .then(setClaims)
      .catch((e) => setError(e instanceof Error ? e.message : String(e)));
    refreshSummary();
  }, [refreshSummary]);

  useEffect(refresh, [refresh]);

  const live = (claims ?? []).filter((c) => c.status === "proposed" || c.status === "confirmed");
  const proposals = live.filter((c) => c.status === "proposed");
  const confirmed = live.filter((c) => c.status === "confirmed");
  const needsAttention = confirmed.filter((c) => c.stale || c.expired).length;

  return (
    <div className="mx-auto max-w-4xl space-y-4 p-6">
      <header className="flex flex-wrap items-baseline justify-between gap-2">
        <div>
          <h1 className="text-xl font-medium">Your organisation</h1>
          <p className="mt-1 text-sm text-ink-muted">
            The facts you assert about yourselves — registered details, trustees, finances,
            policies and cover. Drafts read from here, so a figure corrected once is corrected
            everywhere.
          </p>
        </div>
        {!importing && (
          <button onClick={() => setImporting(true)} className={btn}>
            Look up a register
          </button>
        )}
      </header>

      {importing && (
        <section className={card}>
          <h2 className="mb-3 font-medium">Fill this in from a public register</h2>
          <ImportPanel
            onCancel={() => setImporting(false)}
            onImported={() => {
              setImporting(false);
              refresh();
            }}
          />
        </section>
      )}

      {error && (
        <p className="rounded-[10px] bg-danger-soft px-3 py-2 text-sm text-danger">{error}</p>
      )}

      {claims === null ? (
        <p className="flex items-center gap-2 text-sm text-ink-muted">
          <Spinner /> Loading…
        </p>
      ) : live.length === 0 ? (
        // The activation moment. A first screen that asks somebody to fill in
        // fifty fields is the one this whole feature exists to avoid, so the
        // empty state points at the register rather than at a form.
        <section className={card}>
          <h2 className="font-medium">Nothing here yet — and you should not have to type it</h2>
          <p className="mt-2 text-sm text-ink-muted">
            Enter your charity number or company number and we will read the public register:
            your registered name, when you were formed, your registered office, your trustees or
            directors, and — for charities — your objects and latest income. Each one arrives with
            a link to where it came from, for you to confirm or reject.
          </p>
          <button onClick={() => setImporting(true)} className={`${btn} mt-4`}>
            Look up a register
          </button>
        </section>
      ) : (
        <>
          {proposals.length > 0 && (
            <section className={card}>
              <h2 className="font-medium">
                {proposals.length} {proposals.length === 1 ? "fact" : "facts"} to check
              </h2>
              <p className="mt-1 text-sm text-ink-muted">
                Found for you, not yet asserted. Nothing here reaches a draft until you say it is
                right.
              </p>
              <ul className="mt-3">
                {proposals.map((c) => (
                  <ClaimRow key={c.id} claim={c} onChanged={refresh} />
                ))}
              </ul>
            </section>
          )}

          {needsAttention > 0 && (
            <p className="rounded-[10px] bg-warn-soft px-3 py-2 text-sm text-warn">
              {needsAttention} {needsAttention === 1 ? "fact needs" : "facts need"} checking before
              you rely on {needsAttention === 1 ? "it" : "them"} again.
            </p>
          )}

          {CATEGORY_ORDER.map((category) => {
            const rows = confirmed.filter((c) => c.category === category);
            if (rows.length === 0) return null;
            return (
              <section key={category} className={card}>
                <h2 className="data mb-1 text-ink-muted uppercase">
                  {CATEGORY_LABELS[category]}
                </h2>
                <ul>
                  {rows.map((c) => (
                    <ClaimRow key={c.id} claim={c} onChanged={refresh} />
                  ))}
                </ul>
              </section>
            );
          })}
        </>
      )}

      <p className="text-xs text-ink-faint">
        Register data is published under the{" "}
        <Link
          href="https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/"
          target="_blank"
          rel="noopener noreferrer"
          className="underline"
        >
          Open Government Licence v3.0
        </Link>{" "}
        by Companies House, the Charity Commission for England and Wales, and OSCR.
      </p>
    </div>
  );
}
