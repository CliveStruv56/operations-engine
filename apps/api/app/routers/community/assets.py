"""Community assets: every facility the place has, in one table.

The `attributes` jsonb carries the per-category detail (pupil counts, ferry
frequency); asyncpg has no jsonb codec registered, so it is dumped on the way
in and loaded on the way out, same as `tenants.brand`.
"""

import json
from typing import Any
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, Query

from app.audit import write_audit
from app.community.schemas import AssetIn, AssetOut, AssetPatch, Category
from app.errors import ApiError
from app.routers.community.common import require_community
from app.sqlutil import like_contains, patch_sets
from app.tenant import TenantContext, get_conn

router = APIRouter()

_FIELDS = (
    "id, category, subcategory, name, description, attributes, status,"
    " settlement, contact, url, notes, created_by, created_at, updated_at"
)


def _out(row: asyncpg.Record) -> dict[str, Any]:
    out = dict(row)
    if isinstance(out["attributes"], str):
        out["attributes"] = json.loads(out["attributes"])
    return out


@router.get("/community/assets", response_model=list[AssetOut])
async def list_assets(
    category: Category | None = None,
    settlement: str | None = None,
    q: str | None = None,
    # No default cap for the same reason as the contact book: the profile page
    # wants every row, and a silent truncation reads as "the shop closed".
    limit: int | None = Query(default=None, ge=1, le=200),
    ctx: TenantContext = Depends(require_community),
    conn: asyncpg.Connection = Depends(get_conn),
):
    clauses: list[str] = []
    params: list[object] = []
    if category:
        params.append(category)
        clauses.append(f"category = ${len(params)}")
    if settlement:
        params.append(settlement)
        clauses.append(f"settlement = ${len(params)}")
    if q:
        params.append(like_contains(q))
        n = len(params)
        clauses.append(f"(name ilike ${n} or subcategory ilike ${n} or description ilike ${n})")
    where = f"where {' and '.join(clauses)}" if clauses else ""
    bound = ""
    if limit is not None:
        params.append(limit)
        bound = f"limit ${len(params)}"
    rows = await conn.fetch(
        f"select {_FIELDS} from community_assets {where} order by category, name {bound}",
        *params,
    )
    return [_out(r) for r in rows]


@router.post("/community/assets", status_code=201, response_model=AssetOut)
async def create_asset(
    body: AssetIn,
    ctx: TenantContext = Depends(require_community),
    conn: asyncpg.Connection = Depends(get_conn),
):
    row = await conn.fetchrow(
        f"""
        insert into community_assets (tenant_id, category, subcategory, name, description,
            attributes, status, settlement, contact, url, notes, created_by)
        values ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
        returning {_FIELDS}
        """,
        ctx.tenant_id,
        body.category,
        body.subcategory,
        body.name,
        body.description,
        json.dumps(body.attributes),
        body.status,
        body.settlement,
        body.contact,
        body.url,
        body.notes,
        ctx.user_id,
    )
    await write_audit(
        conn, ctx.tenant_id, ctx.user_id, "community.asset_create", "asset", str(row["id"])
    )
    return _out(row)


@router.get("/community/assets/{asset_id}", response_model=AssetOut)
async def get_asset(
    asset_id: UUID,
    ctx: TenantContext = Depends(require_community),
    conn: asyncpg.Connection = Depends(get_conn),
):
    row = await conn.fetchrow(f"select {_FIELDS} from community_assets where id = $1", asset_id)
    if row is None:
        raise ApiError(404, "not_found", "Asset not found")
    return _out(row)


@router.patch("/community/assets/{asset_id}", response_model=AssetOut)
async def patch_asset(
    asset_id: UUID,
    body: AssetPatch,
    ctx: TenantContext = Depends(require_community),
    conn: asyncpg.Connection = Depends(get_conn),
):
    updates = body.model_dump(exclude_unset=True)
    if not updates:
        raise ApiError(400, "no_changes", "Nothing to update")
    if "attributes" in updates:
        updates["attributes"] = json.dumps(updates["attributes"])
    sets, values = patch_sets("community_assets", updates)
    row = await conn.fetchrow(
        f"update community_assets set {sets}, updated_at = now() where id = $1 returning {_FIELDS}",
        asset_id,
        *values,
    )
    if row is None:
        raise ApiError(404, "not_found", "Asset not found")
    await write_audit(
        conn, ctx.tenant_id, ctx.user_id, "community.asset_update", "asset", str(asset_id)
    )
    return _out(row)


@router.delete("/community/assets/{asset_id}", status_code=204)
async def delete_asset(
    asset_id: UUID,
    ctx: TenantContext = Depends(require_community),
    conn: asyncpg.Connection = Depends(get_conn),
):
    deleted = await conn.execute("delete from community_assets where id = $1", asset_id)
    if deleted == "DELETE 0":
        raise ApiError(404, "not_found", "Asset not found")
    await write_audit(
        conn, ctx.tenant_id, ctx.user_id, "community.asset_delete", "asset", str(asset_id)
    )
