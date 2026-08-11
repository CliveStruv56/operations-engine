"""Groundwork W2 schemas — module-local to keep the core schemas file lean."""

from datetime import date, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

STAGE_KEYS = "^(group|site|plan|build|live)$"


class GroundworkDetail(BaseModel):
    id: UUID
    name: str
    client_org: str | None
    project_type: str
    delivery_route: str | None
    status: str
    dormancy_reason: str | None
    stage_current: str
    site_address: str | None
    homes_planned: int | None
    start_date: date | None
    target_completion: date | None
    applicability: dict[str, Any]
    contract_facts: dict[str, Any]
    updated_at: datetime


class GroundworkPatch(BaseModel):
    client_org: str | None = Field(default=None, max_length=200)
    delivery_route: str | None = Field(
        default=None, pattern="^(direct|ha_partnership|council_enabled)$"
    )
    homes_planned: int | None = Field(default=None, gt=0)
    start_date: date | None = None
    target_completion: date | None = None
    site_address: str | None = Field(default=None, max_length=500)
    applicability: dict[str, Any] | None = None
    contract_facts: dict[str, Any] | None = None


class GateItem(BaseModel):
    id: str
    criterion: str
    kind: str
    ref: str | None = None
    done: bool
    done_by: UUID | None = None
    done_at: datetime | None = None
    note: str | None = None


class StageOut(BaseModel):
    id: UUID
    stage_key: str
    label: str
    riba_ref: str | None
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


class TaskIn(BaseModel):
    stage_key: str = Field(pattern=STAGE_KEYS)
    title: str = Field(min_length=1, max_length=300)
    details: str | None = Field(default=None, max_length=2_000)
    owner_name: str | None = Field(default=None, max_length=200)
    due_date: date | None = None
    is_milestone: bool = False
    tags: list[str] = []


class TaskPatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=300)
    details: str | None = Field(default=None, max_length=2_000)
    owner_name: str | None = Field(default=None, max_length=200)
    due_date: date | None = None
    is_milestone: bool | None = None
    tags: list[str] | None = None
    status: str | None = Field(default=None, pattern="^(todo|doing|done|na)$")
    stage_key: str | None = Field(default=None, pattern=STAGE_KEYS)


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


class BulkCompleteIn(BaseModel):
    ids: list[UUID] = Field(min_length=1)


class ModuleDocOut(BaseModel):
    id: UUID
    doc_type_key: str
    title: str
    stage_key: str
    status: str
    ai_draftable: bool
    current_file_key: str | None
    vault_document_id: UUID | None
    versions: list[dict[str, Any]]
    notes: str | None
    updated_at: datetime


class ModuleDocPatch(BaseModel):
    status: str | None = Field(
        default=None, pattern="^(required|drafting|review|final|submitted|na)$"
    )
    notes: str | None = Field(default=None, max_length=2_000)
    vault_document_id: UUID | None = None


class DocUploadIn(BaseModel):
    filename: str = Field(min_length=1, max_length=300)
    mime: str
    size_bytes: int = Field(gt=0)


class DocUploadOut(BaseModel):
    upload_url: str
    file_key: str


class DocUploadCompleteIn(BaseModel):
    file_key: str
    note: str | None = Field(default=None, max_length=500)


class BudgetLineIn(BaseModel):
    category: str = Field(
        pattern="^(land|construction|externals|abnormals|fees|statutory|contingency|finance|other)$"
    )
    label: str = Field(min_length=1, max_length=200)
    budget: float = 0
    forecast: float = 0
    actual: float = 0
    note: str | None = Field(default=None, max_length=500)


class BudgetOut(BaseModel):
    lines: list[dict[str, Any]]
    totals: dict[str, float]  # budget / forecast / actual / variance


class FundingIn(BaseModel):
    programme_key: str | None = None
    name: str = Field(min_length=1, max_length=300)
    funder: str | None = Field(default=None, max_length=200)
    kind: str = Field(pattern="^(grant|loan|shares|equity_match|s106|other)$")
    amount_sought: float | None = None
    amount_secured: float | None = None
    status: str = Field(
        default="identified",
        pattern="^(identified|applying|offered|secured|drawing|complete|declined)$",
    )
    conditions: str | None = Field(default=None, max_length=2_000)
    drawdown_schedule: list[dict[str, Any]] = []
    notes: str | None = Field(default=None, max_length=2_000)


class FundingPatch(BaseModel):
    programme_key: str | None = None
    name: str | None = Field(default=None, min_length=1, max_length=300)
    funder: str | None = Field(default=None, max_length=200)
    kind: str | None = Field(default=None, pattern="^(grant|loan|shares|equity_match|s106|other)$")
    amount_sought: float | None = None
    amount_secured: float | None = None
    status: str | None = Field(
        default=None,
        pattern="^(identified|applying|offered|secured|drawing|complete|declined)$",
    )
    conditions: str | None = Field(default=None, max_length=2_000)
    drawdown_schedule: list[dict[str, Any]] | None = None
    notes: str | None = Field(default=None, max_length=2_000)


class ProgrammeOut(BaseModel):
    key: str
    name: str
    funder: str
    nations: list[str]
    kind: str
    stage_fit: list[str]
    amount_note: str | None
    match_note: str | None
    eligibility: str
    status: str
    route_url: str | None
    docs_required: list[str]
    last_verified: date
    next_review: date
    notes: str | None
    stale: bool


class RiskIn(BaseModel):
    category: str = Field(min_length=1, max_length=100)
    description: str = Field(min_length=1, max_length=1_000)
    likelihood: int = Field(ge=1, le=5)
    impact: int = Field(ge=1, le=5)
    owner_name: str | None = Field(default=None, max_length=200)
    mitigation: str | None = Field(default=None, max_length=1_000)
    review_date: date | None = None


class RiskPatch(BaseModel):
    category: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, min_length=1, max_length=1_000)
    likelihood: int | None = Field(default=None, ge=1, le=5)
    impact: int | None = Field(default=None, ge=1, le=5)
    owner_name: str | None = Field(default=None, max_length=200)
    mitigation: str | None = Field(default=None, max_length=1_000)
    status: str | None = Field(default=None, pattern="^(open|monitoring|closed)$")
    review_date: date | None = None


class ConditionIn(BaseModel):
    application_ref: str | None = Field(default=None, max_length=100)
    number: str = Field(min_length=1, max_length=50)
    description: str = Field(min_length=1, max_length=2_000)
    pre_commencement: bool = False


class ConditionPatch(BaseModel):
    application_ref: str | None = Field(default=None, max_length=100)
    number: str | None = Field(default=None, min_length=1, max_length=50)
    description: str | None = Field(default=None, min_length=1, max_length=2_000)
    pre_commencement: bool | None = None
    status: str | None = Field(
        default=None,
        pattern="^(outstanding|submitted|discharged|partially_discharged|na)$",
    )
    submitted_at: date | None = None
    discharged_at: date | None = None
    notes: str | None = Field(default=None, max_length=1_000)


class StakeholderIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    org: str | None = Field(default=None, max_length=200)
    role: str = Field(pattern="^(lpa|landowner|funder|contractor|consultant|community|other)$")
    email: str | None = Field(default=None, max_length=320)
    phone: str | None = Field(default=None, max_length=50)
    notes: str | None = Field(default=None, max_length=1_000)
    last_contact: date | None = None


class StakeholderPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    org: str | None = Field(default=None, max_length=200)
    role: str | None = Field(
        default=None, pattern="^(lpa|landowner|funder|contractor|consultant|community|other)$"
    )
    email: str | None = Field(default=None, max_length=320)
    phone: str | None = Field(default=None, max_length=50)
    notes: str | None = Field(default=None, max_length=1_000)
    last_contact: date | None = None


class ActivityOut(BaseModel):
    action: str
    user_id: UUID | None
    created_at: datetime


class DraftIn(BaseModel):
    kind: str = Field(pattern="^(monthly_report|feasibility_study|funding_bid|application_form)$")
    # monthly_report: reporting period; required for that kind.
    month: str | None = Field(default=None, pattern="^\\d{4}-(0[1-9]|1[0-2])$")
    # funding_bid: the project funding source the bid targets; required there.
    funding_source_id: UUID | None = None
    # application_form: which funder's questions to answer; required there.
    question_set_key: str | None = Field(default=None, max_length=200)
    # feasibility_study: optional free-text brief.
    instructions: str | None = Field(default=None, max_length=2_000)


class DraftJobOut(BaseModel):
    id: UUID
    project_id: UUID
    kind: str
    status: str
    error: str | None
    document_id: UUID | None
    download_url: str | None = None
    to_confirm_count: int
    llm_calls: int
    cost_usd: float
    created_at: datetime
    updated_at: datetime
