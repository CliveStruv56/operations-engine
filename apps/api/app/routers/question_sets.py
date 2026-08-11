"""Funder question sets — what a funder's form actually asks.

Unflagged, unlike the drafting modules that consume it. A workspace with
`projects` and a workspace with `grants` both answer funders' forms, and a
workspace with neither can still browse what we hold. Reads only: the platform
catalogue is the operator's, and a tenant's own sets arrive through import.
"""

from datetime import date

import asyncpg
from fastapi import APIRouter, Depends

from app.errors import ApiError
from app.refdata.questions import get_question_set, list_question_sets
from app.refdata.schemas import QuestionSetOut
from app.tenant import TenantContext, get_conn, require_role

router = APIRouter(tags=["question-sets"])


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
