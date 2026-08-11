"""Pydantic models for shared reference data.

Per CLAUDE.md, models live here rather than inline in routers.
"""

from datetime import date
from uuid import UUID

from pydantic import BaseModel, Field


class Question(BaseModel):
    """One field on a funder's form.

    `limit` is the funder's own stated ceiling on the field behind this
    question, and it is the whole reason this data exists: a portal counts
    every letter, number, punctuation mark and space, and cuts off at the
    limit without asking. An answer drafted against a wrong limit is found
    out at the portal, after the writing is done.
    """

    id: str
    order: int
    text: str
    guidance: str = ""
    limit_kind: str = Field(default="characters", pattern="^(characters|words)$")
    limit: int | None = None
    required: bool = True
    #: Retrieve and cite vault excerpts when drafting this answer.
    uses_vault: bool = False


class Citation(BaseModel):
    """A vault source behind an answer. Kept beside the prose rather than
    inside it — a form field has no References page for a `[1]` to point at."""

    n: int
    title: str
    pages: str | None = None


class AnswerOut(BaseModel):
    """One drafted answer, ready to paste.

    `length`/`over_by` are in the question's own units. An over-limit answer is
    reported, never trimmed: cutting it to fit would end it mid-sentence, which
    is the failure `[TO CONFIRM]` exists to make visible rather than hide.
    """

    question_id: str
    question: str
    guidance: str = ""
    text: str
    limit: int | None = None
    limit_kind: str = "characters"
    length: int
    over_by: int
    to_confirm: int
    citations: list[Citation] = Field(default_factory=list)


class AnswerSheetOut(BaseModel):
    job_id: UUID
    question_set_key: str | None = None
    answers: list[AnswerOut]
    #: Counts the UI leads with, so nobody has to scroll to find the problems.
    over_limit: int
    to_confirm: int


class QuestionSetOut(BaseModel):
    """A funder's question set, platform-curated or the tenant's own.

    `stale` is derived, never stored — same contract as the funder catalogue.
    `source` says which table it came from, because a tenant's own set is not
    something we have checked and the UI must not present the two alike.
    """

    key: str
    name: str
    funder: str
    stage: str
    source_url: str | None
    status: str
    questions: list[Question]
    last_verified: date
    next_review: date
    notes: str | None
    stale: bool
    source: str = Field(pattern="^(platform|tenant)$")
