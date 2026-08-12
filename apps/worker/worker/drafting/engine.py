"""The shared drafting job: gather → retrieve → outline → sections →
assemble → upload → register, with the job row tracking every transition.

Registration is the only step that mutates a module's registry, and it runs
last — a failure anywhere (including the cost guard) marks the job failed and
leaves no orphaned rows. Network calls (LiteLLM, S3) always happen outside
tenant transactions.

Cost telemetry is the engine's, not a module's: every terminal outcome —
success, budget guard, empty section, timeout, provider error — writes the
ledger to `usage_events` exactly once (`drafting/usage.py`).

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

from worker.claims.facts import merge_excerpts
from worker.db import tenant_tx as _tenant_tx
from worker.drafting.assemble import AssembledDraft, TableRenderer, assemble_docx
from worker.drafting.llm import DraftBudgetExceeded, EmptySectionError, LlmLedger, chat
from worker.drafting.pack import DraftPackBase
from worker.drafting.prefill import partition_prefilled, restore_order
from worker.drafting.prompts import (
    batch_prompt,
    outline_prompt,
    parse_answers,
    parse_outline,
    section_prompt,
)
from worker.drafting.retrieval import retrieve_excerpts
from worker.drafting.sections import Section, check_call_budget, plan_calls
from worker.drafting.usage import write_usage
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
    #: Writes the registry row, audit row and job completion. Usage events are
    #: the engine's job, not a module's — see `drafting/usage.py`.
    register: Callable[..., Awaitable[UUID]]
    #: (kind, pack) -> sections, for kinds whose shape is data rather than a
    #: skeleton — an application form, where the questions are the funder's.
    #: Consulted only when `kind` has no skeleton. Pure, like `queries_for`:
    #: the module's `gather` puts the question set on the pack, so resolving
    #: sections needs no second trip to the database.
    sections_for: Callable[[str, DraftPackBase], list[Section]] | None = None


async def _section_text(
    ledger: LlmLedger, virtual_key: str, section: Section, system: str, user: str
) -> str:
    """Draft one section, retrying once if the model returns nothing.

    Empty replies are intermittent — the same prompt succeeds on the next
    attempt — so failing a whole job on the first one would make drafting
    flaky for no safety gain. The retry is charged to the ledger like any
    other call, because it really was two calls. If the second is empty too,
    `EmptySectionError` propagates and the job fails: a document with a hole
    in it is never the fallback.
    """
    try:
        return await chat(ledger, virtual_key, section.alias, system, user)
    except EmptySectionError:
        return await chat(ledger, virtual_key, section.alias, system, user)


_TRUNCATED_MARKER = (
    "\n\n[TO CONFIRM: this section was cut short at the model's output "
    "limit — check the end of it and regenerate if needed]"
)


def _resolve_sections(module: DraftModule, kind: str, pack: DraftPackBase) -> list[Section]:
    """The skeleton for this kind, or the question set standing in for one."""
    skeleton = module.skeletons.get(kind)
    if skeleton is not None:
        return skeleton
    if module.sections_for is None:
        raise RuntimeError(f"{kind}: no skeleton and no sections_for on this module")
    sections = module.sections_for(kind, pack)
    if not sections:
        raise RuntimeError(f"{kind}: resolved to no sections at all")
    return sections


async def _batch_answers(
    ledger: LlmLedger, virtual_key: str, batch: list[Section], system: str, user: str
) -> dict[str, str]:
    """Answer a group of questions in one call, retrying the group once.

    A batched reply is JSON, so the usual truncation symptom is not clipped
    prose but a reply that will not parse at all — which lands here as a
    missing key rather than a short answer. Either way the group is redrafted
    once and then the job fails, because a form with a silently blank answer
    on it is worse than one that did not finish.
    """
    for _ in range(2):
        answers = parse_answers(
            await chat(ledger, virtual_key, batch[0].alias, system, user, allow_empty=True)
        )
        if all(answers.get(s.key, "").strip() for s in batch):
            return answers
    missing = ", ".join(s.key for s in batch)
    raise EmptySectionError(
        f"The model did not answer every question in this group ({missing}). Try drafting again."
    )


async def _draft_batch(
    ledger: LlmLedger,
    virtual_key: str,
    module: DraftModule,
    pack: DraftPackBase,
    batch: list[Section],
    outline: dict[str, list[str]],
) -> list[tuple[Section, str]]:
    if len(batch) == 1:
        section = batch[0]
        system, user = section_prompt(
            pack, section, outline.get(section.key, []), module.system_prompt
        )
        text = await _section_text(ledger, virtual_key, section, system, user)
        if ledger.calls[-1].truncated:
            # The prose stops mid-sentence. Say so in the document rather than
            # leaving a reader to notice: this rides the existing [TO CONFIRM]
            # machinery, so it also lands in the job's to_confirm_count and the
            # UI's "N items to confirm".
            text += _TRUNCATED_MARKER
        return [(section, text)]

    system, user = batch_prompt(pack, batch, outline, module.system_prompt)
    answers = await _batch_answers(ledger, virtual_key, batch, system, user)
    drafted = []
    for index, section in enumerate(batch):
        text = answers[section.key]
        # A call stops at the ceiling once, at the end — so within a batch only
        # the last answer can be the one that was cut. Marking them all would
        # send a consultant to check seven answers that are fine.
        if ledger.calls[-1].truncated and index == len(batch) - 1:
            text += _TRUNCATED_MARKER
        drafted.append((section, text))
    return drafted


async def _mark_failed(
    pool: asyncpg.Pool,
    module: DraftModule,
    tenant_id: str,
    job_id: str,
    error: str,
    user_id: str,
    ledger: LlmLedger,
) -> None:
    """Fail the job row, then bill whatever it already spent.

    Two transactions on purpose. A failure that has already made nine model
    calls must still be metered (hard constraint 5), but a usage write that
    itself fails must not roll back the failure status — the UI polls that row
    and would otherwise wait on 'running' forever. Every call site wraps this
    in `contextlib.suppress`, so an exception here is invisible.
    """
    async with _tenant_tx(pool, tenant_id) as conn:
        # Table name comes from the frozen module definition, never a request.
        await conn.execute(
            f"update {module.job_table} set status = 'failed', error = $2,"
            " updated_at = now() where id = $1",
            UUID(job_id),
            error[:500],
        )
    # Nothing spent, nothing to write — and on the cancellation path there may
    # be no time for a second transaction anyway.
    if ledger.calls or ledger.embed_tokens:
        async with _tenant_tx(pool, tenant_id) as conn:
            await write_usage(conn, tenant_id, user_id, ledger)


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
    # Hoisted above the try so every failure path can bill what was spent — a
    # gather-level failure then correctly reports zero calls rather than
    # crashing `_mark_failed` on an unbound name.
    ledger = LlmLedger()

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

        queries = module.queries_for(kind, pack)
        if queries:
            embedded = await embed_texts(virtual_key, queries)  # network — outside tx
            ledger.embed_tokens = embedded.tokens
            ledger.embed_cost_usd = embedded.cost_usd
            async with _tenant_tx(pool, tenant_id) as conn:
                weights = await module.scope_weights(conn, UUID(subject_id))
                pack.excerpts = await retrieve_excerpts(conn, queries, embedded.vectors, weights)

        # Outside the `if queries:` branch on purpose. `retrieve_excerpts`
        # *assigns* `pack.excerpts`, and only runs when there is something to
        # retrieve — so merging inside it would silently drop every claim
        # citation for any kind with no vault retrieval (a monthly report, a
        # short application form), leaving the model told to cite ids that
        # never reached the excerpts.
        pack.excerpts = merge_excerpts(pack.excerpts, pack.claim_excerpts)

        sections_spec = _resolve_sections(module, kind, pack)
        # Answer what the register already knows before planning any calls.
        # Doing it here rather than after drafting is the whole saving: a
        # pre-filled question never reaches `plan_calls`, so it costs nothing
        # and does not count against the call budget — which means a long form
        # that previously refused to draft may now fit.
        prefilled, to_draft, claim_ids = partition_prefilled(sections_spec, pack)

        batches = plan_calls(to_draft)
        # Fail before spending anything, with a message that says what to do.
        check_call_budget(to_draft, batches)

        outline: dict[str, list[str]] = {}
        if to_draft:
            # A form the register answered outright leaves nothing to outline,
            # and paying for a call that annotates no sections would be an odd
            # way to celebrate.
            system, user = outline_prompt(pack, to_draft, module.system_prompt)
            outline = parse_outline(
                await chat(ledger, virtual_key, "drafter", system, user, allow_empty=True)
            )

        drafted: list[tuple[Section, str]] = []
        for batch in batches:
            drafted.extend(await _draft_batch(ledger, virtual_key, module, pack, batch, outline))

        # Back into the funder's own order: the two halves finish separately,
        # and a sheet whose answers do not line up with its questions is
        # unusable.
        sections = restore_order(sections_spec, drafted, prefilled)

        # A kind with no skeleton is answering somebody else's form, so it also
        # produces the pasteable sheet. Ordinary documents do not: their prose
        # is read as a document, and a per-section copy panel would only invite
        # someone to paste a section of a feasibility study somewhere.
        draft: AssembledDraft = assemble_docx(
            pack,
            sections,
            date.today(),
            tables=module.tables,
            answer_sheet=kind not in module.skeletons,
            prefilled_keys={s.key for s, _ in prefilled},
            claim_ids=claim_ids,
        )
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
            await write_usage(conn, tenant_id, user_id, ledger)
        return f"succeeded:{doc_id}"
    except DraftBudgetExceeded as exc:
        with contextlib.suppress(Exception):
            await _mark_failed(pool, module, tenant_id, job_id, str(exc), user_id, ledger)
        raise
    except (ValueError, EmptySectionError) as exc:
        # Gather-level validation (missing subject, missing funding source) and
        # an empty model section — both messages are already user-safe.
        with contextlib.suppress(Exception):
            await _mark_failed(pool, module, tenant_id, job_id, str(exc), user_id, ledger)
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
            await _mark_failed(pool, module, tenant_id, job_id, reason, user_id, ledger)
        raise
