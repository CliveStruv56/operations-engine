"""Reading and writing the claims register.

Nothing here talks to a register or to a model; `registers.py` does the first
and the worker does the second. This is the layer that decides what a claim
means, and it holds three rules the whole feature rests on.

**Staleness is derived, never stored.** `stale` and `expired` are computed
against a `today` passed in, the same contract as the funder catalogue and the
question sets.

**Verification is an act somebody performs.** Exactly one code path may move
`last_verified` and `next_review` forward, and it is the one a person triggers.
Nothing imported, extracted or inferred sets them.

**Nothing is asserted without a person.** Imports write `proposed`. Confirming
is a separate act, and it is the act that supersedes whatever the workspace
previously asserted.
"""

import json
from datetime import date, timedelta
from typing import Any
from uuid import UUID

import asyncpg

from app.claims.registers import RegisterFacts
from app.claims.schemas import ClaimIn, ClaimKindOut, ClaimOut, ClaimPatch
from app.errors import ApiError

#: Fallback review cycle for a kind that names none and whose fact carries no
#: filing date or expiry. Matches the question-set catalogue deliberately: an
#: arbitrary cycle should at least be the same arbitrary cycle everywhere.
DEFAULT_REVIEW_DAYS = 90

#: One list, two renderings — the join needs a table alias and `returning` must
#: not have one. Written once so they cannot drift.
_FIELDS = (
    "id",
    "kind",
    "subject",
    "period",
    "statement",
    "value",
    "unit",
    "as_of",
    "expires_on",
    "status",
    "source",
    "source_ref",
    "source_document_id",
    "source_chunk_id",
    "owner_membership_id",
    "last_verified",
    "next_review",
    "notes",
)
_RETURNING = ", ".join(_FIELDS)
_SELECT = ", ".join(f"c.{f}" for f in _FIELDS)


def _loads(value: Any) -> Any:
    # asyncpg returns jsonb as str (no codec registered) — decode at the edge.
    return json.loads(value) if isinstance(value, str) else value


def _dumps(value: Any) -> str | None:
    """Encode a claim value for jsonb.

    Registers hand back real `date` objects for incorporation and year-end
    facts, and `json.dumps` refuses them. ISO strings round-trip through jsonb
    and read correctly on a form, so that is what a date value becomes.
    """
    if value is None:
        return None
    return json.dumps(value, default=lambda o: o.isoformat() if isinstance(o, date) else str(o))


async def load_kinds(conn: asyncpg.Connection) -> dict[str, ClaimKindOut]:
    """The fact-type catalogue, keyed by kind.

    Tens of rows, read on nearly every claims request, so it is fetched whole
    rather than joined per claim.
    """
    rows = await conn.fetch(
        """
        select key, label, category, value_kind, unit, cardinality, periodic,
               review_days, statement_template, question_hints,
               register as register_key, notes
        from ref_claim_kinds order by category, label
        """
    )
    return {r["key"]: ClaimKindOut(**dict(r)) for r in rows}


def _row_out(
    row: asyncpg.Record,
    kinds: dict[str, ClaimKindOut],
    today: date,
    *,
    document_title: str | None = None,
) -> ClaimOut:
    kind = kinds.get(row["kind"])
    return ClaimOut(
        id=row["id"],
        kind=row["kind"],
        # A kind retired from the catalogue leaves its claims readable rather
        # than breaking the list — the whole reason `kind` is not an FK.
        label=kind.label if kind else row["kind"],
        category=kind.category if kind else "identity",
        subject=row["subject"],
        period=row["period"],
        statement=row["statement"],
        value=_loads(row["value"]),
        unit=row["unit"],
        as_of=row["as_of"],
        expires_on=row["expires_on"],
        status=row["status"],
        source=row["source"],
        source_ref=row["source_ref"],
        source_document_id=row["source_document_id"],
        source_document_title=document_title,
        source_chunk_id=row["source_chunk_id"],
        owner_membership_id=row["owner_membership_id"],
        last_verified=row["last_verified"],
        next_review=row["next_review"],
        notes=row["notes"],
        stale=row["next_review"] is not None and row["next_review"] <= today,
        expired=row["expires_on"] is not None and row["expires_on"] < today,
    )


async def list_claims(
    conn: asyncpg.Connection, today: date, *, status: str | None = None
) -> list[ClaimOut]:
    """Every claim this workspace holds, proposals included.

    Proposals are returned alongside rather than behind a separate endpoint:
    the register screen leads with "here are eleven things we found, tick the
    right ones", and that is one list with two states, not two screens.
    """
    kinds = await load_kinds(conn)
    rows = await conn.fetch(
        f"""
        select {_SELECT}, d.title as source_document_title
        from claims c left join documents d on d.id = c.source_document_id
        {"where c.status = $1" if status else "where c.status <> 'superseded'"}
        order by c.status <> 'proposed', c.kind,
                 coalesce(c.subject, ''), coalesce(c.period, '')
        """,
        *([status] if status else []),
    )
    return [_row_out(r, kinds, today, document_title=r["source_document_title"]) for r in rows]


async def get_claim(conn: asyncpg.Connection, claim_id: UUID, today: date) -> ClaimOut | None:
    kinds = await load_kinds(conn)
    row = await conn.fetchrow(
        f"""
        select {_SELECT}, d.title as source_document_title
        from claims c left join documents d on d.id = c.source_document_id
        where c.id = $1
        """,
        claim_id,
    )
    if row is None:
        return None
    return _row_out(row, kinds, today, document_title=row["source_document_title"])


def next_review_for(kind: ClaimKindOut | None, today: date, expires_on: date | None) -> date:
    """When a fact of this type should next be looked at.

    Expiry wins where there is one: an accreditation or an insurance policy is
    current until its certificate lapses, and any other cycle would either nag
    early or — much worse — go quiet after it has lapsed.
    """
    if expires_on is not None:
        return expires_on
    days = (kind.review_days if kind else None) or DEFAULT_REVIEW_DAYS
    return today + timedelta(days=days)


async def _check_owned_document(conn: asyncpg.Connection, document_id: UUID | None) -> None:
    """Postgres validates foreign keys with RLS bypassed.

    So the constraint on `source_document_id` would happily accept another
    workspace's document id and silently confirm that it exists. The only
    check that binds is this one, inside the tenant's own RLS context.
    """
    if document_id is None:
        return
    if await conn.fetchval("select 1 from documents where id = $1", document_id) is None:
        raise ApiError(404, "not_found", "That document is not in this workspace's vault")


async def _supersede_existing(
    conn: asyncpg.Connection, kind: str, subject: str | None, period: str | None
) -> None:
    """Retire whatever this workspace currently asserts for the same identity.

    Not a delete: the superseded row is what answers "what did we tell the
    funder in January", and the partial unique index binds confirmed rows only,
    so the old one sits alongside without colliding.
    """
    await conn.execute(
        """
        update claims set status = 'superseded', updated_at = now()
        where status = 'confirmed' and kind = $1
          and coalesce(subject, '') = coalesce($2, '')
          and coalesce(period, '') = coalesce($3, '')
        """,
        kind,
        subject,
        period,
    )


async def _write_revision(
    conn: asyncpg.Connection, tenant_id: UUID, row: asyncpg.Record, user_id: UUID, note: str
) -> None:
    await conn.execute(
        """
        insert into claim_revisions (tenant_id, claim_id, statement, value, as_of,
            source, source_ref, source_document_id, changed_by, note)
        values ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
        """,
        tenant_id,
        row["id"],
        row["statement"],
        row["value"],
        row["as_of"],
        row["source"],
        row["source_ref"],
        row["source_document_id"],
        user_id,
        note,
    )


async def create_claim(
    conn: asyncpg.Connection,
    tenant_id: UUID,
    user_id: UUID,
    body: ClaimIn,
    today: date,
) -> ClaimOut:
    """Write one claim somebody typed.

    Typed claims are confirmed on arrival — the person is asserting the fact,
    and asking them to type it and then tick it would be theatre. Machine-found
    claims do not come through here; they arrive `proposed` via the importer.
    """
    kinds = await load_kinds(conn)
    kind = kinds.get(body.kind)
    if kind is None:
        raise ApiError(
            422, "unknown_claim_kind", f"“{body.kind}” is not a kind of fact we recognise"
        )
    await _check_owned_document(conn, body.source_document_id)
    if kind.cardinality == "single" and body.subject is not None:
        raise ApiError(
            422, "unexpected_subject", f"“{kind.label}” is a single fact, not a list of them"
        )

    await _supersede_existing(conn, body.kind, body.subject, body.period)
    row = await conn.fetchrow(
        f"""
        insert into claims (tenant_id, kind, subject, period, statement, value, unit, as_of,
            expires_on, status, source, source_document_id, source_chunk_id,
            last_verified, next_review, notes, created_by)
        values ($1, $2, $3, $4, $5, $6, $7, $8, $9, 'confirmed', 'typed', $10, $11,
                $12, $13, $14, $15)
        returning {_RETURNING}
        """,
        tenant_id,
        body.kind,
        body.subject,
        body.period,
        body.statement,
        _dumps(body.value),
        body.unit or kind.unit,
        body.as_of,
        body.expires_on,
        body.source_document_id,
        body.source_chunk_id,
        today,
        next_review_for(kind, today, body.expires_on),
        body.notes,
        user_id,
    )
    await _write_revision(conn, tenant_id, row, user_id, "created")
    return _row_out(row, kinds, today)


async def update_claim(
    conn: asyncpg.Connection,
    tenant_id: UUID,
    user_id: UUID,
    claim_id: UUID,
    body: ClaimPatch,
    today: date,
) -> ClaimOut:
    existing = await conn.fetchrow(f"select {_RETURNING} from claims where id = $1", claim_id)
    if existing is None:
        raise ApiError(404, "not_found", "Claim not found")

    kinds = await load_kinds(conn)
    kind = kinds.get(existing["kind"])
    sets: list[str] = []
    values: list[Any] = [claim_id]

    def add(column: str, value: Any) -> None:
        values.append(value)
        sets.append(f"{column} = ${len(values)}")

    for column in ("subject", "period", "statement", "unit", "as_of", "expires_on", "notes"):
        value = getattr(body, column)
        if value is not None:
            add(column, value)
    if body.value is not None:
        add("value", _dumps(body.value))
    if body.owner_membership_id is not None:
        add("owner_membership_id", body.owner_membership_id)

    expires_on = body.expires_on or existing["expires_on"]
    if body.status == "confirmed":
        # Confirming a proposal is the moment it becomes something this
        # workspace asserts, so it is also the moment whatever it replaces
        # stops being one.
        await _supersede_existing(
            conn,
            existing["kind"],
            body.subject if body.subject is not None else existing["subject"],
            body.period if body.period is not None else existing["period"],
        )
        add("status", "confirmed")
        add("last_verified", today)
        add("next_review", next_review_for(kind, today, expires_on))
    elif body.status == "rejected":
        add("status", "rejected")
    elif body.verified:
        # Verification is an act somebody performs. This is where they perform
        # it, so it is the one place these dates may move forward.
        add("last_verified", today)
        add("next_review", next_review_for(kind, today, expires_on))

    if not sets:
        raise ApiError(422, "nothing_to_update", "No changes were sent")

    row = await conn.fetchrow(
        f"update claims set {', '.join(sets)}, updated_at = now()"
        f" where id = $1 returning {_RETURNING}",
        *values,
    )
    # A revision records a change of value, never a re-verification: "still
    # true" and "now different" are the two things this table exists to tell
    # apart.
    if (body.value is not None or body.statement is not None) and row["status"] == "confirmed":
        await _write_revision(conn, tenant_id, row, user_id, "edited")
    elif body.status == "confirmed":
        await _write_revision(conn, tenant_id, row, user_id, "confirmed")
    return _row_out(row, kinds, today)


async def delete_claim(conn: asyncpg.Connection, claim_id: UUID) -> None:
    deleted = await conn.fetchval("delete from claims where id = $1 returning id", claim_id)
    if deleted is None:
        raise ApiError(404, "not_found", "Claim not found")


async def import_register_facts(
    conn: asyncpg.Connection,
    tenant_id: UUID,
    user_id: UUID,
    found: RegisterFacts,
    today: date,
) -> tuple[list[ClaimOut], int, list[str]]:
    """Turn what a register said into proposals.

    Returns the proposals written, how many facts the workspace already agreed
    with, and any kinds the catalogue does not know. That last list is a
    development signal rather than a user-facing one: a register field we hold
    no kind for is a fixture gap, and it should be visible rather than dropped.

    Re-running is safe and useful. A fact matching what the workspace already
    confirmed counts as unchanged and is not re-proposed; a fact that differs
    is proposed again, which is exactly how a changed income figure surfaces.
    """
    kinds = await load_kinds(conn)
    proposed: list[ClaimOut] = []
    unchanged = 0
    unknown: list[str] = []

    for fact in found.facts:
        kind = kinds.get(fact.kind)
        if kind is None:
            if fact.kind not in unknown:
                unknown.append(fact.kind)
            continue

        statement = render_statement(kind, fact.subject, fact.value)
        # Both states have to be read, not whichever one the planner happens to
        # return first. A workspace can hold a confirmed claim AND an unanswered
        # proposal for the same fact at once — that is the normal state between
        # an import and somebody sitting down to tick it — and looking at only
        # one of them either stacks a duplicate proposal on every re-run or
        # misses a genuine change.
        existing = await conn.fetch(
            """
            select id, statement, status from claims
            where kind = $1 and coalesce(subject, '') = coalesce($2, '')
              and coalesce(period, '') = coalesce($3, '')
              and status in ('confirmed', 'proposed')
            """,
            fact.kind,
            fact.subject,
            fact.period,
        )
        if any(r["statement"] == statement for r in existing):
            unchanged += 1
            continue
        for stale_proposal in (r for r in existing if r["status"] == "proposed"):
            # Replace the superseded proposal rather than stacking a second
            # one: two live proposals for one fact is a choice nobody can make.
            await conn.execute("delete from claims where id = $1", stale_proposal["id"])

        row = await conn.fetchrow(
            f"""
            insert into claims (tenant_id, kind, subject, period, statement, value, unit,
                as_of, status, source, source_ref, next_review, created_by)
            values ($1, $2, $3, $4, $5, $6, $7, $8, 'proposed', 'register', $9, $10, $11)
            returning {_RETURNING}
            """,
            tenant_id,
            fact.kind,
            fact.subject,
            fact.period,
            statement,
            _dumps(fact.value),
            kind.unit,
            fact.as_of,
            found.source_url,
            # The register's own filing calendar where it gave us one. That is
            # what makes "due for review" mean the register has probably
            # changed, rather than that ninety days have passed.
            fact.review_on,
            user_id,
        )
        proposed.append(_row_out(row, kinds, today))

    return proposed, unchanged, unknown


def render_statement(kind: ClaimKindOut, subject: str | None, value: Any) -> str:
    """The sentence a person reads and a prompt is handed.

    Templates are deliberately simple. A template wanting something the fact
    does not carry falls back to a plain label-and-value line, because a
    statement reading "The organisation holds {subject}" is worse than a dull
    one that is true.
    """
    rendered = format_value(kind, value)
    try:
        statement = kind.statement_template.format(value=rendered, subject=subject or kind.label)
    except (KeyError, IndexError):
        statement = f"{kind.label}: {rendered}" if rendered else kind.label
    return statement.strip()


def format_value(kind: ClaimKindOut, value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return ", ".join(str(v) for v in value)
    if isinstance(value, dict):
        # An officer record carries role and appointment date; the statement
        # template names the person, so the dict is detail, not the sentence.
        return ""
    if kind.value_kind == "money" and isinstance(value, (int, float)):
        return f"£{value:,.0f}"
    if kind.value_kind == "number" and isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)
