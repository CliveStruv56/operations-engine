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

import json
from datetime import date
from typing import TYPE_CHECKING, Any
from uuid import UUID

import asyncpg

from worker.drafting.pack import ClaimFacts, VaultExcerpt

if TYPE_CHECKING:  # import cycle: extract.py has no need of this module
    from worker.claims.extract import ExtractedFact, KindSpec

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
        select c.id, c.kind, c.subject, c.period, c.statement, c.value, c.unit,
               c.as_of, c.expires_on, c.source, c.source_ref, c.source_chunk_id,
               c.last_verified, c.next_review,
               coalesce(k.label, c.kind) as label,
               coalesce(k.value_kind, 'text') as value_kind,
               coalesce(k.cardinality, 'single') as cardinality,
               coalesce(k.question_hints, '{}') as question_hints
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
            id=r["id"],
            kind=r["kind"],
            label=r["label"],
            subject=r["subject"],
            period=r["period"],
            statement=r["statement"],
            value=json.loads(r["value"]) if isinstance(r["value"], str) else r["value"],
            value_kind=r["value_kind"],
            unit=r["unit"],
            question_hints=list(r["question_hints"] or []),
            cardinality=r["cardinality"],
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


async def load_kind_specs(conn: asyncpg.Connection) -> list["KindSpec"]:
    """The fact-type catalogue, in the shape extraction needs it.

    Register-only kinds are excluded: nothing in a tenant's own documents
    establishes their Companies House status, and offering the model a kind it
    cannot honestly fill is an invitation to fill it anyway.
    """
    from worker.claims.extract import KindSpec

    rows = await conn.fetch(
        """
        select key, label, value_kind, cardinality, question_hints
        from ref_claim_kinds
        where key not in ('registration_status', 'company_number', 'charity_number')
        order by key
        """
    )
    return [
        KindSpec(
            key=r["key"],
            label=r["label"],
            value_kind=r["value_kind"],
            cardinality=r["cardinality"],
            question_hints=list(r["question_hints"] or []),
        )
        for r in rows
    ]


def _parse_date(raw: str | None) -> date | None:
    """A model-supplied date, or nothing.

    Anything it could not read as ISO is dropped rather than guessed at: a
    wrong expiry date is worse than none, because none shows as "nobody has
    checked this" and a wrong one shows as cover that is fine.
    """
    if not raw:
        return None
    try:
        return date.fromisoformat(raw.strip()[:10])
    except ValueError:
        return None


def render_statement(
    template: str, label: str, subject: str | None, value: Any, value_kind: str = "text"
) -> str:
    """The sentence a person reads when deciding whether to keep the fact.

    Deliberately a copy of `app/claims/service.py::render_statement`, and the
    same standing hazard as the worker's copy of the alias price table
    (ASSUMPTIONS #27): the API renders when a register import or a person
    writes a claim, and the worker renders when a document proposes one, and
    the two must not drift — or the same organisation's income would read
    "£847,000" from Companies House and "847000" from its own accounts, and a
    person ticking both would have no idea they were the same fact.

    The drift is not hypothetical: this function shipped without the money
    branch and a test caught exactly that pair of statements.
    """
    if value is None or isinstance(value, dict):
        rendered = ""
    elif isinstance(value, list):
        rendered = ", ".join(str(v) for v in value)
    elif value_kind == "money" and isinstance(value, int | float):
        rendered = f"£{value:,.0f}"
    elif value_kind == "number" and isinstance(value, float) and value.is_integer():
        rendered = str(int(value))
    elif isinstance(value, float) and value.is_integer():
        rendered = str(int(value))
    else:
        rendered = str(value)
    try:
        statement = template.format(value=rendered, subject=subject or label)
    except (KeyError, IndexError):
        statement = f"{label}: {rendered}" if rendered else label
    return statement.strip()


async def save_proposals(
    conn: asyncpg.Connection,
    tenant_id: str,
    document_id: str,
    user_id: str,
    facts: list["ExtractedFact"],
    *,
    source: str = "document",
) -> int:
    """Write extracted facts as proposals. Never as claims.

    A proposal that duplicates something the workspace already holds — same
    kind, subject and period, same statement — is dropped rather than stacked:
    re-uploading last year's accounts should not put the same eleven questions
    in front of somebody a second time.

    `source` is `document` when reading an upload and `draft` when harvesting
    something the organisation submitted. The difference is real and shows on
    the register: an uploaded certificate is evidence, whereas a bid is the
    organisation repeating a claim it made elsewhere — worth keeping, worth
    checking a little harder.
    """
    templates = {
        r["key"]: (r["statement_template"], r["label"], r["value_kind"])
        for r in await conn.fetch(
            "select key, statement_template, label, value_kind from ref_claim_kinds"
        )
    }
    written = 0
    for fact in facts:
        entry = templates.get(fact.kind)
        if entry is None:
            continue
        statement = render_statement(entry[0], entry[1], fact.subject, fact.value, entry[2])
        if not statement:
            continue
        duplicate = await conn.fetchval(
            """
            select 1 from claims
            where kind = $1 and coalesce(subject, '') = coalesce($2, '')
              and coalesce(period, '') = coalesce($3, '')
              and statement = $4 and status in ('confirmed', 'proposed')
            """,
            fact.kind,
            fact.subject,
            fact.period,
            statement,
        )
        if duplicate:
            continue
        # A document proposal's locator is a `doc_chunks` id, so it can be
        # cited later. A harvested one's is a question id on a form, which
        # names no chunk — the claim points at the submitted document instead
        # and carries no citation, the same position a register fact is in.
        chunk_id = _as_uuid(fact.locator) if source == "document" else None
        found_in = "the document" if source == "document" else "a document you submitted"
        await conn.execute(
            """
            insert into claims (tenant_id, kind, subject, period, statement, value,
                expires_on, notes, status, source, source_document_id, source_chunk_id,
                created_by)
            values ($1, $2, $3, $4, $5, $6, $7, $8, 'proposed', $9, $10, $11, $12)
            """,
            tenant_id,
            fact.kind,
            fact.subject,
            fact.period,
            statement,
            json.dumps(fact.value),
            # An insurance certificate's renewal date is most of why reading
            # the certificate was worth doing: it is what later makes lapsed
            # cover visible instead of quietly asserted.
            _parse_date(fact.expires_on),
            # The quote is the whole reason a person can decide in ten seconds
            # rather than opening the document.
            f"Found in {found_in}: “{fact.quote}”",
            source,
            document_id,
            chunk_id,
            user_id,
        )
        written += 1
    return written


def _as_uuid(raw: str) -> UUID | None:
    try:
        return UUID(raw)
    except (ValueError, TypeError):
        return None


def merge_excerpts(existing: list[VaultExcerpt], extra: list[VaultExcerpt]) -> list[VaultExcerpt]:
    """Add claim evidence to whatever retrieval found, without duplicates.

    Kept here rather than inline in the engine so the dedupe rule has one home:
    a chunk that is both retrieved for a section and cited by a claim must
    appear once, or the model sees the same id twice with different framing.
    """
    seen = {e.chunk_id for e in existing}
    return existing + [e for e in extra if e.chunk_id not in seen]
