"""CRM schemas — module-local to keep the core schemas file lean."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

EMAIL = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


class CompanyIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    website: str | None = Field(default=None, max_length=500)
    email: str | None = Field(default=None, max_length=320, pattern=EMAIL)
    phone: str | None = Field(default=None, max_length=50)
    address_line1: str | None = Field(default=None, max_length=300)
    address_line2: str | None = Field(default=None, max_length=300)
    city: str | None = Field(default=None, max_length=100)
    postcode: str | None = Field(default=None, max_length=20)
    notes: str | None = Field(default=None, max_length=5_000)


class CompanyPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    website: str | None = Field(default=None, max_length=500)
    email: str | None = Field(default=None, max_length=320, pattern=EMAIL)
    phone: str | None = Field(default=None, max_length=50)
    address_line1: str | None = Field(default=None, max_length=300)
    address_line2: str | None = Field(default=None, max_length=300)
    city: str | None = Field(default=None, max_length=100)
    postcode: str | None = Field(default=None, max_length=20)
    notes: str | None = Field(default=None, max_length=5_000)


class CompanyOut(BaseModel):
    id: UUID
    name: str
    website: str | None
    email: str | None
    phone: str | None
    address_line1: str | None
    address_line2: str | None
    city: str | None
    postcode: str | None
    notes: str | None
    contact_count: int
    created_by: UUID | None
    created_at: datetime
    updated_at: datetime


class ContactIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    company_id: UUID | None = None
    job_title: str | None = Field(default=None, max_length=200)
    email: str | None = Field(default=None, max_length=320, pattern=EMAIL)
    phone: str | None = Field(default=None, max_length=50)
    mobile: str | None = Field(default=None, max_length=50)
    address: str | None = Field(default=None, max_length=1_000)
    notes: str | None = Field(default=None, max_length=5_000)
    tags: list[str] = []


class ContactPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    company_id: UUID | None = None
    job_title: str | None = Field(default=None, max_length=200)
    email: str | None = Field(default=None, max_length=320, pattern=EMAIL)
    phone: str | None = Field(default=None, max_length=50)
    mobile: str | None = Field(default=None, max_length=50)
    address: str | None = Field(default=None, max_length=1_000)
    notes: str | None = Field(default=None, max_length=5_000)
    tags: list[str] | None = None


class ContactOut(BaseModel):
    id: UUID
    name: str
    company_id: UUID | None
    company_name: str | None
    job_title: str | None
    email: str | None
    phone: str | None
    mobile: str | None
    address: str | None
    notes: str | None
    tags: list[str]
    project_ids: list[UUID]
    created_by: UUID | None
    created_at: datetime
    updated_at: datetime
