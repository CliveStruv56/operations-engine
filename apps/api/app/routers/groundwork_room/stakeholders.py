"""Stakeholder directory: role-ordered list, CRUD."""

from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends

from app.audit import write_audit
from app.errors import ApiError
from app.groundwork.schemas import StakeholderIn, StakeholderPatch
from app.routers.groundwork import require_projects
from app.routers.groundwork_room.common import module_project
from app.sqlutil import patch_sets
from app.tenant import TenantContext, get_conn

router = APIRouter()


@router.get("/projects/{project_id}/stakeholders")
async def list_stakeholders(
    project_id: UUID,
    ctx: TenantContext = Depends(require_projects),
    conn: asyncpg.Connection = Depends(get_conn),
):
    await module_project(conn, project_id)
    rows = await conn.fetch(
        "select * from proj_stakeholders where project_id = $1 order by role, name", project_id
    )
    return [dict(r) for r in rows]


@router.post("/projects/{project_id}/stakeholders", status_code=201)
async def create_stakeholder(
    project_id: UUID,
    body: StakeholderIn,
    ctx: TenantContext = Depends(require_projects),
    conn: asyncpg.Connection = Depends(get_conn),
):
    await module_project(conn, project_id)
    row = await conn.fetchrow(
        """
        insert into proj_stakeholders (tenant_id, project_id, name, org, role, email,
                                       phone, notes, last_contact)
        values ($1, $2, $3, $4, $5, $6, $7, $8, $9) returning id
        """,
        ctx.tenant_id,
        project_id,
        body.name,
        body.org,
        body.role,
        body.email,
        body.phone,
        body.notes,
        body.last_contact,
    )
    await write_audit(
        conn,
        ctx.tenant_id,
        ctx.user_id,
        "projects.stakeholder_create",
        "stakeholder",
        str(row["id"]),
    )
    return {"id": str(row["id"])}


@router.patch("/projects/{project_id}/stakeholders/{stakeholder_id}")
async def patch_stakeholder(
    project_id: UUID,
    stakeholder_id: UUID,
    body: StakeholderPatch,
    ctx: TenantContext = Depends(require_projects),
    conn: asyncpg.Connection = Depends(get_conn),
):
    updates = body.model_dump(exclude_unset=True)
    if not updates:
        raise ApiError(400, "no_changes", "Nothing to update")
    sets, values = patch_sets("proj_stakeholders", updates, id_param=2)
    row = await conn.fetchrow(
        f"update proj_stakeholders set {sets} where project_id = $1 and id = $2 returning id",
        project_id,
        stakeholder_id,
        *values,
    )
    if row is None:
        raise ApiError(404, "not_found", "Stakeholder not found")
    await write_audit(
        conn,
        ctx.tenant_id,
        ctx.user_id,
        "projects.stakeholder_update",
        "stakeholder",
        str(stakeholder_id),
    )
    return {"id": str(stakeholder_id)}


@router.delete("/projects/{project_id}/stakeholders/{stakeholder_id}", status_code=204)
async def delete_stakeholder(
    project_id: UUID,
    stakeholder_id: UUID,
    ctx: TenantContext = Depends(require_projects),
    conn: asyncpg.Connection = Depends(get_conn),
):
    deleted = await conn.execute(
        "delete from proj_stakeholders where project_id = $1 and id = $2",
        project_id,
        stakeholder_id,
    )
    if deleted == "DELETE 0":
        raise ApiError(404, "not_found", "Stakeholder not found")
    await write_audit(
        conn,
        ctx.tenant_id,
        ctx.user_id,
        "projects.stakeholder_delete",
        "stakeholder",
        str(stakeholder_id),
    )
