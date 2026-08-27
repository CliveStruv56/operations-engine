"""The place itself: one profile row per tenant, upserted whole.

PUT rather than POST/PATCH because the profile is a singleton — "create" and
"edit" are the same act, and the form always submits every field it shows.
GET returns null rather than 404 when no profile exists yet: the module is
enabled and the resource is reachable, it is simply not written yet, which is
a state the page renders (an empty-state card), not an error.
"""

import asyncpg
from fastapi import APIRouter, Depends

from app.audit import write_audit
from app.community.schemas import ProfileIn, ProfileOut
from app.routers.community.common import require_community
from app.tenant import TenantContext, get_conn

router = APIRouter()

_FIELDS = (
    "id, place_name, description, geography_note, council_area, settlements,"
    " census_area_codes, data_sources_note, created_by, created_at, updated_at"
)


@router.get("/community/profile", response_model=ProfileOut | None)
async def get_profile(
    ctx: TenantContext = Depends(require_community),
    conn: asyncpg.Connection = Depends(get_conn),
):
    row = await conn.fetchrow(f"select {_FIELDS} from community_profile")
    return None if row is None else dict(row)


@router.put("/community/profile", response_model=ProfileOut)
async def put_profile(
    body: ProfileIn,
    ctx: TenantContext = Depends(require_community),
    conn: asyncpg.Connection = Depends(get_conn),
):
    row = await conn.fetchrow(
        f"""
        insert into community_profile (tenant_id, place_name, description, geography_note,
            council_area, settlements, census_area_codes, data_sources_note, created_by)
        values ($1, $2, $3, $4, $5, $6, $7, $8, $9)
        on conflict (tenant_id) do update set
            place_name = excluded.place_name,
            description = excluded.description,
            geography_note = excluded.geography_note,
            council_area = excluded.council_area,
            settlements = excluded.settlements,
            census_area_codes = excluded.census_area_codes,
            data_sources_note = excluded.data_sources_note,
            updated_at = now()
        returning {_FIELDS}
        """,
        ctx.tenant_id,
        body.place_name,
        body.description,
        body.geography_note,
        body.council_area,
        body.settlements,
        body.census_area_codes,
        body.data_sources_note,
        ctx.user_id,
    )
    await write_audit(
        conn, ctx.tenant_id, ctx.user_id, "community.profile_update", "profile", str(row["id"])
    )
    return dict(row)
