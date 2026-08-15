"""arq worker: ingest_document = download → Docling parse → chunk → embed →
doc_chunks, with status transitions and usage capture.

Run: arq worker.main.WorkerSettings

DB access mirrors the API's conventions: connect as the non-owner ops_app
role and set app.current_tenant per transaction, so RLS applies to the
worker exactly as it does to request handlers.
"""

import asyncio
import contextlib
import logging
import tempfile
from datetime import date
from pathlib import Path

import asyncpg
import sentry_sdk
from arq import cron
from arq.connections import RedisSettings

from worker.answer_pdf import render_answer_pdf
from worker.blocks import estimate_tokens
from worker.chunking import chunk_blocks
from worker.claims.extract import EXTRACT_ALIAS, ScorableChunk, extract_claims
from worker.claims.facts import load_kind_specs, save_proposals
from worker.claims.harvest import harvest_claims_from_application
from worker.claims.sweep import (
    digest_recipients,
    due_claims,
    proposals_count,
    record_review_due,
    render_digest,
)
from worker.db import tenant_tx
from worker.drafts.job import draft_document
from worker.email import send_email, unsubscribe_token
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


async def _propose_claims(
    pool: asyncpg.Pool,
    tenant_id: str,
    document_id: str,
    user_id: str,
    title: str,
    virtual_key: str,
) -> None:
    """Read a just-ingested document for facts the organisation could assert.

    Three reads and one write, with the model call deliberately outside every
    transaction — it is network, and the rest of the codebase does not hold a
    tenant transaction open across one.

    Most documents return here having spent nothing: `extract_claims` scores
    the chunks against the catalogue first and gives up when a document is a
    site plan rather than a set of accounts. That is what keeps this a feature
    rather than a charge on every upload.
    """
    async with tenant_tx(pool, tenant_id) as conn:
        kinds = await load_kind_specs(conn)
        chunk_rows = await conn.fetch(
            "select id, content from doc_chunks where document_id = $1 and is_summary is not true",
            document_id,
        )
    chunks = [ScorableChunk(id=r["id"], content=r["content"]) for r in chunk_rows]

    result = await extract_claims(virtual_key, title, chunks, kinds)
    if result is None:
        return  # nothing worth reading; no call was made and nothing is billed

    async with tenant_tx(pool, tenant_id) as conn:
        # Usage first, and unconditionally: the tokens were spent whether or
        # not the model found anything, and a call that bills nothing because
        # the answer was an empty array is exactly the leak hard constraint 5
        # exists to stop (the drafting engine learned this on 4 Aug 2026).
        await conn.execute(
            """
            insert into usage_events (tenant_id, user_id, kind, model,
                                      tokens_in, tokens_out, cost_usd)
            values ($1, $2, 'extract', $3, $4, $5, $6)
            """,
            tenant_id,
            user_id,
            EXTRACT_ALIAS,
            result.tokens_in,
            result.tokens_out,
            result.cost_usd,
        )
        if result.facts:
            await save_proposals(conn, tenant_id, document_id, user_id, result.facts)


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
        except Exception:
            summary = None
        if summary is not None:
            # Its own try: a summary that was generated has already been paid
            # for, so a failure embedding it must not throw the call away
            # unmetered (hard constraint 5). The document keeps the summary
            # text and simply has no retrievable summary chunk.
            try:
                summary_vec = (await embed_texts(virtual_key, [summary.text])).vectors[0]
            except Exception:
                summary_vec = None

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
            # Billed on the summary call, not on the chunk: the tokens were
            # spent either way.
            if summary is not None:
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

        # Claim proposals — best-effort, and after the chunk transaction rather
        # than inside it, because a proposal's evidence link points at a
        # persisted `doc_chunks` row and those ids do not exist until it
        # commits. Same contract as the summary above: its absence never fails
        # ingest, and a document that proposes nothing is the normal case.
        with contextlib.suppress(Exception):
            await _propose_claims(pool, tenant_id, document_id, user_id, doc["title"], virtual_key)
        return f"ready:{len(chunks)} chunks"
    except Exception as exc:
        # Sanitized failure reason only — no file content in the row or logs.
        reason = f"{type(exc).__name__}: {str(exc)[:200]}"
        with contextlib.suppress(Exception):
            await _set_status(pool, tenant_id, document_id, "failed", reason)
        raise


async def _sweep_tenant_ids(pool: asyncpg.Pool, today: date) -> list[str]:
    """Tenants with anything due, via the owner-run discovery function
    (migration 0020) — the sweep itself then runs per tenant under RLS."""
    async with pool.acquire() as conn:
        rows = await conn.fetch("select out_tenant_id from claims_sweep_tenants($1)", today)
    return [str(r["out_tenant_id"]) for r in rows]


async def sweep_claims(ctx: dict) -> str:
    """Daily: put 'N facts need a check' on each affected tenant's activity
    feed (claims brief §14.1 step 2). Dedupe lives in `record_review_due`."""
    pool: asyncpg.Pool = ctx["pool"]
    today = date.today()
    tenant_ids = await _sweep_tenant_ids(pool, today)
    written = 0
    for tenant_id in tenant_ids:
        async with tenant_tx(pool, tenant_id) as conn:
            due = await due_claims(conn, today)
            if await record_review_due(conn, tenant_id, due):
                written += 1
    return f"due:{len(tenant_ids)} feed_rows:{written}"


async def send_claims_digest(ctx: dict) -> str:
    """Weekly: the same picture, emailed to each workspace's admins and
    owners (brief §14.1 step 3). No transport configured = a clean no-op."""
    settings = get_settings()
    if not settings.resend_api_key:
        return "email off"
    if not settings.email_unsubscribe_secret:
        # A digest whose unsubscribe link cannot be signed is not sent — same
        # rule the API enforces at boot; the worker logs instead of crashing
        # so document jobs keep running.
        logging.getLogger("worker.email").error(
            "EMAIL_UNSUBSCRIBE_SECRET is unset; skipping the claims digest"
        )
        return "no unsubscribe secret"
    pool: asyncpg.Pool = ctx["pool"]
    today = date.today()
    sent = 0
    tenant_ids = await _sweep_tenant_ids(pool, today)
    for tenant_id in tenant_ids:
        async with tenant_tx(pool, tenant_id) as conn:
            workspace = await conn.fetchval("select name from tenants where id = $1", tenant_id)
            due = await due_claims(conn, today)
            proposals = await proposals_count(conn)
            recipients = await digest_recipients(conn, tenant_id)
        if not due:
            continue
        for r in recipients:
            token = unsubscribe_token(tenant_id, r.membership_id)
            unsubscribe_url = (
                f"{settings.api_base_url.rstrip('/')}"
                f"/api/v1/email/digest?tenant={tenant_id}&membership={r.membership_id}"
                f"&token={token}"
            )
            subject, text = render_digest(
                workspace, due, proposals, settings.web_base_url, unsubscribe_url
            )
            if await send_email(r.email, subject, text):
                sent += 1
    return f"due:{len(tenant_ids)} sent:{sent}"


async def startup(ctx: dict) -> None:
    # Same trap as the API (see app/main.py configure_logging): arq configures
    # only its own `arq` logger, so without this the root logger stays at
    # WARNING and the per-call drafting timings — the numbers that decide
    # whether the Groq switch worked — are dropped before reaching a handler.
    logging.basicConfig(level=logging.INFO, format="%(levelname)s:     %(name)s %(message)s")
    logging.getLogger("worker").setLevel(logging.INFO)
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
        harvest_claims_from_application,
        render_answer_pdf,
    ]
    # The register's dates change at midnight with nobody touching anything —
    # these are the only jobs that run on a clock rather than an enqueue.
    # 06:10 UTC daily for the feed row; Monday 07:00 UTC for the email, early
    # enough to be in UK inboxes at the start of the working week.
    cron_jobs = [
        cron(sweep_claims, hour=6, minute=10),
        cron(send_claims_digest, weekday="mon", hour=7, minute=0),
    ]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
    # Drafts make ~11 sequential LLM calls. The ~3 min/call measured on 3 Aug
    # was Groq free-tier backoff, not generation, and no longer applies:
    # `drafter` now reaches Groq through OpenRouter (handoff §6j). The ceiling
    # stays generous until a real figure replaces it — `worker.drafting.
    # latency` logs elapsed per call, so measure before trusting any number
    # written here, including this sentence.
    job_timeout = 3600
    max_tries = 1  # failures surface as status=failed; users reprocess explicitly
    keep_result = 0  # frees the job id so reprocess can requeue immediately
