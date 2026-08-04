"""Cost telemetry for a drafting job.

CLAUDE.md hard constraint 5 is "cost telemetry on every LLM call", so these
rows belong to the engine, not to a module: the engine is the only thing that
sees *every* terminal outcome. They used to be written inside each module's
`register_draft()`, which runs only on success — a job that died on its ninth
model call billed the tenant nothing (observed live, 4 Aug 2026: a provider
429 after real calls recorded `llm_calls 0, cost_usd 0`).

Keeping it here also means module #4 cannot forget it, the same reason the
module manifest and `test_every_module_table_has_rls` exist.
"""

from uuid import UUID

import asyncpg

from worker.drafting.llm import LlmLedger


async def write_usage(
    conn: asyncpg.Connection, tenant_id: str, user_id: str, ledger: LlmLedger
) -> None:
    """One `usage_events` row per model call, plus one for the embedding call.

    `usage_events` is tenant-scoped, so the caller must already be inside a
    tenant transaction. Safe on an empty ledger — a job that failed before its
    first call writes nothing rather than a zero row.
    """
    if ledger.calls:
        await conn.executemany(
            """
            insert into usage_events (tenant_id, user_id, kind, model,
                                      tokens_in, tokens_out, cost_usd)
            values ($1, $2, 'draft', $3, $4, $5, $6)
            """,
            [
                (UUID(tenant_id), UUID(user_id), c.alias, c.tokens_in, c.tokens_out, c.cost_usd)
                for c in ledger.calls
            ],
        )
    if ledger.embed_tokens:
        await conn.execute(
            """
            insert into usage_events (tenant_id, user_id, kind, model, tokens_in, cost_usd)
            values ($1, $2, 'embed', 'embedder', $3, $4)
            """,
            UUID(tenant_id),
            UUID(user_id),
            ledger.embed_tokens,
            ledger.embed_cost_usd,
        )
