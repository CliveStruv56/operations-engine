"""Funders: the tenant's own funder records, plus the platform catalogue.

The two are deliberately separate. `grant_funders` is who this charity has a
relationship with; `grant_ref_funders` is the maintained catalogue of real UK
funders, and a tenant row points at it by `ref_key` rather than by foreign
key so retiring a catalogue row cannot erase the tenant's history of having
applied to it.
"""

from datetime import date
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, Query

from app.audit import write_audit
from app.errors import ApiError
from app.grants.schemas import CatalogueRow, FunderIn, FunderOut, FunderPatch
from app.routers.grants.common import require_grants
from app.sqlutil import like_contains, patch_sets
from app.tenant import TenantContext, get_conn

router = APIRouter()

_SELECT = """
select f.*, (select count(*) from grant_applications a where a.funder_id = f.id)
             as application_count
from grant_funders f
"""


@router.get("/grants/funders", response_model=list[FunderOut])
async def list_funders(
    q: str | None = None,
    relationship: str | None = Query(default=None, max_length=20),
    ctx: TenantContext = Depends(require_grants),
    conn: asyncpg.Connection = Depends(get_conn),
):
    clauses: list[str] = []
    params: list[object] = []
    if q:
        params.append(like_contains(q))
        clauses.append(f"(f.name ilike ${len(params)} or f.contact_name ilike ${len(params)})")
    if relationship:
        params.append(relationship)
        clauses.append(f"f.relationship = ${len(params)}")
    where = f"where {' and '.join(clauses)}" if clauses else ""
    rows = await conn.fetch(f"{_SELECT} {where} order by f.name", *params)
    return [dict(r) for r in rows]


@router.post("/grants/funders", status_code=201, response_model=FunderOut)
async def create_funder(
    body: FunderIn,
    ctx: TenantContext = Depends(require_grants),
    conn: asyncpg.Connection = Depends(get_conn),
):
    row = await conn.fetchrow(
        """
        insert into grant_funders (tenant_id, ref_key, name, kind, website, contact_name,
                                   contact_email, relationship, notes, created_by)
        values ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10) returning id
        """,
        ctx.tenant_id,
        body.ref_key,
        body.name,
        body.kind,
        body.website,
        body.contact_name,
        body.contact_email,
        body.relationship,
        body.notes,
        ctx.user_id,
    )
    await write_audit(
        conn, ctx.tenant_id, ctx.user_id, "grants.funder_create", "grant_funder", str(row["id"])
    )
    return await _funder_out(conn, row["id"])


@router.get("/grants/funder-catalogue", response_model=list[CatalogueRow])
async def funder_catalogue(
    q: str | None = None,
    nation: str | None = Query(default=None, max_length=20),
    ctx: TenantContext = Depends(require_grants),
    conn: asyncpg.Connection = Depends(get_conn),
):
    """The maintained catalogue. `stale` is computed here rather than stored
    so a row goes stale on the day it is due, not the day someone re-runs a
    job — the badge is load-bearing, because a stale row also warns inside
    any draft it parameterised."""
    clauses: list[str] = []
    params: list[object] = []
    if q:
        params.append(like_contains(q))
        clauses.append(
            f"(name ilike ${len(params)} or funder ilike ${len(params)}"
            f" or eligibility ilike ${len(params)})"
        )
    if nation:
        params.append(nation)
        clauses.append(f"${len(params)} = any(nations)")
    where = f"where {' and '.join(clauses)}" if clauses else ""
    rows = await conn.fetch(f"select * from grant_ref_funders {where} order by name", *params)
    today = date.today()
    return [{**dict(r), "stale": r["next_review"] < today} for r in rows]


@router.get("/grants/funders/{funder_id}", response_model=FunderOut)
async def get_funder(
    funder_id: UUID,
    ctx: TenantContext = Depends(require_grants),
    conn: asyncpg.Connection = Depends(get_conn),
):
    return await _funder_out(conn, funder_id)


@router.patch("/grants/funders/{funder_id}", response_model=FunderOut)
async def patch_funder(
    funder_id: UUID,
    body: FunderPatch,
    ctx: TenantContext = Depends(require_grants),
    conn: asyncpg.Connection = Depends(get_conn),
):
    updates = body.model_dump(exclude_unset=True)
    if not updates:
        raise ApiError(400, "no_changes", "Nothing to update")
    sets, values = patch_sets("grant_funders", updates)
    row = await conn.fetchrow(
        f"update grant_funders set {sets}, updated_at = now() where id = $1 returning id",
        funder_id,
        *values,
    )
    if row is None:
        raise ApiError(404, "not_found", "Funder not found")
    await write_audit(
        conn, ctx.tenant_id, ctx.user_id, "grants.funder_update", "grant_funder", str(funder_id)
    )
    return await _funder_out(conn, funder_id)


@router.delete("/grants/funders/{funder_id}", status_code=204)
async def delete_funder(
    funder_id: UUID,
    ctx: TenantContext = Depends(require_grants),
    conn: asyncpg.Connection = Depends(get_conn),
):
    """Applications keep their history: the FK is `on delete set null`, so
    deleting a funder detaches its bids rather than deleting them."""
    deleted = await conn.execute("delete from grant_funders where id = $1", funder_id)
    if deleted == "DELETE 0":
        raise ApiError(404, "not_found", "Funder not found")
    await write_audit(
        conn, ctx.tenant_id, ctx.user_id, "grants.funder_delete", "grant_funder", str(funder_id)
    )


async def _funder_out(conn: asyncpg.Connection, funder_id: UUID) -> dict:
    row = await conn.fetchrow(f"{_SELECT} where f.id = $1", funder_id)
    if row is None:
        raise ApiError(404, "not_found", "Funder not found")
    return dict(row)
