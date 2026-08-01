from datetime import date, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class TenantCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class TenantPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    brand: dict[str, Any] | None = None


class TenantOut(BaseModel):
    id: UUID
    name: str
    plan: str
    seats: int
    brand: dict[str, Any]
    features: dict[str, Any]
    model_mode: str
    trial_ends_at: datetime | None
    created_at: datetime


class TenantMeOut(TenantOut):
    role: str


class MemberOut(BaseModel):
    id: UUID
    user_id: UUID
    role: str
    email: str | None = None
    created_at: datetime


class MemberRolePatch(BaseModel):
    role: str = Field(pattern="^(owner|admin|member)$")


class InviteCreate(BaseModel):
    email: EmailStr
    role: str = Field(default="member", pattern="^(admin|member)$")


class InviteOut(BaseModel):
    id: UUID
    email: str
    role: str
    token: str
    expires_at: datetime


class InviteAccept(BaseModel):
    token: str


class InviteAcceptOut(BaseModel):
    tenant_id: UUID
    role: str


class ConversationCreate(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    project_id: UUID | None = None


class ConversationOut(BaseModel):
    id: UUID
    title: str | None
    project_id: UUID | None
    created_at: datetime
    updated_at: datetime


class MessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=200_000)
    task_kind: str | None = Field(default=None, pattern="^(chat|analyse|report|financial)$")
    use_vault: bool = True


class Citation(BaseModel):
    n: int
    chunk_id: UUID
    document_id: UUID
    title: str
    page_start: int | None
    page_end: int | None
    snippet: str


class MessageOut(BaseModel):
    id: UUID
    conversation_id: UUID
    role: str
    content: str
    citations: list[Citation]
    model: str | None
    tokens_in: int | None
    tokens_out: int | None
    cost_usd: float | None
    created_at: datetime


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2_000)


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2_000)
    archived: bool | None = None


class ProjectOut(BaseModel):
    id: UUID
    name: str
    description: str | None
    archived: bool
    created_at: datetime
    updated_at: datetime
    document_count: int = 0
    is_development: bool = False


class DocumentCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    mime: str
    size_bytes: int = Field(gt=0)
    project_id: UUID | None = None


class DocumentUpdate(BaseModel):
    # Sentinel-free: PATCH sends the full desired assignment each time.
    project_id: UUID | None = None
    is_primary: bool | None = None


class DocumentOut(BaseModel):
    id: UUID
    title: str
    mime: str | None
    project_id: UUID | None
    is_primary: bool
    summary: str | None
    status: str
    error: str | None
    created_by: UUID | None
    created_at: datetime
    updated_at: datetime


class DocumentCreateOut(BaseModel):
    id: UUID
    upload_url: str


class GroundworkApplicability(BaseModel):
    wales: bool = False
    hrb: bool = False
    bng_exempt: bool = False
    conservation_area: bool = False


class GroundworkSetup(BaseModel):
    client_org: str | None = Field(default=None, max_length=200)
    delivery_route: str | None = Field(
        default=None, pattern="^(direct|ha_partnership|council_enabled)$"
    )
    homes_planned: int | None = Field(default=None, gt=0)
    start_date: date | None = None
    target_completion: date | None = None
    site_address: str | None = Field(default=None, max_length=500)
    applicability: GroundworkApplicability = GroundworkApplicability()


class GroundworkSetupOut(BaseModel):
    project_id: UUID
    stage_current: str
    seeded: dict[str, int]


class GroundworkStatusIn(BaseModel):
    status: str = Field(pattern="^(active|dormant|complete|archived)$")
    dormancy_reason: str | None = Field(default=None, max_length=200)


class RagOut(BaseModel):
    programme: str
    cost: str
    risk: str


class NextMilestone(BaseModel):
    title: str
    due_date: date


class PortfolioRow(BaseModel):
    id: UUID
    name: str
    client_org: str | None
    status: str
    dormancy_reason: str | None
    stage_current: str
    homes_planned: int | None
    target_completion: date | None
    rag: RagOut
    next_milestone: NextMilestone | None
    open_risks: int
    outstanding_pre_commencement: int
    overdue_tasks: int
    updated_at: datetime


class VaultSearchIn(BaseModel):
    query: str = Field(min_length=1, max_length=2_000)


class VaultSearchHit(BaseModel):
    chunk_id: UUID
    document_id: UUID
    title: str
    heading_path: list[str]
    page_start: int | None
    page_end: int | None
    content: str
    score: float


class UsageBucket(BaseModel):
    key: str
    tokens_in: int
    tokens_out: int
    cost_usd: float
    requests: int


class UsageSummaryOut(BaseModel):
    month: str
    tokens_in: int
    tokens_out: int
    cost_usd: float
    requests: int
    by_user: list[UsageBucket]
    by_model: list[UsageBucket]
