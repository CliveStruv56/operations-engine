"""CRM schemas — module-local to keep the core schemas file lean."""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, BeforeValidator, Field

EMAIL = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"

# Field limits the CSV importer mirrors so imported rows stay editable.
NAME_MAX = 200
JOB_TITLE_MAX = 200
EMAIL_MAX = 320
PHONE_MAX = 50
ADDRESS_MAX = 1_000
NOTES_MAX = 5_000


def _reject_null(value: object) -> object:
    """Patch fields are `X | None` to mean "unset", never "set to null".

    The column behind these is NOT NULL, so an explicit null would reach the
    UPDATE and surface as a 500. Defaults skip validation in Pydantic, so this
    fires only when the client actually sends null.
    """
    if value is None:
        raise ValueError("must not be null — omit the field to leave it unchanged")
    return value


NotNull = BeforeValidator(_reject_null)


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
    name: Annotated[str | None, NotNull] = Field(default=None, min_length=1, max_length=200)
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
    name: Annotated[str | None, NotNull] = Field(default=None, min_length=1, max_length=200)
    company_id: UUID | None = None
    job_title: str | None = Field(default=None, max_length=200)
    email: str | None = Field(default=None, max_length=320, pattern=EMAIL)
    phone: str | None = Field(default=None, max_length=50)
    mobile: str | None = Field(default=None, max_length=50)
    address: str | None = Field(default=None, max_length=1_000)
    notes: str | None = Field(default=None, max_length=5_000)
    tags: Annotated[list[str] | None, NotNull] = None


class ImportIn(BaseModel):
    # ~2MB ceiling — thousands of contacts; the row cap is enforced separately.
    csv: str = Field(min_length=1, max_length=2_000_000)


class ImportError_(BaseModel):
    line: int
    reason: str


class ImportOut(BaseModel):
    created: int
    updated: int
    skipped: int
    companies_created: int
    errors: list[ImportError_]


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
