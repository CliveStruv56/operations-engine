"""The tenant's own standing facts, on their way into a draft.

Shared by every module rather than owned by one, for the same reason the table
is unflagged core: a case for support, a funding bid and a bid response all
open by saying who the organisation is, and they should all say the same thing.

Two kinds of claim reach a prompt and they are handled differently, which is
the only subtlety here:

**Document-backed claims** name a real `doc_chunks` row. Their chunk goes into
`pack.claim_excerpts`, the engine merges it into `pack.excerpts`, and the model
is told to cite it as `[c:<id>]`. Nothing in the citation machinery changes —
the id resolves through the same index into the same References page.

**Register-backed claims** have no chunk, because Companies House is not a
document in the vault. Inventing a pseudo-chunk for one would be lying about
the evidence, so the model is told plainly not to cite them, and their
provenance reaches the Data sources appendix through `source_notes()` instead.
That is also what discharges the Open Government Licence attribution.
"""

from datetime import date
from uuid import UUID

import asyncpg

from worker.drafting.pack import ClaimFacts, VaultExcerpt

#: A workspace is expected to hold 40–80 claims. The cap is well clear of that
#: and exists only so a pathological register cannot push a section prompt into
#: the context ceiling; `LlmLedger.check_next_call` would catch it, but failing
#: a draft is a worse answer than dropping the eightieth accreditation.
MAX_CLAIMS = 150

#: Evidence chunks are the expensive half — full document text, not one line.
#: Eight is roughly what vault retrieval itself returns for a section.
MAX_CLAIM_EXCERPTS = 8


async def load_claims(
    conn: asyncpg.Connection, today: date
) -> tuple[list[ClaimFacts], list[VaultExcerpt]]:
    """Confirmed claims and the vault chunks behind them.

    Runs inside the caller's tenant transaction, so RLS applies. Proposals are
    excluded: a fact nobody has confirmed is not something this workspace
    asserts, and a draft is exactly where that distinction has to hold.
    """
    rows = await conn.fetch(
        """
        select c.kind, c.subject, c.period, c.statement, c.as_of, c.expires_on,
               c.source, c.source_ref, c.source_chunk_id, c.last_verified, c.next_review,
               coalesce(k.label, c.kind) as label,
               coalesce(k.category, 'identity') as category
        from claims c left join ref_claim_kinds k on k.key = c.kind
        where c.status = 'confirmed'
        order by c.kind, coalesce(c.subject, ''), coalesce(c.period, '')
        limit $1
        """,
        MAX_CLAIMS,
    )

    # Fetch the evidence in one query rather than per claim: a workspace that
    # has been ticking document proposals for a month can easily have thirty.
    chunk_ids = [r["source_chunk_id"] for r in rows if r["source_chunk_id"] is not None]
    excerpts: dict[UUID, VaultExcerpt] = {}
    if chunk_ids:
        chunk_rows = await conn.fetch(
            """
            select ch.id, ch.document_id, ch.content, ch.page_start, ch.page_end, d.title
            from doc_chunks ch join documents d on d.id = ch.document_id
            where ch.id = any($1::uuid[])
            limit $2
            """,
            chunk_ids,
            MAX_CLAIM_EXCERPTS,
        )
        excerpts = {
            r["id"]: VaultExcerpt(
                chunk_id=r["id"],
                document_id=r["document_id"],
                title=r["title"],
                page_start=r["page_start"],
                page_end=r["page_end"],
                content=r["content"],
            )
            for r in chunk_rows
        }

    claims = [
        ClaimFacts(
            kind=r["kind"],
            label=r["label"],
            subject=r["subject"],
            period=r["period"],
            statement=r["statement"],
            as_of=r["as_of"],
            expires_on=r["expires_on"],
            source=r["source"],
            source_ref=r["source_ref"],
            # Only claim a citation when the chunk actually came back. A
            # document deleted since the claim was made leaves the fact
            # standing but uncitable, and telling the model to cite an id that
            # is not in the excerpts is how stripped markers happen.
            chunk_id=(r["source_chunk_id"] if r["source_chunk_id"] in excerpts else None),
            last_verified=r["last_verified"],
            next_review=r["next_review"],
            stale=r["next_review"] is not None and r["next_review"] <= today,
            expired=r["expires_on"] is not None and r["expires_on"] < today,
        )
        for r in rows
    ]
    return claims, list(excerpts.values())


def claims_block(claims: list[ClaimFacts]) -> str:
    """The facts, one per line, each saying whether it may be cited."""
    lines = []
    for claim in claims:
        qualifiers = []
        if claim.period:
            qualifiers.append(claim.period)
        if claim.as_of:
            qualifiers.append(f"as at {claim.as_of.isoformat()}")
        if claim.expired:
            # Said inline as well as in the first-page warning: the model must
            # not assert lapsed cover as current, whatever the reader is told.
            qualifiers.append(f"EXPIRED {claim.expires_on.isoformat()}")
        elif claim.stale:
            qualifiers.append("overdue for review")
        suffix = f" ({'; '.join(qualifiers)})" if qualifiers else ""

        if claim.chunk_id is not None:
            provenance = f"cite as [c:{claim.chunk_id}]"
        elif claim.source == "register":
            provenance = "from the public register — do not cite"
        else:
            provenance = "recorded by the organisation — do not cite"
        lines.append(f"- {claim.statement}{suffix} [{provenance}]")
    return "\n".join(lines)


def claims_warning(claims: list[ClaimFacts]) -> str | None:
    """First-page warning when a draft leans on a fact that has gone off.

    Names the specific problem rather than gesturing at staleness, following
    `warning_for`: "four claims are stale" tells a reader nothing they can act
    on, whereas a lapsed insurance date sends them to the right filing cabinet.

    Only the claims that are actually a problem are counted. Warning because a
    workspace holds eighty facts would put a warning on every draft, and a
    warning that is always there is not read.
    """
    expired = [c for c in claims if c.expired]
    stale = [c for c in claims if c.stale and not c.expired]
    if not expired and not stale:
        return None

    if expired:
        first = expired[0]
        lead = (
            f"{first.statement.rstrip('.')} — but that lapsed on {first.expires_on.isoformat()}."
        )
        if len(expired) > 1:
            lead += f" {len(expired) - 1} other lapsed item(s) are also used here."
    else:
        first = stale[0]
        lead = (
            f"This draft relies on {len(stale)} fact(s) that are past review, including: "
            f"{first.statement.rstrip('.')}"
            + (
                f", last checked {first.last_verified.isoformat()}."
                if first.last_verified
                else ", never checked."
            )
        )
    return f"{lead} Check before submitting."


def claim_source_notes(claims: list[ClaimFacts]) -> list[str]:
    """Data sources lines for facts that carry no `[c:]` citation.

    Document-backed claims need nothing here — their chunk is in the excerpts,
    so they already appear on the References page by number. Register-backed
    ones have nowhere else to be named, and naming them is both the useful
    thing for a procurement officer and the Open Government Licence
    attribution the registers require.
    """
    by_url: dict[str, int] = {}
    for claim in claims:
        if claim.source != "register" or not claim.source_ref:
            continue
        by_url[claim.source_ref] = by_url.get(claim.source_ref, 0) + 1

    notes = []
    for url, count in by_url.items():
        verified = next(
            (c.last_verified for c in claims if c.source_ref == url and c.last_verified), None
        )
        note = f"{count} organisational fact(s) from the public register at {url}"
        if verified:
            note += f", confirmed {verified.isoformat()}"
        notes.append(note + ".")
    return notes


def merge_excerpts(existing: list[VaultExcerpt], extra: list[VaultExcerpt]) -> list[VaultExcerpt]:
    """Add claim evidence to whatever retrieval found, without duplicates.

    Kept here rather than inline in the engine so the dedupe rule has one home:
    a chunk that is both retrieved for a section and cited by a claim must
    appear once, or the model sees the same id twice with different framing.
    """
    seen = {e.chunk_id for e in existing}
    return existing + [e for e in extra if e.chunk_id not in seen]
