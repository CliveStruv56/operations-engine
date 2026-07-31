"""Planning conditions: pre-commencement-first list, CRUD."""

from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends

from app.audit import write_audit
from app.errors import ApiError
from app.groundwork.schemas import ConditionIn, ConditionPatch
from app.routers.groundwork import require_projects
from app.routers.groundwork_room.common import module_project
from app.sqlutil import patch_sets
from app.tenant import TenantContext, get_conn

router = APIRouter()


@router.get("/projects/{project_id}/conditions")
async def list_conditions(
    project_id: UUID,
    ctx: TenantContext = Depends(require_projects),
    conn: asyncpg.Connection = Depends(get_conn),
):
    await module_project(conn, project_id)
    rows = await conn.fetch(
        """select * from proj_conditions where project_id = $1
           order by pre_commencement desc, number""",
        project_id,
    )
    return [dict(r) for r in rows]


@router.post("/projects/{project_id}/conditions", status_code=201)
async def create_condition(
    project_id: UUID,
    body: ConditionIn,
    ctx: TenantContext = Depends(require_projects),
    conn: asyncpg.Connection = Depends(get_conn),
):
    await module_project(conn, project_id)
    row = await conn.fetchrow(
        """
        insert into proj_conditions (tenant_id, project_id, application_ref, number,
                                     description, pre_commencement)
        values ($1, $2, $3, $4, $5, $6) returning id
        """,
        ctx.tenant_id,
        project_id,
        body.application_ref,
        body.number,
        body.description,
        body.pre_commencement,
    )
    await write_audit(
        conn, ctx.tenant_id, ctx.user_id, "projects.condition_create", "condition", str(row["id"])
    )
    return {"id": str(row["id"])}


@router.patch("/projects/{project_id}/conditions/{condition_id}")
async def patch_condition(
    project_id: UUID,
    condition_id: UUID,
    body: ConditionPatch,
    ctx: TenantContext = Depends(require_projects),
    conn: asyncpg.Connection = Depends(get_conn),
):
    updates = body.model_dump(exclude_unset=True)
    if not updates:
        raise ApiError(400, "no_changes", "Nothing to update")
    sets, values = patch_sets("proj_conditions", updates, id_param=2)
    row = await conn.fetchrow(
        f"update proj_conditions set {sets} where project_id = $1 and id = $2 returning id",
        project_id,
        condition_id,
        *values,
    )
    if row is None:
        raise ApiError(404, "not_found", "Condition not found")
    await write_audit(
        conn,
        ctx.tenant_id,
        ctx.user_id,
        "projects.condition_update",
        "condition",
        str(condition_id),
    )
    return {"id": str(condition_id)}


@router.delete("/projects/{project_id}/conditions/{condition_id}", status_code=204)
async def delete_condition(
    project_id: UUID,
    condition_id: UUID,
    ctx: TenantContext = Depends(require_projects),
    conn: asyncpg.Connection = Depends(get_conn),
):
    deleted = await conn.execute(
        "delete from proj_conditions where project_id = $1 and id = $2",
        project_id,
        condition_id,
    )
    if deleted == "DELETE 0":
        raise ApiError(404, "not_found", "Condition not found")
    await write_audit(
        conn,
        ctx.tenant_id,
        ctx.user_id,
        "projects.condition_delete",
        "condition",
        str(condition_id),
    )
