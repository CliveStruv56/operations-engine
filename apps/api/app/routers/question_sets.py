"""Funder question sets — what a funder's form actually asks, and how one
gets into the workspace.

Unflagged, unlike the drafting modules that consume it. A workspace with
`projects` and a workspace with `grants` both answer funders' forms, and a
workspace with neither can still browse what we hold.

Two sources, and the difference is the whole point. The platform catalogue is
curated by the operator and read-only here. A tenant's own set is transcribed
from a funder's published guidance by somebody in that workspace, arrives
`unverified`, and says so wherever it is used until a person confirms it.

Writes are member-level rather than admin. Blocking them behind admin would
put the person who actually hits a new funder on Tuesday behind whoever holds
the role, and the safety mechanism here was never the role gate — it is that
an unverified set is labelled as one on the draft's first page, on the answer
sheet, and in the picker.
"""

from datetime import date

import asyncpg
from fastapi import APIRouter, Depends

from app.audit import write_audit
from app.errors import ApiError
from app.litellm import StreamResult, estimate_cost_usd, litellm_client
from app.refdata.questions import (
    create_question_set,
    get_question_set,
    list_question_sets,
    update_question_set,
)
from app.refdata.schemas import (
    QuestionSetIn,
    QuestionSetOut,
    QuestionSetPatch,
    TranscribeIn,
    TranscribeOut,
)
from app.refdata.transcribe import build_prompt, limits_in_source, parse_questions
from app.secrets import decrypt_llm_key
from app.tenant import TenantContext, get_conn, require_role

router = APIRouter(tags=["question-sets"])

#: Extraction, not reasoning — the cheap alias is the right one.
TRANSCRIBE_ALIAS = "workhorse"


@router.get("/question-sets", response_model=list[QuestionSetOut])
async def list_sets(
    ctx: TenantContext = Depends(require_role("member")),
    conn: asyncpg.Connection = Depends(get_conn),
):
    return await list_question_sets(conn, date.today())


@router.get("/question-sets/{key}", response_model=QuestionSetOut)
async def get_set(
    key: str,
    ctx: TenantContext = Depends(require_role("member")),
    conn: asyncpg.Connection = Depends(get_conn),
):
    question_set = await get_question_set(conn, key, date.today())
    if question_set is None:
        raise ApiError(404, "not_found", "Question set not found")
    return question_set


@router.post("/question-sets/transcribe", response_model=TranscribeOut)
async def transcribe(
    body: TranscribeIn,
    ctx: TenantContext = Depends(require_role("member")),
    conn: asyncpg.Connection = Depends(get_conn),
):
    """Read a funder's published question list into a proposal.

    Stores nothing. The reply is something to correct, not something to trust:
    the model is told never to invent a limit, and every limit it could not
    find comes back null for a person to fill in.
    """
    virtual_key = decrypt_llm_key(
        await conn.fetchval(
            "select litellm_key_encrypted from tenants where id = $1", ctx.tenant_id
        )
    )
    if not virtual_key:
        raise ApiError(503, "llm_unavailable", "No model key is provisioned for this workspace")

    result = StreamResult()
    raw = await litellm_client.complete(
        virtual_key, TRANSCRIBE_ALIAS, build_prompt(body.source), result
    )
    cost = estimate_cost_usd(TRANSCRIBE_ALIAS, result.tokens_in, result.tokens_out)
    await conn.execute(
        """
        insert into usage_events (tenant_id, user_id, kind, model,
                                  tokens_in, tokens_out, cost_usd)
        values ($1, $2, 'transcribe', $3, $4, $5, $6)
        """,
        ctx.tenant_id,
        ctx.user_id,
        TRANSCRIBE_ALIAS,
        result.tokens_in,
        result.tokens_out,
        cost,
    )

    questions = parse_questions(raw)
    return TranscribeOut(
        questions=questions,
        limits_missing=sum(1 for q in questions if q.limit is None),
        limits_in_source=limits_in_source(body.source),
    )


@router.post("/question-sets", status_code=201, response_model=QuestionSetOut)
async def create_set(
    body: QuestionSetIn,
    ctx: TenantContext = Depends(require_role("member")),
    conn: asyncpg.Connection = Depends(get_conn),
):
    existing = await conn.fetchval("select 1 from tenant_question_sets where key = $1", body.key)
    if existing:
        raise ApiError(409, "key_taken", "This workspace already has a form with that key")
    question_set = await create_question_set(conn, str(ctx.tenant_id), body)
    await write_audit(
        conn,
        ctx.tenant_id,
        ctx.user_id,
        "question_sets.create",
        "tenant_question_set",
        body.key,
        {"funder": body.funder, "questions": len(body.questions)},
    )
    return question_set


@router.patch("/question-sets/{key}", response_model=QuestionSetOut)
async def update_set(
    key: str,
    body: QuestionSetPatch,
    ctx: TenantContext = Depends(require_role("member")),
    conn: asyncpg.Connection = Depends(get_conn),
):
    """Edit a set this workspace transcribed. The platform catalogue is the
    operator's — a tenant that wants to change one copies it first."""
    question_set = await update_question_set(conn, key, body)
    await write_audit(
        conn,
        ctx.tenant_id,
        ctx.user_id,
        "question_sets.verify" if body.verified else "question_sets.update",
        "tenant_question_set",
        key,
    )
    return question_set


@router.delete("/question-sets/{key}", status_code=204)
async def delete_set(
    key: str,
    ctx: TenantContext = Depends(require_role("member")),
    conn: asyncpg.Connection = Depends(get_conn),
):
    """Drafts already written against it keep their answers — those live on
    the job row, not here — so removing a set loses no work."""
    deleted = await conn.fetchval(
        "delete from tenant_question_sets where key = $1 returning key", key
    )
    if deleted is None:
        raise ApiError(404, "not_found", "You can only delete your workspace's own question sets")
    await write_audit(
        conn, ctx.tenant_id, ctx.user_id, "question_sets.delete", "tenant_question_set", key
    )
