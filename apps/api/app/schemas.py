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
