"use client";

// The claims register: the facts this workspace asserts about itself, each
// with a date on it and something behind it.
//
// It is a register, not a dashboard — dull on purpose. The one thing it does
// insist on is the difference between a fact somebody has confirmed and a
// proposal still waiting for them, because everything downstream depends on
// that line holding.

import { Suspense, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
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
import { Member, listMembers, memberName } from "@/lib/members";
import { useWorkspace } from "../workspace";
import { ImportPanel } from "./import-panel";

const card = "rounded-card border border-edge bg-card p-5 shadow-card";
const btn =
  "rounded-[10px] bg-accent px-4 py-2 text-sm font-medium text-accent-ink hover:bg-accent-deep disabled:opacity-50";
const btnGhost = "text-xs text-ink-muted underline hover:text-ink";

function ClaimRow({
  claim,
  members,
  onChanged,
}: {
  claim: Claim;
  members: Member[];
  onChanged: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const note = claimNote(claim);
  const proposed = claim.status === "proposed";
  const owner = memberName(members, claim.owner_membership_id);

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
            {/* Ownership is optional and most facts will never have an owner,
                so this is stated plainly and never as a warning — see
                ASSUMPTIONS #43. A proposal has no owner because nobody has
                asserted it yet; confirming it is the moment that question
                starts to make sense. */}
            {!proposed && (
              <label>
                <span className="sr-only">Who looks after “{claim.statement}”</span>
                <select
                  value={claim.owner_membership_id ?? ""}
                  disabled={busy}
                  onChange={(e) =>
                    act(() =>
                      updateClaim(claim.id, { owner_membership_id: e.target.value || null }),
                    )
                  }
                  className="rounded-[6px] border border-edge bg-surface px-1 py-px text-xs text-ink-muted disabled:opacity-50"
                >
                  <option value="">nobody looks after this</option>
                  {members.map((m) => (
                    <option key={m.id} value={m.id}>
                      {m.email ?? m.user_id}
                    </option>
                  ))}
                  {/* The owner has just been removed in another tab; keep the
                      select honest rather than silently showing "nobody". */}
                  {claim.owner_membership_id !== null &&
                    !members.some((m) => m.id === claim.owner_membership_id) && (
                      <option value={claim.owner_membership_id}>{owner}</option>
                    )}
                </select>
              </label>
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
  return (
    // useSearchParams needs a Suspense boundary at the page level.
    <Suspense>
      <ClaimsPageInner />
    </Suspense>
  );
}

function ClaimsPageInner() {
  const ws = useWorkspace();
  const router = useRouter();
  const sp = useSearchParams();
  const [claims, setClaims] = useState<Claim[] | null>(null);
  const [members, setMembers] = useState<Member[]>([]);
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

  useEffect(() => {
    // Only for labelling and the owner picker: a register that cannot list the
    // workspace's people is still a readable register, so this failing must not
    // take the screen down.
    listMembers()
      .then(setMembers)
      .catch((e) => console.error("Failed to load members", e));
  }, []);

  const live = (claims ?? []).filter((c) => c.status === "proposed" || c.status === "confirmed");
  const proposals = live.filter((c) => c.status === "proposed");
  const allConfirmed = live.filter((c) => c.status === "confirmed");
  const needsAttention = allConfirmed.filter((c) => c.stale || c.expired).length;

  // A view somebody opts into, never a badge (ASSUMPTIONS #43): ownership is
  // optional and most facts never have an owner, so "nobody owns this" is a
  // question to go looking for, not a warning to be shown. It is a URL because
  // the removal confirmation in Settings links straight to it — the moment
  // somebody's facts are released is the moment to go and reassign them.
  const unownedOnly = sp.get("owner") === "none";
  const unowned = allConfirmed.filter((c) => c.owner_membership_id === null);
  const confirmed = unownedOnly ? unowned : allConfirmed;

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
          {/* Proposals are about whether a fact is right, which is a different
              question from who keeps it right — so the filtered view leaves
              them out rather than mixing the two. */}
          {proposals.length > 0 && !unownedOnly && (
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
                  <ClaimRow key={c.id} claim={c} members={members} onChanged={refresh} />
                ))}
              </ul>
            </section>
          )}

          {needsAttention > 0 && !unownedOnly && (
            <p className="rounded-[10px] bg-warn-soft px-3 py-2 text-sm text-warn">
              {needsAttention} {needsAttention === 1 ? "fact needs" : "facts need"} checking before
              you rely on {needsAttention === 1 ? "it" : "them"} again.
            </p>
          )}

          {/* Deliberately not warn-coloured. Nothing here is wrong; these facts
              are true and simply nobody's, which is the ordinary state of most
              of them. */}
          {unownedOnly ? (
            <p className="flex flex-wrap items-baseline justify-between gap-2 rounded-[10px] bg-accent-soft px-3 py-2 text-sm">
              <span>
                {unowned.length === 0
                  ? "Somebody looks after every fact here."
                  : `${unowned.length} ${unowned.length === 1 ? "fact has" : "facts have"} nobody looking after ${unowned.length === 1 ? "it" : "them"}. Use the picker on a row to hand it to somebody.`}
              </span>
              <button onClick={() => router.push("/app/claims")} className={btnGhost}>
                Show everything
              </button>
            </p>
          ) : (
            // Hidden while nobody owns anything — which is every workspace
            // until somebody starts assigning. "See the 40 facts nobody owns"
            // when that is all 40 of them is noise, not a finding.
            unowned.length > 0 &&
            unowned.length < allConfirmed.length && (
              <p className="text-xs text-ink-faint">
                <button
                  onClick={() => router.push("/app/claims?owner=none")}
                  className="underline hover:text-ink"
                >
                  {unowned.length} {unowned.length === 1 ? "fact has" : "facts have"} nobody looking
                  after {unowned.length === 1 ? "it" : "them"}
                </button>
              </p>
            )
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
                    <ClaimRow key={c.id} claim={c} members={members} onChanged={refresh} />
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
