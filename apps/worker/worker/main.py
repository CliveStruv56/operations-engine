"""arq worker: ingest_document = download → Docling parse → chunk → embed →
doc_chunks, with status transitions and usage capture.

Run: arq worker.main.WorkerSettings

DB access mirrors the API's conventions: connect as the non-owner ops_app
role and set app.current_tenant per transaction, so RLS applies to the
worker exactly as it does to request handlers.
"""

import asyncio
import contextlib
import tempfile
from pathlib import Path

import asyncpg
import sentry_sdk
from arq.connections import RedisSettings

from worker.blocks import estimate_tokens
from worker.chunking import chunk_blocks
from worker.db import tenant_tx
from worker.drafts.job import draft_document
from worker.embed import embed_texts
from worker.grants.impact_card import generate_impact_card
from worker.grants.job import grant_draft_document
from worker.health_card import generate_health_card
from worker.parsing import parse_file
from worker.secrets import decrypt_llm_key
from worker.settings import get_settings
from worker.storage import download_file
from worker.summarize import summarize_document

PARSE_TIMEOUT_S = 600


async def _set_status(
    pool: asyncpg.Pool, tenant_id: str, document_id: str, status: str, error: str | None = None
) -> None:
    async with tenant_tx(pool, tenant_id) as conn:
        await conn.execute(
            "update documents set status = $2, error = $3, updated_at = now() where id = $1",
            document_id,
            status,
            error,
        )


async def ingest_document(ctx: dict, tenant_id: str, document_id: str, user_id: str) -> str:
    pool: asyncpg.Pool = ctx["pool"]
    loop = asyncio.get_running_loop()

    async with tenant_tx(pool, tenant_id) as conn:
        doc = await conn.fetchrow("select * from documents where id = $1", document_id)
        if doc is None:
            return "gone"  # deleted between enqueue and run
        virtual_key = decrypt_llm_key(
            await conn.fetchval(
                "select litellm_key_encrypted from tenants where id = $1", tenant_id
            )
        )

    try:
        await _set_status(pool, tenant_id, document_id, "parsing")
        with tempfile.TemporaryDirectory() as tmp:
            local = str(Path(tmp) / Path(doc["storage_key"]).name)
            await loop.run_in_executor(None, download_file, doc["storage_key"], local)
            blocks = await asyncio.wait_for(
                loop.run_in_executor(None, parse_file, local), timeout=PARSE_TIMEOUT_S
            )
        chunks = chunk_blocks(
            blocks,
            target_tokens=get_settings().chunk_target_tokens,
            overlap_ratio=get_settings().chunk_overlap_ratio,
        )
        if not chunks:
            raise ValueError("No readable content found in the file")

        await _set_status(pool, tenant_id, document_id, "embedding")
        if not virtual_key:
            raise RuntimeError("No model key provisioned for this workspace")
        embedded = await embed_texts(virtual_key, [c.content for c in chunks])

        # Summary (Slice 4.5) — best-effort: its absence never fails ingest.
        summary = None
        summary_vec: list[float] | None = None
        try:
            summary = await summarize_document(
                virtual_key, doc["title"], [c.content for c in chunks]
            )
            summary_vec = (await embed_texts(virtual_key, [summary.text])).vectors[0]
        except Exception:
            summary = None

        async with tenant_tx(pool, tenant_id) as conn:
            await conn.execute("delete from doc_chunks where document_id = $1", document_id)
            await conn.executemany(
                """
                insert into doc_chunks (tenant_id, document_id, content, heading_path,
                                        page_start, page_end, token_count, embedding)
                values ($1, $2, $3, $4, $5, $6, $7, $8::vector)
                """,
                [
                    (
                        tenant_id,
                        document_id,
                        c.content,
                        c.heading_path,
                        c.page_start,
                        c.page_end,
                        c.token_count,
                        "[" + ",".join(f"{x:.7g}" for x in vec) + "]",
                    )
                    for c, vec in zip(chunks, embedded.vectors, strict=True)
                ],
            )
            await conn.execute(
                """
                insert into usage_events (tenant_id, user_id, kind, model, tokens_in, cost_usd)
                values ($1, $2, 'parse', 'docling', $3, 0),
                       ($1, $2, 'embed', 'embedder', $4, $5)
                """,
                tenant_id,
                user_id,
                sum(estimate_tokens(b.text) for b in blocks),
                embedded.tokens,
                embedded.cost_usd,
            )
            if summary is not None and summary_vec is not None:
                await conn.execute(
                    """
                    insert into doc_chunks (tenant_id, document_id, content,
                                            is_summary, token_count, embedding)
                    values ($1, $2, $3, true, $4, $5::vector)
                    """,
                    tenant_id,
                    document_id,
                    f"Summary of the document:\n\n{summary.text}",
                    estimate_tokens(summary.text),
                    "[" + ",".join(f"{x:.7g}" for x in summary_vec) + "]",
                )
                await conn.execute(
                    """
                    insert into usage_events (tenant_id, user_id, kind, model,
                                              tokens_in, tokens_out, cost_usd)
                    values ($1, $2, 'summary', 'drafter', $3, $4, $5)
                    """,
                    tenant_id,
                    user_id,
                    summary.tokens_in,
                    summary.tokens_out,
                    summary.cost_usd,
                )
            await conn.execute(
                "update documents set status = 'ready', error = null, summary = $2,"
                " updated_at = now() where id = $1",
                document_id,
                summary.text if summary else None,
            )
        return f"ready:{len(chunks)} chunks"
    except Exception as exc:
        # Sanitized failure reason only — no file content in the row or logs.
        reason = f"{type(exc).__name__}: {str(exc)[:200]}"
        with contextlib.suppress(Exception):
            await _set_status(pool, tenant_id, document_id, "failed", reason)
        raise


async def startup(ctx: dict) -> None:
    settings = get_settings()
    if settings.sentry_dsn:
        sentry_sdk.init(
            dsn=settings.sentry_dsn, environment=settings.environment, send_default_pii=False
        )
    ctx["pool"] = await asyncpg.create_pool(settings.app_database_url, min_size=1, max_size=4)


async def shutdown(ctx: dict) -> None:
    pool = ctx.get("pool")  # absent when startup itself failed
    if pool is not None:
        await pool.close()


class WorkerSettings:
    functions = [
        ingest_document,
        draft_document,
        generate_health_card,
        grant_draft_document,
        generate_impact_card,
    ]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
    # Drafts make ~11 sequential LLM calls; live proof measured ~3 min/call
    # on the drafter alias, so a full draft can run past 30 minutes.
    job_timeout = 3600
    max_tries = 1  # failures surface as status=failed; users reprocess explicitly
    keep_result = 0  # frees the job id so reprocess can requeue immediately
