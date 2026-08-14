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
from app.db import db
from app.errors import ApiError
from app.litellm import StreamResult, estimate_cost_usd, litellm_client
from app.ratelimit import rate_limiter
from app.refdata.questions import (
    create_question_set,
    get_question_set,
    list_question_sets,
    update_question_set,
)
from app.refdata.schemas import (
    FormFetchIn,
    FormFetchOut,
    QuestionSetIn,
    QuestionSetOut,
    QuestionSetPatch,
    TranscribeIn,
    TranscribeOut,
)
from app.refdata.transcribe import build_prompt, limits_in_source, parse_questions
from app.search import exa_contents
from app.secrets import decrypt_llm_key
from app.tenant import TenantContext, get_conn, require_role

router = APIRouter(tags=["question-sets"])

#: Extraction, not reasoning — the cheap alias is the right one.
TRANSCRIBE_ALIAS = "workhorse"

#: The transcribe box's own ceiling (TranscribeIn.source max_length) — a
#: fetch that returns more than the box can take is truncated and says so.
FETCH_MAX_CHARS = 24_000


@router.post("/question-sets/fetch", response_model=FormFetchOut)
async def fetch_form_page(
    body: FormFetchIn,
    ctx: TenantContext = Depends(require_role("member")),
):
    """Fetch a funder page's text to pre-fill the transcribe box.

    An assist, never an automation (form-fetch PRD §3): the text lands in the
    paste box the user already reviews, and nothing is transcribed or saved
    here. Gated on `web_search` the cross-cutting way (400, not a 404 router)
    because it is the same egress and the same commercial boundary as
    research mode. The fetch runs on Exa's infrastructure, so the
    user-supplied URL is never dereferenced from inside our network.

    Explicit transactions rather than Depends(get_conn): the Exa call is
    network and stays outside any transaction, and the usage row must commit
    before the empty-page 422 can raise — an ApiError inside a shared
    request transaction would roll the metering back (hard constraint 5).
    """
    async with db.tenant_tx(ctx.user_id, ctx.tenant_id) as conn:
        enabled = await conn.fetchval(
            "select features->>'web_search' = 'true' from tenants where id = $1", ctx.tenant_id
        )
    if not enabled:
        raise ApiError(400, "feature_disabled", "Web search is not enabled for this workspace")
    await rate_limiter.check_form_fetch(ctx.tenant_id)

    # Fetch one char past the cap so truncation is detectable, not guessed.
    page = await exa_contents(str(body.url), max_chars=FETCH_MAX_CHARS + 1)
    # Per-fetch metering, same shape as research mode: Exa bills per call, so
    # there are no token counts — but the call is spend either way.
    async with db.tenant_tx(ctx.user_id, ctx.tenant_id) as conn:
        await conn.execute(
            "insert into usage_events (tenant_id, user_id, kind, model)"
            " values ($1, $2, 'search', 'exa')",
            ctx.tenant_id,
            ctx.user_id,
        )
    if page is None:
        raise ApiError(
            422,
            "no_text",
            "That page had no readable text — a PDF, a login page or a script-only portal."
            " Paste the questions instead.",
        )
    truncated = len(page.text) > FETCH_MAX_CHARS
    return FormFetchOut(
        url=page.url,
        title=page.title,
        text=page.text[:FETCH_MAX_CHARS],
        truncated=truncated,
    )


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
