from datetime import datetime
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
    created_at: datetime


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


class ConversationOut(BaseModel):
    id: UUID
    title: str | None
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


class DocumentCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    mime: str
    size_bytes: int = Field(gt=0)


class DocumentOut(BaseModel):
    id: UUID
    title: str
    mime: str | None
    status: str
    error: str | None
    created_by: UUID | None
    created_at: datetime
    updated_at: datetime


class DocumentCreateOut(BaseModel):
    id: UUID
    upload_url: str


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
