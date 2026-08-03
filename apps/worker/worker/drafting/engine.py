"""The shared drafting job: gather → retrieve → outline → sections →
assemble → upload → register, with the job row tracking every transition.

Registration is the only step that mutates a module's registry, and it runs
last — a failure anywhere (including the cost guard) marks the job failed and
leaves no orphaned rows. Network calls (LiteLLM, S3) always happen outside
tenant transactions.

A vertical supplies a `DraftModule`: where its job rows live, how to gather
its facts, what its documents look like, and how to register the result.
Everything else here is the same work for every module.
"""

import asyncio
import contextlib
import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import date
from uuid import UUID

import asyncpg

from worker.db import tenant_tx as _tenant_tx
from worker.drafting.assemble import AssembledDraft, TableRenderer, assemble_docx
from worker.drafting.llm import DraftBudgetExceeded, LlmLedger, chat
from worker.drafting.pack import DraftPackBase
from worker.drafting.prompts import outline_prompt, parse_outline, section_prompt
from worker.drafting.retrieval import retrieve_excerpts
from worker.drafting.sections import Section
from worker.embed import embed_texts
from worker.secrets import decrypt_llm_key
from worker.storage import DOCX_MIME, upload_bytes


@dataclass(frozen=True)
class DraftModule:
    """Everything the pipeline needs that differs between verticals."""

    #: Module slug, used in the storage path: tenants/<t>/<slug>/<subject>/drafts/.
    storage_segment: str
    #: The module's own job table (`proj_draft_jobs`, `grant_draft_jobs`, …).
    job_table: str
    #: System prompt — build it with `prompts.grounding_prompt(domain)`.
    system_prompt: str
    skeletons: dict[str, list[Section]]
    #: Named data tables a section can render from the pack's own records.
    tables: dict[str, TableRenderer]
    #: (conn, subject_id, kind, params, today) -> pack, inside a tenant tx.
    gather: Callable[..., Awaitable[DraftPackBase]]
    #: (kind, pack) -> retrieval queries; empty means the kind is not
    #: vault-grounded and no embedding call is made at all.
    queries_for: Callable[[str, DraftPackBase], list[str]]
    #: (conn, subject_id) -> per-document fusion boosts.
    scope_weights: Callable[..., Awaitable[dict[UUID, float]]]
    #: Writes the registry row, usage events, audit row and job completion.
    register: Callable[..., Awaitable[UUID]]


async def _mark_failed(
    pool: asyncpg.Pool, module: DraftModule, tenant_id: str, job_id: str, error: str
) -> None:
    async with _tenant_tx(pool, tenant_id) as conn:
        # Table name comes from the frozen module definition, never a request.
        await conn.execute(
            f"update {module.job_table} set status = 'failed', error = $2,"
            " updated_at = now() where id = $1",
            UUID(job_id),
            error[:500],
        )


async def run_draft(
    module: DraftModule,
    ctx: dict,
    tenant_id: str,
    subject_id: str,
    job_id: str,
    user_id: str,
) -> str:
    pool: asyncpg.Pool = ctx["pool"]
    loop = asyncio.get_running_loop()

    async with _tenant_tx(pool, tenant_id) as conn:
        job = await conn.fetchrow(f"select * from {module.job_table} where id = $1", UUID(job_id))
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
            f"update {module.job_table} set status = 'running', updated_at = now() where id = $1",
            UUID(job_id),
        )

    try:
        if not virtual_key:
            raise RuntimeError("No model key provisioned for this workspace")

        async with _tenant_tx(pool, tenant_id) as conn:
            pack = await module.gather(conn, UUID(subject_id), kind, params, date.today())

        ledger = LlmLedger()
        queries = module.queries_for(kind, pack)
        if queries:
            embedded = await embed_texts(virtual_key, queries)  # network — outside tx
            ledger.embed_tokens = embedded.tokens
            ledger.embed_cost_usd = embedded.cost_usd
            async with _tenant_tx(pool, tenant_id) as conn:
                weights = await module.scope_weights(conn, UUID(subject_id))
                pack.excerpts = await retrieve_excerpts(conn, queries, embedded.vectors, weights)

        sections_spec = module.skeletons[kind]
        system, user = outline_prompt(pack, sections_spec, module.system_prompt)
        outline = parse_outline(await chat(ledger, virtual_key, "drafter", system, user))

        sections: list[tuple[Section, str]] = []
        for section in sections_spec:
            system, user = section_prompt(
                pack, section, outline.get(section.key, []), module.system_prompt
            )
            text = await chat(ledger, virtual_key, section.alias, system, user)
            sections.append((section, text))

        draft: AssembledDraft = assemble_docx(pack, sections, date.today(), tables=module.tables)
        file_key = f"{tenant_id}/{module.storage_segment}/{subject_id}/drafts/{job_id}.docx"
        await loop.run_in_executor(None, upload_bytes, file_key, draft.data, DOCX_MIME)

        async with _tenant_tx(pool, tenant_id) as conn:
            doc_id = await module.register(
                conn,
                tenant_id=tenant_id,
                subject_id=subject_id,
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
            await _mark_failed(pool, module, tenant_id, job_id, str(exc))
        raise
    except ValueError as exc:
        # Gather-level validation (missing subject, missing funding source) —
        # the message is already user-safe.
        with contextlib.suppress(Exception):
            await _mark_failed(pool, module, tenant_id, job_id, str(exc))
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
            await _mark_failed(pool, module, tenant_id, job_id, reason)
        raise
