"""The draft_document arq job: gather → retrieve → outline → sections →
assemble → upload → register, with the job row tracking every transition.

Registration is the only step that mutates the registry, and it runs last —
a failure anywhere (including the cost guard) marks the job failed and
leaves no orphaned rows (PRD §5 cost guard). Network calls (LiteLLM, S3)
always happen outside tenant transactions."""

import asyncio
import contextlib
import json
from datetime import date
from uuid import UUID

import asyncpg

from worker.db import tenant_tx as _tenant_tx
from worker.drafts.assemble import assemble_docx
from worker.drafts.context import gather
from worker.drafts.llm import DraftBudgetExceeded, LlmLedger, chat
from worker.drafts.prompts import SKELETONS, outline_prompt, parse_outline, section_prompt
from worker.drafts.register import register_draft
from worker.drafts.retrieval import queries_for, retrieve_excerpts, scope_weights
from worker.embed import embed_texts
from worker.secrets import decrypt_llm_key
from worker.storage import DOCX_MIME, upload_bytes


async def _mark_failed(pool: asyncpg.Pool, tenant_id: str, job_id: str, error: str) -> None:
    async with _tenant_tx(pool, tenant_id) as conn:
        await conn.execute(
            "update proj_draft_jobs set status = 'failed', error = $2, updated_at = now()"
            " where id = $1",
            UUID(job_id),
            error[:500],
        )


async def draft_document(
    ctx: dict, tenant_id: str, project_id: str, job_id: str, user_id: str
) -> str:
    pool: asyncpg.Pool = ctx["pool"]
    loop = asyncio.get_running_loop()

    async with _tenant_tx(pool, tenant_id) as conn:
        job = await conn.fetchrow("select * from proj_draft_jobs where id = $1", UUID(job_id))
        if job is None:
            return "gone"  # deleted between enqueue and run
        kind = job["kind"]
        params = json.loads(job["params"])
        virtual_key = decrypt_llm_key(
            await conn.fetchval(
                "select litellm_key_encrypted from tenants where id = $1", tenant_id
            )
        )
        await conn.execute(
            "update proj_draft_jobs set status = 'running', updated_at = now() where id = $1",
            UUID(job_id),
        )

    try:
        if not virtual_key:
            raise RuntimeError("No model key provisioned for this workspace")

        async with _tenant_tx(pool, tenant_id) as conn:
            pack = await gather(conn, UUID(project_id), kind, params, date.today())

        ledger = LlmLedger()
        queries = queries_for(kind, pack.project.site_address or pack.project.name)
        if queries:
            embedded = await embed_texts(virtual_key, queries)  # network — outside tx
            ledger.embed_tokens = embedded.tokens
            ledger.embed_cost_usd = embedded.cost_usd
            async with _tenant_tx(pool, tenant_id) as conn:
                weights = await scope_weights(conn, UUID(project_id))
                pack.excerpts = await retrieve_excerpts(conn, queries, embedded.vectors, weights)

        system, user = outline_prompt(pack)
        outline = parse_outline(await chat(ledger, virtual_key, "drafter", system, user))

        sections = []
        for section in SKELETONS[kind]:
            system, user = section_prompt(pack, section, outline.get(section.key, []))
            text = await chat(ledger, virtual_key, section.alias, system, user)
            sections.append((section, text))

        draft = assemble_docx(pack, sections, date.today())
        file_key = f"{tenant_id}/projects/{project_id}/drafts/{job_id}.docx"
        await loop.run_in_executor(None, upload_bytes, file_key, draft.data, DOCX_MIME)

        async with _tenant_tx(pool, tenant_id) as conn:
            doc_id = await register_draft(
                conn,
                tenant_id=tenant_id,
                project_id=project_id,
                user_id=user_id,
                job_id=job_id,
                pack=pack,
                file_key=file_key,
                ledger=ledger,
                draft=draft,
            )
        return f"succeeded:{doc_id}"
    except DraftBudgetExceeded as exc:
        with contextlib.suppress(Exception):
            await _mark_failed(pool, tenant_id, job_id, str(exc))
        raise
    except ValueError as exc:
        # Gather-level validation (missing project/funding source) — the
        # message is already user-safe.
        with contextlib.suppress(Exception):
            await _mark_failed(pool, tenant_id, job_id, str(exc))
        raise
    except BaseException as exc:
        # BaseException on purpose: arq's job_timeout cancellation raises
        # CancelledError (a BaseException since 3.8) — without this a
        # timed-out job leaves a 'running' row the UI polls forever.
        reason = (
            "Draft generation was interrupted — try again"
            if isinstance(exc, asyncio.CancelledError)
            # Sanitized failure reason only — no prompt or document content.
            else f"Draft generation failed ({type(exc).__name__}: {str(exc)[:160]})"
        )
        with contextlib.suppress(BaseException):
            await _mark_failed(pool, tenant_id, job_id, reason)
        raise
