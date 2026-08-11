"""Reading question sets, and the answer sheet a draft produces from one.

Shared by both drafting modules: a funder's form is the same object whether a
development consultancy or a charity is filling it in, and the answer sheet is
the same shape either way.

Writes belong to the operator (platform catalogue) or to a later import flow
(the tenant's own). Nothing here writes.
"""

import json
from datetime import date
from typing import Any

import asyncpg

from app.errors import ApiError
from app.refdata.schemas import AnswerOut, AnswerSheetOut, QuestionSetOut

_COLUMNS = """
    key, name, funder, stage, status, source_url, questions,
    last_verified, next_review, notes
"""


def _loads(value: Any) -> Any:
    # asyncpg returns jsonb as str (no codec registered) — decode at the edge.
    return json.loads(value) if isinstance(value, str) else value


def _row_out(row: asyncpg.Record, source: str, today: date) -> QuestionSetOut:
    return QuestionSetOut(
        **{k: row[k] for k in ("key", "name", "funder", "stage", "status", "source_url", "notes")},
        last_verified=row["last_verified"],
        next_review=row["next_review"],
        questions=_loads(row["questions"]) or [],
        stale=row["next_review"] <= today,
        source=source,
    )


async def list_question_sets(conn: asyncpg.Connection, today: date) -> list[QuestionSetOut]:
    """Every set this tenant can draft against.

    A tenant's own copy of a key replaces the platform one rather than
    appearing beside it — two rows with the same key and different questions
    is a choice nobody can make correctly from a dropdown.
    """
    tenant_rows = await conn.fetch(f"select {_COLUMNS} from tenant_question_sets")
    owned = {r["key"] for r in tenant_rows}
    ref_rows = await conn.fetch(f"select {_COLUMNS} from ref_question_sets")

    sets = [_row_out(r, "tenant", today) for r in tenant_rows]
    sets += [_row_out(r, "platform", today) for r in ref_rows if r["key"] not in owned]
    return sorted(sets, key=lambda s: (s.funder.lower(), s.name.lower()))


async def get_question_set(
    conn: asyncpg.Connection, key: str, today: date
) -> QuestionSetOut | None:
    row = await conn.fetchrow(f"select {_COLUMNS} from tenant_question_sets where key = $1", key)
    if row is not None:
        return _row_out(row, "tenant", today)
    row = await conn.fetchrow(f"select {_COLUMNS} from ref_question_sets where key = $1", key)
    return _row_out(row, "platform", today) if row is not None else None


async def require_question_set(conn: asyncpg.Connection, key: str | None) -> QuestionSetOut:
    """Resolve the key a draft was submitted with, or refuse the draft.

    Checked here rather than in the worker so a mistyped key is a 422 the user
    can act on, not a job that queues, starts, and fails a minute later.
    """
    if not key:
        raise ApiError(422, "question_set_required", "Pick the funder's form you are answering")
    question_set = await get_question_set(conn, key, date.today())
    if question_set is None:
        raise ApiError(404, "not_found", "Question set not found")
    if not question_set.questions:
        raise ApiError(
            422, "question_set_empty", "That form has no questions recorded against it yet"
        )
    return question_set


def answer_sheet(row: asyncpg.Record) -> AnswerSheetOut:
    """The persisted answer sheet for a finished draft job.

    `answers` is null for every kind but `application_form` — an ordinary
    document is read as a document, not pasted field by field.
    """
    answers = _loads(row["answers"])
    if not answers:
        raise ApiError(
            404, "no_answer_sheet", "This draft is a document, not a set of form answers"
        )
    parsed = [AnswerOut(**a) for a in answers]
    params = _loads(row["params"]) or {}
    return AnswerSheetOut(
        job_id=row["id"],
        question_set_key=params.get("question_set_key"),
        answers=parsed,
        over_limit=sum(1 for a in parsed if a.over_by > 0),
        to_confirm=sum(a.to_confirm for a in parsed),
    )
