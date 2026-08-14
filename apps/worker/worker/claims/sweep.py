"""The claims sweep: which facts have gone off, told to people who aren't looking.

Claims brief §14.1 steps 2–3. Two consumers share the queries here: the daily
cron writes a `claims.review_due` audit row so the tenant activity feed
carries it, and the weekly cron emails the same picture to the workspace's
admins. Everything DB-touching stays asyncpg + pydantic so the API test suite
can exercise it against a real migrated Postgres (ASSUMPTIONS #13) — the cron
wiring in `worker/main.py` stays thin.

The rule that must hold (brief §14.1): count only claims that are actually a
problem, never "you have eighty facts". Both consumers trigger on
needs-attention claims only; proposals ride along as a footnote count.
"""

from datetime import date

import asyncpg
from pydantic import BaseModel

#: The same two predicates as the API's `claims_summary` — a digest that
#: disagrees with the badge it echoes is worse than no digest.
_DUE_SQL = """
    select c.statement, c.next_review, c.expires_on,
           (c.expires_on is not null and c.expires_on < $1) as lapsed
    from claims c
    where c.status = 'confirmed'
      and ((c.next_review is not null and c.next_review <= $1)
           or (c.expires_on is not null and c.expires_on < $1))
    order by lapsed desc, coalesce(c.expires_on, c.next_review), c.statement
"""

#: One feed row per tenant per week, not per day: the sweep runs daily so a
#: fact going off surfaces within a day, but a standing problem must not
#: drown the feed's fifteen slots in identical rows.
_FEED_DEDUPE_DAYS = 7


class DueClaim(BaseModel):
    statement: str
    next_review: date | None
    expires_on: date | None
    #: True = the fact is now false (expired), not merely unchecked.
    lapsed: bool


class Recipient(BaseModel):
    membership_id: str
    email: str


async def due_claims(conn: asyncpg.Connection, today: date) -> list[DueClaim]:
    rows = await conn.fetch(_DUE_SQL, today)
    return [
        DueClaim(
            statement=r["statement"],
            next_review=r["next_review"],
            expires_on=r["expires_on"],
            lapsed=r["lapsed"],
        )
        for r in rows
    ]


async def proposals_count(conn: asyncpg.Connection) -> int:
    return await conn.fetchval("select count(*) from claims where status = 'proposed'") or 0


async def record_review_due(conn: asyncpg.Connection, tenant_id: str, due: list[DueClaim]) -> bool:
    """Write the feed row, unless one landed within the dedupe window.

    `user_id` stays null — nobody did this, and the feed renders a null actor
    as the platform rather than pinning a member to it.
    """
    if not due:
        return False
    recent = await conn.fetchval(
        """
        select 1 from audit_log
        where tenant_id = $1 and action = 'claims.review_due'
          and created_at > now() - make_interval(days => $2)
        """,
        tenant_id,
        _FEED_DEDUPE_DAYS,
    )
    if recent:
        return False
    lapsed = sum(1 for c in due if c.lapsed)
    # tenant_id twice: the uuid column and the text target_id would otherwise
    # force one parameter into two types, which asyncpg refuses to deduce.
    await conn.execute(
        """
        insert into audit_log (tenant_id, user_id, action, target_type, target_id, meta)
        values ($1, null, 'claims.review_due', 'claims', $2,
                jsonb_build_object('needs_attention', $3::int, 'lapsed', $4::int))
        """,
        tenant_id,
        str(tenant_id),
        len(due),
        lapsed,
    )
    return True


async def digest_recipients(conn: asyncpg.Connection, tenant_id: str) -> list[Recipient]:
    """Admins and owners with an email who have not opted out.

    Members get the in-app badge; the people who can actually re-verify a
    fact or reassign its owner are the ones worth interrupting by email.
    """
    rows = await conn.fetch(
        """
        select id, email from memberships
        where tenant_id = $1 and role in ('admin', 'owner')
          and email is not null and not digest_opt_out
        order by created_at
        """,
        tenant_id,
    )
    return [Recipient(membership_id=str(r["id"]), email=r["email"]) for r in rows]


def render_digest(
    workspace: str,
    due: list[DueClaim],
    proposals: int,
    base_url: str,
    unsubscribe_url: str,
    max_lines: int = 10,
) -> tuple[str, str]:
    """(subject, text). Pure, so the worker suite can test it without a DB.

    Worst first — lapsed facts (now false) before past-review ones (merely
    unchecked) — and never the full register: the email's job is to get
    somebody to the screen, not to be the screen.
    """
    n = len(due)
    subject = f"{n} fact{'s' if n != 1 else ''} need{'s' if n == 1 else ''} a check — {workspace}"
    lines = []
    for claim in due[:max_lines]:
        # day-month by hand: %-d is Linux-only and %#d is Windows-only.
        if claim.lapsed and claim.expires_on:
            lines.append(
                f"- Lapsed {claim.expires_on.day} {claim.expires_on:%b}: {claim.statement}"
            )
        elif claim.next_review:
            lines.append(
                f"- Past review ({claim.next_review.day} {claim.next_review:%b}):"
                f" {claim.statement}"
            )
        else:
            lines.append(f"- {claim.statement}")
    if n > max_lines:
        lines.append(f"…and {n - max_lines} more.")
    footer = f"\n\nThere are also {proposals} facts waiting to be checked." if proposals else ""
    text = (
        f"These facts in {workspace}'s register can no longer be relied on"
        " until somebody checks them:\n\n"
        + "\n".join(lines)
        + footer
        + f"\n\nOpen the register: {base_url}/app/claims"
        + f"\n\nStop these emails: {unsubscribe_url}"
    )
    return subject, text
