import re
from datetime import date, datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, BeforeValidator, EmailStr, Field, field_validator

from app.modules import FEATURE_FLAGS

_HEX_COLOUR = re.compile(r"^#[0-9a-fA-F]{6}$")


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


class TenantCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class TenantPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    brand: dict[str, Any] | None = None

    @field_validator("brand")
    @classmethod
    def _validate_brand(cls, v: dict[str, Any] | None) -> dict[str, Any] | None:
        # brand feeds CSS variables verbatim — keep garbage out.
        if v is None:
            return v
        accent = v.get("accent")
        if accent is not None and not _HEX_COLOUR.match(str(accent)):
            raise ValueError("brand.accent must be a #rrggbb hex colour")
        for key in ("logo_key", "slides_template_key"):
            if v.get(key) is not None and not isinstance(v[key], str):
                raise ValueError(f"brand.{key} must be a string")
        return v


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
    logo_url: str | None = None


class TenantMeOut(TenantOut):
    role: str


# -- operator console (platform admin) --------------------------------------


def _reject_unknown_flags(v: dict[str, bool]) -> dict[str, bool]:
    """Flags are an allowlist, not free-form jsonb: a typo would otherwise
    persist a key no gate ever reads, looking enabled in the console and
    404ing in the app."""
    unknown = set(v) - FEATURE_FLAGS
    if unknown:
        raise ValueError(f"unknown feature flag(s): {sorted(unknown)}")
    return v


class AdminTenantCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    owner_email: EmailStr
    seats: int | None = Field(default=None, ge=1, le=100)
    trial_days: int | None = Field(default=None, ge=1, le=365)
    features: dict[str, bool] = {}
    brand_accent: str | None = Field(default=None, pattern=r"^#[0-9a-fA-F]{6}$")

    _known_flags = field_validator("features")(_reject_unknown_flags)


class AdminFeaturesIn(BaseModel):
    """Modules to switch on or off for an existing workspace. Merged into
    the tenant's flags, so naming one module never disturbs another; set a
    flag false to switch it off (the gates test `= 'true'`)."""

    features: dict[str, bool] = Field(min_length=1)

    _known_flags = field_validator("features")(_reject_unknown_flags)


class AdminFeaturesOut(BaseModel):
    id: UUID
    features: dict[str, Any]


class AdminTenantPatch(BaseModel):
    """Post-creation edits. Every field optional; only what is sent changes,
    so two operators editing different fields cannot clobber each other."""

    name: str | None = Field(default=None, min_length=1, max_length=200)
    seats: int | None = Field(default=None, ge=1, le=100)
    trial_ends_at: datetime | None = None
    plan: str | None = Field(default=None, pattern="^(trial|core|pro|managed)$")
    brand_accent: str | None = Field(default=None, pattern=r"^#[0-9a-fA-F]{6}$")

    def changes(self) -> dict[str, Any]:
        return self.model_dump(exclude_unset=True)


class AdminTenantOut(BaseModel):
    """The tenant's own columns after an edit or a suspend/resume — the
    console refetches the fleet listing for the derived counts."""

    id: UUID
    name: str
    plan: str
    seats: int
    trial_ends_at: datetime | None
    features: dict[str, Any]
    brand: dict[str, Any]
    suspended_at: datetime | None
    suspended_reason: str | None


class AdminSuspendIn(BaseModel):
    """Reason is required on suspend so the fleet listing can say why — an
    unexplained dark workspace is worse than no suspension at all."""

    reason: str = Field(min_length=1, max_length=300)


class AdminPurgeIn(BaseModel):
    """The workspace's exact name, typed — the same confirmation GitHub asks
    for before deleting a repository, and for the same reason."""

    confirm_name: str = Field(min_length=1, max_length=200)


class AdminPurgeOut(BaseModel):
    objects_deleted: int
    key_revoked: bool


class AdminInviteOut(BaseModel):
    token: str
    email: str
    role: str
    expires_at: datetime
    email_sent: bool = False


class AdminTenantCreatedOut(BaseModel):
    id: UUID
    name: str
    seats: int
    trial_ends_at: datetime | None
    features: dict[str, Any]
    brand: dict[str, Any]
    invite: AdminInviteOut


class AdminOwnerInviteIn(BaseModel):
    email: EmailStr


class AdminTenantRow(BaseModel):
    id: UUID
    name: str
    plan: str
    seats: int
    trial_ends_at: datetime | None
    created_at: datetime
    features: dict[str, Any]
    brand: dict[str, Any] = {}
    suspended_at: datetime | None = None
    suspended_reason: str | None = None
    member_count: int
    pending_invites: int
    month_cost_usd: float
    month_requests: int


class MemberOut(BaseModel):
    id: UUID
    user_id: UUID
    role: str
    email: str | None = None
    created_at: datetime
    #: Read-only here: the digest preference belongs to the recipient and is
    #: changed only through the signed link in the digest itself.
    digest_opt_out: bool = False


class MemberRolePatch(BaseModel):
    role: str = Field(pattern="^(owner|admin|member)$")


class MemberRemoveOut(BaseModel):
    """What removing somebody left behind.

    Removal used to answer 204, which is honest for the membership and silent
    about everything the person was responsible for. The claims they owned are
    released rather than deleted — still true, just nobody's — and the moment
    an admin is removing them is the only moment they can hand those facts to
    somebody else. So the count comes back, rather than only into `audit_log`.
    """

    claims_disowned: int


class LogoUploadIn(BaseModel):
    mime: str
    size_bytes: int = Field(gt=0)


class LogoUploadOut(BaseModel):
    upload_url: str
    logo_key: str


class SlidesTemplateUploadOut(BaseModel):
    upload_url: str
    template_key: str


class InviteCreate(BaseModel):
    email: EmailStr
    role: str = Field(default="member", pattern="^(admin|member)$")


class InviteOut(BaseModel):
    id: UUID
    email: str
    role: str
    token: str
    expires_at: datetime
    #: Whether the invite notification actually went out — False when email is
    #: not configured or Resend refused it, in which case the UI says "copy
    #: the link" instead of pretending.
    email_sent: bool = False


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
    # Defaults keep create/patch paths (which return the bare row) valid;
    # the list/search queries compute is_mine and join owner_email.
    visibility: str = "private"
    is_mine: bool = True
    owner_email: str | None = None
    created_at: datetime
    updated_at: datetime


class ConversationPatch(BaseModel):
    visibility: str = Field(pattern="^(private|tenant)$")


class ActivityFeedItem(BaseModel):
    action: str
    actor_email: str | None
    target_type: str | None
    target_id: str | None
    target_title: str | None
    meta: dict[str, Any] = {}
    created_at: datetime


class MessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=200_000)
    task_kind: str | None = Field(
        default=None, pattern="^(chat|analyse|report|financial|slides|research)$"
    )
    use_vault: bool = True


class Citation(BaseModel):
    n: int
    chunk_id: UUID
    document_id: UUID
    title: str
    page_start: int | None
    page_end: int | None
    snippet: str
    # Web-search citations; defaults keep pre-existing rows valid.
    url: str | None = None
    source_type: str = "vault"


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


class SlidesExportOut(BaseModel):
    download_url: str
    filename: str
    slide_count: int


class PlanTaskSeed(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    details: str | None = Field(default=None, max_length=2_000)
    due_date: date | None = None
    assignee_membership_id: UUID | None = None


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2_000)
    kind: Literal["blank", "planned"] = "blank"
    tasks: list[PlanTaskSeed] = Field(default_factory=list, max_length=20)


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2_000)
    archived: bool | None = None
    has_plan: bool | None = None


class ProjectOut(BaseModel):
    id: UUID
    name: str
    description: str | None
    archived: bool
    has_plan: bool = False
    created_at: datetime
    updated_at: datetime
    document_count: int = 0
    is_development: bool = False
    open_task_count: int = 0


class PlanTaskIn(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    details: str | None = Field(default=None, max_length=2_000)
    due_date: date | None = None
    assignee_membership_id: UUID | None = None


class PlanTaskPatch(BaseModel):
    title: Annotated[str | None, NotNull] = Field(default=None, min_length=1, max_length=300)
    details: str | None = Field(default=None, max_length=2_000)
    due_date: date | None = None
    assignee_membership_id: UUID | None = None
    status: Annotated[str | None, NotNull] = Field(default=None, pattern="^(todo|doing|done)$")
    position: Annotated[int | None, NotNull] = None


class PlanTaskOut(BaseModel):
    id: UUID
    project_id: UUID
    title: str
    details: str | None
    status: str
    due_date: date | None
    assignee_membership_id: UUID | None
    assignee_email: str | None = None
    position: int
    completed_at: datetime | None
    created_at: datetime


class DocumentCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    mime: str
    size_bytes: int = Field(gt=0)
    project_id: UUID | None = None
    #: Set when the file was dropped into a chat: retrieval boosts it for
    #: that conversation. Must be a conversation the caller owns.
    conversation_id: UUID | None = None


class DocumentUpdate(BaseModel):
    # Sentinel-free: PATCH sends the full desired assignment each time.
    project_id: UUID | None = None
    is_primary: bool | None = None


class DocumentOut(BaseModel):
    id: UUID
    title: str
    mime: str | None
    project_id: UUID | None
    conversation_id: UUID | None = None
    is_primary: bool
    summary: str | None
    status: str
    error: str | None
    created_by: UUID | None
    created_at: datetime
    updated_at: datetime
    #: False for seeded notes (the planned-project brief): there is no stored
    #: file, so Open and Re-index have nothing to work on.
    has_source: bool = False


class DocumentCreateOut(BaseModel):
    id: UUID
    upload_url: str


class DocumentDownloadOut(BaseModel):
    download_url: str


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


class ContactHit(BaseModel):
    """⌘K search row for a CRM contact — list shape only, not the full record."""

    id: UUID
    name: str
    job_title: str | None
    company_name: str | None
    email: str | None


class SearchResultsOut(BaseModel):
    conversations: list[ConversationOut]
    documents: list[DocumentOut]
    contacts: list[ContactHit]


class UsageSummaryOut(BaseModel):
    month: str
    tokens_in: int
    tokens_out: int
    cost_usd: float
    requests: int
    by_user: list[UsageBucket]
    by_model: list[UsageBucket]
