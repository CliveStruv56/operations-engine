"""Grantwork schemas — every module model lives here (ASSUMPTIONS #20).

Groundwork's split between core `app/schemas.py` and its own module file was
incidental and is explicitly not a precedent, so nothing Grantwork defines
belongs in the core surface.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, BeforeValidator, Field

STAGE_KEYS = "^(case|prospect|apply|decision|deliver|monitor|evaluate)$"
APPLICATION_STATUSES = "^(pipeline|drafting|submitted|awarded|declined|withdrawn|complete)$"
FUNDER_KINDS = "^(trust|lottery|statutory|corporate|community_foundation|other)$"
FUNDER_RELATIONSHIPS = "^(prospect|applied|funder|declined|lapsed)$"
DOC_STATUSES = "^(required|drafting|review|final|submitted|na)$"
TASK_STATUSES = "^(todo|doing|done|na)$"
CONDITION_STATUSES = "^(outstanding|submitted|discharged|partially_discharged|na)$"
PERIOD_STATUSES = "^(upcoming|open|drafting|submitted|accepted|na)$"
EMAIL = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"

NOTES_MAX = 5_000


def _reject_null(value: object) -> object:
    """Patch fields are `X | None` to mean "unset", never "set to null".

    The columns behind these are NOT NULL, so an explicit null would reach the
    UPDATE and surface as a 500. Defaults skip validation in Pydantic, so this
    fires only when the client actually sends null. Same helper as the CRM's.
    """
    if value is None:
        raise ValueError("must not be null — omit the field to leave it unchanged")
    return value


NotNull = BeforeValidator(_reject_null)


# -- funders -----------------------------------------------------------------


class FunderIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    ref_key: str | None = Field(default=None, max_length=100)
    kind: str = Field(default="trust", pattern=FUNDER_KINDS)
    website: str | None = Field(default=None, max_length=500)
    contact_name: str | None = Field(default=None, max_length=200)
    contact_email: str | None = Field(default=None, max_length=320, pattern=EMAIL)
    relationship: str = Field(default="prospect", pattern=FUNDER_RELATIONSHIPS)
    notes: str | None = Field(default=None, max_length=NOTES_MAX)


class FunderPatch(BaseModel):
    name: Annotated[str | None, NotNull] = Field(default=None, min_length=1, max_length=200)
    ref_key: str | None = Field(default=None, max_length=100)
    kind: Annotated[str | None, NotNull] = Field(default=None, pattern=FUNDER_KINDS)
    website: str | None = Field(default=None, max_length=500)
    contact_name: str | None = Field(default=None, max_length=200)
    contact_email: str | None = Field(default=None, max_length=320, pattern=EMAIL)
    relationship: Annotated[str | None, NotNull] = Field(default=None, pattern=FUNDER_RELATIONSHIPS)
    notes: str | None = Field(default=None, max_length=NOTES_MAX)


class FunderOut(BaseModel):
    id: UUID
    ref_key: str | None
    name: str
    kind: str
    website: str | None
    contact_name: str | None
    contact_email: str | None
    relationship: str
    notes: str | None
    application_count: int = 0
    created_by: UUID | None
    created_at: datetime
    updated_at: datetime


class CatalogueRow(BaseModel):
    """A platform funder-catalogue row. `stale` is derived, never stored — a
    row past its review date badges in the UI and warns inside any draft it
    parameterised."""

    key: str
    name: str
    funder: str
    funder_type: str
    nations: list[str]
    kind: str
    amount_note: str | None
    typical_award: str | None
    match_note: str | None
    eligibility: str
    status: str
    deadlines: str | None
    route_url: str | None
    docs_required: list[str]
    reporting_note: str | None
    last_verified: date
    next_review: date
    notes: str | None
    stale: bool


# -- applications ------------------------------------------------------------


class ApplicationIn(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    funder_id: UUID | None = None
    project_id: UUID | None = None
    application_type: str = Field(default="project_grant", max_length=100)
    programme_key: str | None = Field(default=None, max_length=100)
    reference: str | None = Field(default=None, max_length=100)
    amount_requested: Decimal | None = Field(default=None, ge=0, le=Decimal("9999999999"))
    restricted: bool = True
    deadline: date | None = None
    start_date: date | None = None
    end_date: date | None = None
    reporting_note: str | None = Field(default=None, max_length=NOTES_MAX)
    notes: str | None = Field(default=None, max_length=NOTES_MAX)


class ApplicationPatch(BaseModel):
    title: Annotated[str | None, NotNull] = Field(default=None, min_length=1, max_length=300)
    funder_id: UUID | None = None
    project_id: UUID | None = None
    reference: str | None = Field(default=None, max_length=100)
    programme_key: str | None = Field(default=None, max_length=100)
    amount_requested: Decimal | None = Field(default=None, ge=0, le=Decimal("9999999999"))
    amount_awarded: Decimal | None = Field(default=None, ge=0, le=Decimal("9999999999"))
    restricted: Annotated[bool | None, NotNull] = None
    deadline: date | None = None
    start_date: date | None = None
    end_date: date | None = None
    reporting_note: str | None = Field(default=None, max_length=NOTES_MAX)
    notes: str | None = Field(default=None, max_length=NOTES_MAX)


class ApplicationStatusIn(BaseModel):
    status: str = Field(pattern=APPLICATION_STATUSES)
    amount_awarded: Decimal | None = Field(default=None, ge=0, le=Decimal("9999999999"))
    decision_at: date | None = None
    submitted_at: date | None = None
    notes: str | None = Field(default=None, max_length=NOTES_MAX)


class ApplicationOut(BaseModel):
    id: UUID
    title: str
    funder_id: UUID | None
    funder_name: str | None
    project_id: UUID | None
    project_name: str | None
    reference: str | None
    application_type: str
    programme_key: str | None
    stage_current: str
    status: str
    amount_requested: Decimal | None
    amount_awarded: Decimal | None
    restricted: bool
    deadline: date | None
    submitted_at: date | None
    decision_at: date | None
    start_date: date | None
    end_date: date | None
    reporting_note: str | None
    notes: str | None
    created_by: UUID | None
    created_at: datetime
    updated_at: datetime
    #: Set only by POST .../status when moving to submitted. True if the
    #: harvest job was queued; false if Redis/worker could not take it. The
    #: application is submitted either way — harvesting must not be able to
    #: fail that act. Null on every other read.
    harvest_queued: bool | None = None


class PortfolioRow(BaseModel):
    """One line of the application portfolio, with the derived figures the
    list view needs. Nothing here is stored — see `app/grants/analytics.py`."""

    id: UUID
    title: str
    funder_id: UUID | None
    funder_name: str | None
    status: str
    stage_current: str
    amount_requested: Decimal | None
    amount_awarded: Decimal | None
    restricted: bool
    deadline: date | None
    updated_at: datetime
    weighted_value: float
    open_conditions: int
    overdue_returns: int
    next_return_due: date | None


class ApplicationCreatedOut(BaseModel):
    id: UUID
    stage_current: str
    seeded: dict[str, int]


# -- stages ------------------------------------------------------------------


class GateItem(BaseModel):
    id: str
    criterion: str
    kind: str
    ref: str | None = None
    done: bool
    done_by: UUID | None = None
    done_at: datetime | None = None


class StageOut(BaseModel):
    id: UUID
    stage_key: str
    label: str
    position: int
    status: str
    planned_start: date | None
    planned_end: date | None
    forecast_start: date | None
    forecast_end: date | None
    actual_start: date | None
    actual_end: date | None
    gate: list[GateItem]
    gate_signed_off_by: UUID | None
    gate_signed_off_at: datetime | None
    gate_exceptions: str | None


class StagePatch(BaseModel):
    status: str | None = Field(default=None, pattern="^(pending|active|passed|regressed|na)$")
    note: str | None = Field(default=None, max_length=1_000)
    planned_start: date | None = None
    planned_end: date | None = None
    forecast_start: date | None = None
    forecast_end: date | None = None
    actual_start: date | None = None
    actual_end: date | None = None


class SignoffIn(BaseModel):
    exceptions: str | None = Field(default=None, max_length=2_000)


# -- tasks -------------------------------------------------------------------


class TaskIn(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    stage_key: str = Field(pattern=STAGE_KEYS)
    details: str | None = Field(default=None, max_length=NOTES_MAX)
    owner_name: str | None = Field(default=None, max_length=200)
    due_date: date | None = None
    is_milestone: bool = False
    tags: list[str] = Field(default_factory=list, max_length=20)


class TaskPatch(BaseModel):
    title: Annotated[str | None, NotNull] = Field(default=None, min_length=1, max_length=300)
    stage_key: Annotated[str | None, NotNull] = Field(default=None, pattern=STAGE_KEYS)
    details: str | None = Field(default=None, max_length=NOTES_MAX)
    owner_name: str | None = Field(default=None, max_length=200)
    due_date: date | None = None
    is_milestone: Annotated[bool | None, NotNull] = None
    tags: Annotated[list[str] | None, NotNull] = Field(default=None, max_length=20)
    status: Annotated[str | None, NotNull] = Field(default=None, pattern=TASK_STATUSES)


class TaskOut(BaseModel):
    id: UUID
    stage_key: str
    title: str
    details: str | None
    owner_name: str | None
    due_date: date | None
    is_milestone: bool
    tags: list[str]
    status: str
    source: str
    completed_at: datetime | None
    position: int


# -- document registry -------------------------------------------------------


class RegistryDocOut(BaseModel):
    id: UUID
    doc_type_key: str
    title: str
    stage_key: str
    status: str
    ai_draftable: bool
    reporting_period_id: UUID | None
    current_file_key: str | None
    vault_document_id: UUID | None
    versions: list[dict]
    notes: str | None
    updated_at: datetime


class RegistryDocPatch(BaseModel):
    status: Annotated[str | None, NotNull] = Field(default=None, pattern=DOC_STATUSES)
    notes: str | None = Field(default=None, max_length=NOTES_MAX)
    vault_document_id: UUID | None = None


class DocUploadIn(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    mime: str = Field(max_length=200)
    size_bytes: int = Field(gt=0)


class DocUploadOut(BaseModel):
    upload_url: str
    file_key: str


class DocUploadCompleteIn(BaseModel):
    file_key: str = Field(min_length=1, max_length=1_000)
    note: str | None = Field(default=None, max_length=500)


# -- conditions --------------------------------------------------------------


class ConditionIn(BaseModel):
    number: str = Field(min_length=1, max_length=50)
    description: str = Field(min_length=1, max_length=NOTES_MAX)
    pre_drawdown: bool = False
    due_date: date | None = None
    notes: str | None = Field(default=None, max_length=NOTES_MAX)


class ConditionPatch(BaseModel):
    number: Annotated[str | None, NotNull] = Field(default=None, min_length=1, max_length=50)
    description: Annotated[str | None, NotNull] = Field(
        default=None, min_length=1, max_length=NOTES_MAX
    )
    pre_drawdown: Annotated[bool | None, NotNull] = None
    status: Annotated[str | None, NotNull] = Field(default=None, pattern=CONDITION_STATUSES)
    due_date: date | None = None
    submitted_at: date | None = None
    discharged_at: date | None = None
    notes: str | None = Field(default=None, max_length=NOTES_MAX)


class ConditionOut(BaseModel):
    id: UUID
    number: str
    description: str
    pre_drawdown: bool
    status: str
    due_date: date | None
    submitted_at: date | None
    discharged_at: date | None
    notes: str | None


# -- reporting periods, measures and outcomes --------------------------------


class ReportingPeriodIn(BaseModel):
    label: str = Field(min_length=1, max_length=200)
    period_start: date
    period_end: date
    due_date: date | None = None
    notes: str | None = Field(default=None, max_length=NOTES_MAX)


class ReportingPeriodPatch(BaseModel):
    label: Annotated[str | None, NotNull] = Field(default=None, min_length=1, max_length=200)
    period_start: Annotated[date | None, NotNull] = None
    period_end: Annotated[date | None, NotNull] = None
    due_date: date | None = None
    status: Annotated[str | None, NotNull] = Field(default=None, pattern=PERIOD_STATUSES)
    submitted_at: date | None = None
    accepted_at: date | None = None
    notes: str | None = Field(default=None, max_length=NOTES_MAX)


class ReportingPeriodOut(BaseModel):
    id: UUID
    application_id: UUID
    label: str
    period_start: date
    period_end: date
    due_date: date | None
    status: str
    submitted_at: date | None
    accepted_at: date | None
    notes: str | None
    overdue: bool


class CalendarRow(ReportingPeriodOut):
    """The tenant-wide obligation calendar: every period not yet accepted,
    across every application, with the RAG the funder's deadline implies."""

    application_title: str
    funder_name: str | None
    rag: str


class MeasureIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    definition: str | None = Field(default=None, max_length=NOTES_MAX)
    unit: str = Field(default="count", max_length=50)
    baseline: Decimal | None = Field(default=None, ge=-Decimal("999999999999"))
    target: Decimal | None = Field(default=None, ge=-Decimal("999999999999"))
    notes: str | None = Field(default=None, max_length=NOTES_MAX)


class MeasurePatch(BaseModel):
    name: Annotated[str | None, NotNull] = Field(default=None, min_length=1, max_length=200)
    definition: str | None = Field(default=None, max_length=NOTES_MAX)
    unit: Annotated[str | None, NotNull] = Field(default=None, max_length=50)
    baseline: Decimal | None = Field(default=None, ge=-Decimal("999999999999"))
    target: Decimal | None = Field(default=None, ge=-Decimal("999999999999"))
    notes: str | None = Field(default=None, max_length=NOTES_MAX)


class MeasureOut(BaseModel):
    id: UUID
    name: str
    definition: str | None
    unit: str
    baseline: Decimal | None
    target: Decimal | None
    position: int
    notes: str | None


class OutcomeIn(BaseModel):
    value: Decimal | None = Field(default=None, ge=-Decimal("999999999999"))
    narrative: str | None = Field(default=None, max_length=NOTES_MAX)
    evidence_notes: str | None = Field(default=None, max_length=NOTES_MAX)


class OutcomeOut(BaseModel):
    id: UUID
    measure_id: UUID
    measure_name: str
    unit: str
    target: Decimal | None
    reporting_period_id: UUID
    value: Decimal | None
    narrative: str | None
    evidence_notes: str | None
    recorded_by: UUID | None
    recorded_at: datetime


# -- draft jobs --------------------------------------------------------------

DRAFT_KINDS = (
    "^(case_for_support|funding_application|monitoring_report|impact_evaluation|application_form)$"
)


class DraftIn(BaseModel):
    kind: str = Field(pattern=DRAFT_KINDS)
    #: Required for `monitoring_report` — which obligation the return answers.
    reporting_period_id: UUID | None = None
    #: Required for `application_form` — whose questions are being answered.
    question_set_key: str | None = Field(default=None, max_length=200)
    instructions: str | None = Field(default=None, max_length=2_000)


class DraftJobOut(BaseModel):
    id: UUID
    application_id: UUID
    kind: str
    status: str
    error: str | None
    document_id: UUID | None
    file_key: str | None
    to_confirm_count: int
    llm_calls: int
    tokens_in: int
    tokens_out: int
    cost_usd: float
    created_at: datetime
    updated_at: datetime
    download_url: str | None = None
