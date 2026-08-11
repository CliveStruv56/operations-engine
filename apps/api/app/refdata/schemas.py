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


class TranscribeIn(BaseModel):
    """Text a person copied out of a funder's own published guidance."""

    source: str = Field(min_length=20, max_length=24_000)


class TranscribeOut(BaseModel):
    """A proposal, not a saved set. Nothing is stored until a human confirms.

    `limits_missing` and `limits_in_source` exist to make the one unverifiable
    field noisy: if the text mentions five limits and only three came back, the
    reviewer should look again before anything drafts against it.
    """

    questions: list[Question]
    limits_missing: int
    limits_in_source: int


class QuestionSetIn(BaseModel):
    key: str = Field(min_length=1, max_length=200, pattern=r"^[a-z0-9][a-z0-9_-]*$")
    name: str = Field(min_length=1, max_length=300)
    funder: str = Field(min_length=1, max_length=300)
    stage: str = Field(default="full", pattern="^(eoi|full|monitoring)$")
    #: Where the questions were transcribed from. Required: a set with no
    #: source is one nobody can re-check, which is how a catalogue rots.
    source_url: str = Field(min_length=1, max_length=1000)
    questions: list[Question] = Field(min_length=1)
    notes: str | None = Field(default=None, max_length=5_000)


class QuestionSetPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=300)
    funder: str | None = Field(default=None, min_length=1, max_length=300)
    stage: str | None = Field(default=None, pattern="^(eoi|full|monitoring)$")
    source_url: str | None = Field(default=None, min_length=1, max_length=1000)
    questions: list[Question] | None = Field(default=None, min_length=1)
    notes: str | None = Field(default=None, max_length=5_000)
    #: Confirming a set you have checked against the funder's live form. Sets
    #: `last_verified` to today and `next_review` 90 days out — the same act an
    #: operator performs on the platform catalogue, and the only thing that
    #: clears the "not one we have checked" warning.
    verified: bool | None = None


class PromoteIn(BaseModel):
    """Publish a workspace's transcribed form to the platform catalogue."""

    tenant_id: UUID
    key: str = Field(min_length=1, max_length=200)
    #: The operator's own affirmation that they have opened the funder's form
    #: and read the questions and limits against it. Required and must be
    #: true. A tenant verifying a set for themselves is not the same act as
    #: putting it in front of every workspace, and "verification is an act
    #: somebody performs, not a value somebody types" has to keep meaning
    #: something at the point where one row becomes everybody's.
    confirmed_against_source: bool
    #: Replace an existing catalogue row of the same key. Off by default so a
    #: promotion cannot quietly overwrite a curated form.
    replace: bool = False
    notes: str | None = Field(default=None, max_length=5_000)


class PromoteCandidate(BaseModel):
    """A tenant's transcribed form, seen from the operator console."""

    tenant_id: UUID
    tenant_name: str
    key: str
    name: str
    funder: str
    stage: str
    status: str
    source_url: str | None
    question_count: int
    #: Questions with no limit recorded. A form still carrying blanks is not
    #: ready to be everybody's copy.
    limits_missing: int
    last_verified: date
    next_review: date
    stale: bool
    #: Whether the platform catalogue already holds this key.
    in_catalogue: bool


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
