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
from uuid import UUID

import asyncpg

from app.errors import ApiError
from app.refdata.schemas import (
    AnswerOut,
    AnswerSheetOut,
    Question,
    QuestionSetIn,
    QuestionSetOut,
    QuestionSetPatch,
)

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


async def list_platform_sets(conn: asyncpg.Connection, today: date) -> list[QuestionSetOut]:
    """The curated catalogue alone.

    Separate from `list_question_sets` because the operator console runs on
    the owner connection, where RLS does not bind: reading
    `tenant_question_sets` there would hand the operator every workspace's
    private forms as though they were ours.
    """
    rows = await conn.fetch(f"select {_COLUMNS} from ref_question_sets")
    sets = [_row_out(r, "platform", today) for r in rows]
    return sorted(sets, key=lambda s: (s.funder.lower(), s.name.lower()))


async def get_platform_set(
    conn: asyncpg.Connection, key: str, today: date
) -> QuestionSetOut | None:
    row = await conn.fetchrow(f"select {_COLUMNS} from ref_question_sets where key = $1", key)
    return _row_out(row, "platform", today) if row is not None else None


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


def validate_questions(questions: list[Question]) -> list[dict]:
    """Reject a set that would break drafting, and normalise the order.

    Checked here rather than trusted from the client because these rows drive
    the worker: a duplicate id silently loses an answer on the sheet, and a
    gap in the order misnumbers every question after it on a funder's form.
    """
    ids = [q.id for q in questions]
    if len(ids) != len(set(ids)):
        raise ApiError(422, "duplicate_question_id", "Two questions share the same id")
    for q in questions:
        if not q.text.strip():
            raise ApiError(422, "empty_question", "A question cannot be blank")
        if q.limit is not None and q.limit <= 0:
            raise ApiError(422, "bad_limit", f"“{q.text[:40]}” has a limit of {q.limit}")
    # Renumber rather than reject: the client may have reordered or deleted,
    # and position is ours to own once the set is stored.
    return [
        {**q.model_dump(), "order": position}
        for position, q in enumerate(sorted(questions, key=lambda q: q.order), start=1)
    ]


async def create_question_set(
    conn: asyncpg.Connection, tenant_id: str, body: QuestionSetIn
) -> QuestionSetOut:
    questions = validate_questions(body.questions)
    row = await conn.fetchrow(
        f"""
        insert into tenant_question_sets (tenant_id, key, name, funder, stage, source_url,
                                          questions, status, last_verified, next_review, notes)
        values ($1, $2, $3, $4, $5, $6, $7, 'unverified', current_date, current_date, $8)
        returning {_COLUMNS}
        """,
        UUID(tenant_id),
        body.key,
        body.name,
        body.funder,
        body.stage,
        body.source_url,
        json.dumps(questions),
        body.notes,
    )
    return _row_out(row, "tenant", date.today())


async def update_question_set(
    conn: asyncpg.Connection, key: str, body: QuestionSetPatch
) -> QuestionSetOut:
    sets: list[str] = []
    values: list[object] = [key]

    def add(column: str, value: object) -> None:
        values.append(value)
        sets.append(f"{column} = ${len(values)}")

    for column in ("name", "funder", "stage", "source_url", "notes"):
        value = getattr(body, column)
        if value is not None:
            add(column, value)
    if body.questions is not None:
        add("questions", json.dumps(validate_questions(body.questions)))
        if not body.verified:
            # Changing the questions is a new transcription. The old tick was
            # against a different form, so the caveat has to come back.
            sets.append("status = 'unverified'")
    if body.verified:
        # Verification is an act somebody performs. This is the endpoint where
        # they perform it, so it is the one place a date may move forward.
        sets.append("status = 'open'")
        sets.append("last_verified = current_date")
        sets.append("next_review = current_date + 90")
    if not sets:
        raise ApiError(422, "nothing_to_update", "No changes were sent")

    row = await conn.fetchrow(
        f"update tenant_question_sets set {', '.join(sets)}, updated_at = now()"
        f" where key = $1 returning {_COLUMNS}",
        *values,
    )
    if row is None:
        raise ApiError(404, "not_found", "You can only edit your workspace's own question sets")
    return _row_out(row, "tenant", date.today())


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
        from_register=sum(1 for a in parsed if a.origin == "claim"),
    )
