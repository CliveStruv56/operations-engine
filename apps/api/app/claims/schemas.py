"""Pydantic models for the claims register.

Per CLAUDE.md, models live here rather than inline in routers.
"""

from datetime import date
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

#: Identifier patterns, enforced before anything reaches a register client.
#: These are the only user input that becomes part of an outbound URL, so
#: validating them here is what keeps `registers.py` free of URL-building
#: defence: a value that matches cannot express a path or a host.
COMPANY_NUMBER = r"^[A-Z0-9]{8}$"
EW_CHARITY_NUMBER = r"^\d{6,8}$"
SCOTTISH_CHARITY_NUMBER = r"^SC\d{6}$"


class ClaimKindOut(BaseModel):
    """One fact type the register recognises.

    The catalogue is public within a workspace: the register screen needs it to
    label rows and offer a picker, and the pre-fill matcher needs
    `question_hints`.

    `review_days` is null for kinds whose review date comes from somewhere
    better — an insurance certificate's expiry, an accounting year end — and
    the fallback only applies when nothing better is available.
    """

    key: str
    label: str
    category: str
    value_kind: str
    unit: str | None = None
    cardinality: str
    periodic: bool
    review_days: int | None = None
    statement_template: str
    question_hints: list[str] = Field(default_factory=list)
    #: Named `register_key` rather than `register` because a field called
    #: `register` shadows a BaseModel attribute and Pydantic warns about it.
    register_key: str | None = None
    notes: str | None = None


class ClaimIn(BaseModel):
    kind: str = Field(min_length=1, max_length=100)
    #: Which instance of a multi-valued kind — a trustee's name, "Public
    #: liability", "Cyber Essentials Plus". Null for an ordinary single fact.
    subject: str | None = Field(default=None, max_length=300)
    #: Which slice of a series — "2024/25". Null for the current standing
    #: value, which is what almost everything reads.
    period: str | None = Field(default=None, max_length=50)
    #: The sentence a prompt and a list row read. Generated from the kind's
    #: template on import; typed by a person otherwise.
    statement: str = Field(min_length=1, max_length=4_000)
    value: Any = None
    unit: str | None = Field(default=None, max_length=50)
    as_of: date | None = None
    expires_on: date | None = None
    notes: str | None = Field(default=None, max_length=5_000)
    #: The vault document this fact was read from, when there is one. Checked
    #: against the tenant's own documents before it is stored — Postgres
    #: validates foreign keys with RLS bypassed, so the constraint alone would
    #: accept another workspace's id.
    source_document_id: UUID | None = None
    source_chunk_id: UUID | None = None


class ClaimPatch(BaseModel):
    subject: str | None = Field(default=None, max_length=300)
    period: str | None = Field(default=None, max_length=50)
    statement: str | None = Field(default=None, min_length=1, max_length=4_000)
    value: Any = None
    unit: str | None = Field(default=None, max_length=50)
    as_of: date | None = None
    expires_on: date | None = None
    notes: str | None = Field(default=None, max_length=5_000)
    #: Accept a proposal, or reject one. Confirming supersedes any existing
    #: confirmed claim of the same identity in the same transaction, which is
    #: how a changed figure replaces the old one without losing it.
    status: str | None = Field(default=None, pattern="^(confirmed|rejected)$")
    #: Confirming a fact somebody has just checked is still true. Moves
    #: `last_verified` to today and `next_review` by the kind's own cycle.
    #: The one place either date may move forward.
    verified: bool | None = None
    #: Who is responsible for keeping this true. The only field here where an
    #: explicit null means "clear it" rather than "unchanged" — `update_claim`
    #: reads `model_fields_set` for this one, so sending null hands the fact
    #: back to nobody, and omitting it leaves the owner alone.
    owner_membership_id: UUID | None = None


class ClaimOut(BaseModel):
    """A claim as the register screen and the drafting worker see it.

    `stale` and `expired` are derived, never stored — same contract as the
    funder catalogue and the question sets. A claim can be both: an insurance
    policy that lapsed in April is expired, and overdue for review besides.
    """

    id: UUID
    kind: str
    label: str
    category: str
    subject: str | None
    period: str | None
    statement: str
    value: Any = None
    unit: str | None
    as_of: date | None
    expires_on: date | None
    status: str
    source: str
    source_ref: str | None
    source_document_id: UUID | None
    source_document_title: str | None = None
    source_chunk_id: UUID | None
    owner_membership_id: UUID | None
    last_verified: date | None
    next_review: date | None
    notes: str | None
    stale: bool
    expired: bool


class ClaimSummaryOut(BaseModel):
    """The register in four numbers, for a count the sidebar can always show.

    A fact only gets updated if somebody is told it has gone off *before* they
    need it, and until this existed the register announced itself in exactly
    two places, both of which needed somebody to already be looking.

    Counts only what a person can act on, following `claims_warning`: a badge
    saying "you hold eighty facts" is a badge nobody reads. `stale` and
    `expired` break `needs_attention` down so the count can name the problem
    rather than gesture at it — and because one claim can be both, they may sum
    to more than `needs_attention`, which counts claims and not complaints.
    """

    #: Confirmed claims past review or lapsed. Proposals are deliberately not
    #: in here — an unanswered question is not a fact that has gone wrong.
    needs_attention: int
    stale: int
    expired: int
    proposals: int


class RegisterImportIn(BaseModel):
    """A lookup against one public register.

    Exactly one identifier is meaningful per route, so each route takes the
    one it needs rather than this carrying a union — a body that accepts both
    a company number and a charity number invites sending the wrong one.
    """

    number: str = Field(min_length=1, max_length=20)
    #: Import from a register whose record is not active. Off by default: a
    #: dissolved company and a removed charity both still return full data,
    #: and a bid asserting current registration from a dead record is the
    #: worst failure this feature could produce.
    allow_inactive: bool = False


class RegisterImportOut(BaseModel):
    """What a lookup found, after it has been written as proposals.

    Nothing here is asserted. Every row lands `proposed` and waits for a
    person, which is the register's founding rule: never ask somebody to
    populate a database, ask them to confirm or reject something already found.
    """

    register_key: str
    #: The public, human-readable page these facts came from. Shown beside the
    #: proposals, and later carried into the Data sources appendix of any
    #: document that leans on them.
    source_url: str
    registration_status: str
    #: True when the register's record is not live. The proposals are still
    #: returned, but the UI leads with this.
    inactive: bool
    proposed: list[ClaimOut]
    #: Facts the register returned that the register already agreed with —
    #: counted rather than listed, so a re-run reads as "nothing changed".
    unchanged: int
    skipped_unknown_kinds: list[str] = Field(default_factory=list)
