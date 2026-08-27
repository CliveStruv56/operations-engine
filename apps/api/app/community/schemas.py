"""Community module schemas — module-local, per the schema-location rule.

One profile, one asset table, one statistics table. The asset `attributes`
jsonb is the deliberate escape hatch for per-category detail (pupil counts,
ferry frequency, broadband speed): scalars only, bounded, because it renders
on a card and feeds a prompt — it is not a place to smuggle documents.
"""

from datetime import date, datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, BeforeValidator, Field, field_validator

Category = Literal[
    "transport",
    "education",
    "health",
    "housing",
    "retail_services",
    "community_spaces",
    "energy",
    "employment",
    "other",
]
AssetStatus = Literal["open", "closed", "seasonal", "planned"]

ATTRIBUTES_MAX_KEYS = 40
ATTRIBUTE_KEY_MAX = 60
ATTRIBUTE_VALUE_MAX = 500


def _reject_null(value: object) -> object:
    """Patch fields are `X | None` to mean "unset", never "set to null".

    Same contract as the CRM: the column behind these is NOT NULL, so an
    explicit null would reach the UPDATE and surface as a 500.
    """
    if value is None:
        raise ValueError("must not be null — omit the field to leave it unchanged")
    return value


NotNull = BeforeValidator(_reject_null)


def _check_attributes(value: dict[str, str | int | float | bool]) -> dict:
    if len(value) > ATTRIBUTES_MAX_KEYS:
        raise ValueError(f"at most {ATTRIBUTES_MAX_KEYS} attributes")
    for key, item in value.items():
        if not key or len(key) > ATTRIBUTE_KEY_MAX:
            raise ValueError(f"attribute names must be 1–{ATTRIBUTE_KEY_MAX} characters")
        if isinstance(item, str) and len(item) > ATTRIBUTE_VALUE_MAX:
            raise ValueError(f"attribute values must be at most {ATTRIBUTE_VALUE_MAX} characters")
    return value


class ProfileIn(BaseModel):
    place_name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5_000)
    geography_note: str | None = Field(default=None, max_length=2_000)
    council_area: str | None = Field(default=None, max_length=200)
    settlements: list[str] = Field(default=[], max_length=50)
    census_area_codes: list[str] = Field(default=[], max_length=50)
    data_sources_note: str | None = Field(default=None, max_length=2_000)

    @field_validator("settlements", "census_area_codes")
    @classmethod
    def _short_items(cls, value: list[str]) -> list[str]:
        for item in value:
            if not item or len(item) > 100:
                raise ValueError("entries must be 1–100 characters")
        return value


class ProfileOut(ProfileIn):
    id: UUID
    created_by: UUID | None
    created_at: datetime
    updated_at: datetime


class AssetIn(BaseModel):
    category: Category
    subcategory: str | None = Field(default=None, max_length=100)
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5_000)
    attributes: dict[str, str | int | float | bool] = {}
    status: AssetStatus = "open"
    settlement: str | None = Field(default=None, max_length=100)
    contact: str | None = Field(default=None, max_length=500)
    url: str | None = Field(default=None, max_length=500)
    notes: str | None = Field(default=None, max_length=5_000)

    @field_validator("attributes")
    @classmethod
    def _attributes(cls, value: dict) -> dict:
        return _check_attributes(value)


class AssetPatch(BaseModel):
    category: Annotated[Category | None, NotNull] = None
    subcategory: str | None = Field(default=None, max_length=100)
    name: Annotated[str | None, NotNull] = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5_000)
    attributes: Annotated[dict[str, str | int | float | bool] | None, NotNull] = None
    status: Annotated[AssetStatus | None, NotNull] = None
    settlement: str | None = Field(default=None, max_length=100)
    contact: str | None = Field(default=None, max_length=500)
    url: str | None = Field(default=None, max_length=500)
    notes: str | None = Field(default=None, max_length=5_000)

    @field_validator("attributes")
    @classmethod
    def _attributes(cls, value: dict | None) -> dict | None:
        return None if value is None else _check_attributes(value)


class AssetOut(BaseModel):
    id: UUID
    category: Category
    subcategory: str | None
    name: str
    description: str | None
    attributes: dict[str, str | int | float | bool]
    status: AssetStatus
    settlement: str | None
    contact: str | None
    url: str | None
    notes: str | None
    created_by: UUID | None
    created_at: datetime
    updated_at: datetime


class StatIn(BaseModel):
    label: str = Field(min_length=1, max_length=200)
    value: float
    unit: str | None = Field(default=None, max_length=50)
    period: str | None = Field(default=None, max_length=50)
    as_of: date | None = None
    claim_kind: str | None = Field(default=None, max_length=100)
    source: str | None = Field(default=None, max_length=300)
    source_url: str | None = Field(default=None, max_length=500)
    notes: str | None = Field(default=None, max_length=5_000)


class StatPatch(BaseModel):
    label: Annotated[str | None, NotNull] = Field(default=None, min_length=1, max_length=200)
    value: Annotated[float | None, NotNull] = None
    unit: str | None = Field(default=None, max_length=50)
    period: str | None = Field(default=None, max_length=50)
    as_of: date | None = None
    claim_kind: str | None = Field(default=None, max_length=100)
    source: str | None = Field(default=None, max_length=300)
    source_url: str | None = Field(default=None, max_length=500)
    notes: str | None = Field(default=None, max_length=5_000)


class StatOut(BaseModel):
    id: UUID
    label: str
    value: float
    unit: str | None
    period: str | None
    as_of: date | None
    claim_kind: str | None
    source: str | None
    source_url: str | None
    notes: str | None
    #: The register claim this save asserted — present only on a write that
    #: fed the register, so the UI can say so without a second request.
    claim_id: UUID | None = None
    created_by: UUID | None
    created_at: datetime
    updated_at: datetime
