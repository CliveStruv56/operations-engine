"use client";

import { useState } from "react";
import { Claim, claimNote, deleteClaim, sourceLabel, updateClaim } from "@/lib/claims";
import { Member, memberName } from "@/lib/members";

const btn =
  "rounded-[10px] bg-accent px-4 py-2 text-sm font-medium text-accent-ink hover:bg-accent-deep disabled:opacity-50";
const btnGhost = "text-xs text-ink-muted underline hover:text-ink";

export function ClaimRow({
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
