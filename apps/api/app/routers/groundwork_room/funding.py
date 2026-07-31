"""Funding stack: sources CRUD with drawdown schedules."""

import json
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends

from app.audit import write_audit
from app.errors import ApiError
from app.groundwork.schemas import FundingIn, FundingPatch
from app.routers.groundwork import require_projects
from app.routers.groundwork_room.common import module_project
from app.sqlutil import patch_sets
from app.tenant import TenantContext, get_conn

router = APIRouter()


@router.get("/projects/{project_id}/funding")
async def list_funding(
    project_id: UUID,
    ctx: TenantContext = Depends(require_projects),
    conn: asyncpg.Connection = Depends(get_conn),
):
    await module_project(conn, project_id)
    rows = await conn.fetch(
        "select * from proj_funding_sources where project_id = $1 order by name", project_id
    )
    return [
        {
            **dict(r),
            "drawdown_schedule": json.loads(r["drawdown_schedule"]),
            "amount_sought": float(r["amount_sought"]) if r["amount_sought"] is not None else None,
            "amount_secured": float(r["amount_secured"])
            if r["amount_secured"] is not None
            else None,
        }
        for r in rows
    ]


@router.post("/projects/{project_id}/funding", status_code=201)
async def create_funding(
    project_id: UUID,
    body: FundingIn,
    ctx: TenantContext = Depends(require_projects),
    conn: asyncpg.Connection = Depends(get_conn),
):
    await module_project(conn, project_id)
    row = await conn.fetchrow(
        """
        insert into proj_funding_sources (tenant_id, project_id, programme_key, name, funder,
            kind, amount_sought, amount_secured, status, conditions, drawdown_schedule, notes)
        values ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12) returning id
        """,
        ctx.tenant_id,
        project_id,
        body.programme_key,
        body.name,
        body.funder,
        body.kind,
        body.amount_sought,
        body.amount_secured,
        body.status,
        body.conditions,
        json.dumps(body.drawdown_schedule),
        body.notes,
    )
    await write_audit(
        conn, ctx.tenant_id, ctx.user_id, "projects.funding_create", "funding", str(row["id"])
    )
    return {"id": str(row["id"])}


@router.patch("/projects/{project_id}/funding/{funding_id}")
async def patch_funding(
    project_id: UUID,
    funding_id: UUID,
    body: FundingPatch,
    ctx: TenantContext = Depends(require_projects),
    conn: asyncpg.Connection = Depends(get_conn),
):
    updates = body.model_dump(exclude_unset=True)
    if not updates:
        raise ApiError(400, "no_changes", "Nothing to update")
    if "drawdown_schedule" in updates:
        updates["drawdown_schedule"] = json.dumps(updates["drawdown_schedule"])
    sets, values = patch_sets("proj_funding_sources", updates, id_param=2)
    row = await conn.fetchrow(
        f"""update proj_funding_sources set {sets}, updated_at = now()
            where project_id = $1 and id = $2 returning id""",
        project_id,
        funding_id,
        *values,
    )
    if row is None:
        raise ApiError(404, "not_found", "Funding source not found")
    await write_audit(
        conn, ctx.tenant_id, ctx.user_id, "projects.funding_update", "funding", str(funding_id)
    )
    return {"id": str(funding_id)}


@router.delete("/projects/{project_id}/funding/{funding_id}", status_code=204)
async def delete_funding(
    project_id: UUID,
    funding_id: UUID,
    ctx: TenantContext = Depends(require_projects),
    conn: asyncpg.Connection = Depends(get_conn),
):
    deleted = await conn.execute(
        "delete from proj_funding_sources where project_id = $1 and id = $2",
        project_id,
        funding_id,
    )
    if deleted == "DELETE 0":
        raise ApiError(404, "not_found", "Funding source not found")
    await write_audit(
        conn, ctx.tenant_id, ctx.user_id, "projects.funding_delete", "funding", str(funding_id)
    )
