"""Per-tenant ceiling on LLM drafting jobs in flight (code review MOD-2).

Each draft is ~11 sequential model calls against a single arq worker. The
per-(parent, kind) duplicate guard in each drafts router stops double clicks,
but not fan-out: twenty applications × three kinds is sixty jobs queued in
seconds, the worker saturated for hours, and the tenant's gateway budget gone —
after which chat is refused for every other member. This counts the tenant's
queued and running LLM drafts across both modules and refuses past the cap.

Runs inside the request's tenant transaction, so RLS scopes the count. Two
requests racing can both pass at the boundary; the hourly rate limit
(`rate_limiter.check_draft`) bounds what that can add.
"""

import asyncpg

from app.config import get_settings
from app.errors import ApiError

# Same window as the drafts routers' duplicate guard: an older queued/running
# row was stranded by a killed worker and must not hold a slot forever.
IN_FLIGHT_WINDOW = "2 hours"

# The one-page cards render rows with no model call — quick, and not what the
# cap protects, so they neither count nor get refused.
_NON_LLM_KINDS = ("health_card", "impact_card")


async def ensure_draft_capacity(conn: asyncpg.Connection) -> None:
    in_flight = await conn.fetchval(
        f"""
        select (select count(*) from proj_draft_jobs
                 where status in ('queued', 'running') and kind <> all($1::text[])
                   and created_at > now() - interval '{IN_FLIGHT_WINDOW}')
             + (select count(*) from grant_draft_jobs
                 where status in ('queued', 'running') and kind <> all($1::text[])
                   and created_at > now() - interval '{IN_FLIGHT_WINDOW}')
        """,
        list(_NON_LLM_KINDS),
    )
    limit = get_settings().draft_max_in_flight_per_tenant
    if in_flight >= limit:
        raise ApiError(
            429,
            "drafts_busy",
            f"{limit} drafts are already being written for this workspace — "
            "try again when one lands.",
        )
