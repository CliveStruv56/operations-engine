"""Recovery for documents an ingest job left mid-flight.

`ingest_document` marks a document failed when it is cancelled, but a process
that is killed outright (OOM, SIGKILL after the grace period, a lost host) runs
no handler at all, and the row stays at `parsing` or `embedding` with nothing
left that will ever move it. The user sees a spinner and no Reprocess button.

This sweep finds those rows by age and marks them failed. Discovery is the one
cross-tenant step, done by the owner-run `stale_document_tenants()` (migration
0030), which returns tenant ids only; the update itself runs per tenant under
RLS, like every other worker write.
"""

from datetime import UTC, datetime, timedelta

import asyncpg

from worker.db import tenant_tx

INTERRUPTED_REASON = "Processing was interrupted — reprocess the document to try again"

#: Older than any live ingest can be. The job timeout is an hour and status is
#: rewritten at each stage, so a row untouched for two is not being worked on.
STALE_AFTER = timedelta(hours=2)


async def sweep_stale_documents(ctx: dict, now: datetime | None = None) -> str:
    pool: asyncpg.Pool = ctx["pool"]
    before = (now or datetime.now(UTC)) - STALE_AFTER
    async with pool.acquire() as conn:
        rows = await conn.fetch("select out_tenant_id from stale_document_tenants($1)", before)
    failed = 0
    for row in rows:
        async with tenant_tx(pool, str(row["out_tenant_id"])) as conn:
            result = await conn.execute(
                """
                update documents
                   set status = 'failed', error = $2, updated_at = now()
                 where status in ('parsing', 'embedding') and updated_at < $1
                """,
                before,
                INTERRUPTED_REASON,
            )
            failed += int(result.split()[-1])
    return f"tenants:{len(rows)} failed:{failed}"
