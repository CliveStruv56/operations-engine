"""Application tasks: the seeded checklist plus anything the team adds."""

from datetime import UTC, datetime
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, Query

from app.audit import write_audit
from app.errors import ApiError
from app.grants.schemas import TaskIn, TaskOut, TaskPatch
from app.routers.grants.common import module_application, require_grants
from app.sqlutil import patch_sets
from app.tenant import TenantContext, get_conn

router = APIRouter()


@router.get("/grants/applications/{application_id}/tasks", response_model=list[TaskOut])
async def list_tasks(
    application_id: UUID,
    stage_key: str | None = Query(default=None, max_length=20),
    status: str | None = Query(default=None, max_length=10),
    ctx: TenantContext = Depends(require_grants),
    conn: asyncpg.Connection = Depends(get_conn),
):
    await module_application(conn, application_id)
    clauses = ["application_id = $1"]
    params: list[object] = [application_id]
    if stage_key:
        params.append(stage_key)
        clauses.append(f"stage_key = ${len(params)}")
    if status:
        params.append(status)
        clauses.append(f"status = ${len(params)}")
    rows = await conn.fetch(
        f"select * from grant_tasks where {' and '.join(clauses)} order by position, id", *params
    )
    return [dict(r) for r in rows]


@router.post("/grants/applications/{application_id}/tasks", status_code=201, response_model=TaskOut)
async def create_task(
    application_id: UUID,
    body: TaskIn,
    ctx: TenantContext = Depends(require_grants),
    conn: asyncpg.Connection = Depends(get_conn),
):
    await module_application(conn, application_id)
    position = await conn.fetchval(
        "select coalesce(max(position), 0) + 1 from grant_tasks where application_id = $1",
        application_id,
    )
    row = await conn.fetchrow(
        """
        insert into grant_tasks (tenant_id, application_id, stage_key, title, details,
                                 owner_name, due_date, is_milestone, tags, source, position)
        values ($1, $2, $3, $4, $5, $6, $7, $8, $9, 'manual', $10)
        returning *
        """,
        ctx.tenant_id,
        application_id,
        body.stage_key,
        body.title,
        body.details,
        body.owner_name,
        body.due_date,
        body.is_milestone,
        body.tags,
        position,
    )
    await write_audit(
        conn, ctx.tenant_id, ctx.user_id, "grants.task_create", "grant_task", str(row["id"])
    )
    return dict(row)


@router.patch("/grants/applications/{application_id}/tasks/{task_id}", response_model=TaskOut)
async def patch_task(
    application_id: UUID,
    task_id: UUID,
    body: TaskPatch,
    ctx: TenantContext = Depends(require_grants),
    conn: asyncpg.Connection = Depends(get_conn),
):
    updates = body.model_dump(exclude_unset=True)
    if not updates:
        raise ApiError(400, "no_changes", "Nothing to update")
    if "status" in updates:
        # completed_at is derived from status so the two can never disagree.
        updates["completed_at"] = datetime.now(UTC) if updates["status"] == "done" else None
    sets, values = patch_sets("grant_tasks", updates, id_param=2)
    row = await conn.fetchrow(
        f"""update grant_tasks set {sets}
            where application_id = $1 and id = $2 returning *""",
        application_id,
        task_id,
        *values,
    )
    if row is None:
        raise ApiError(404, "not_found", "Task not found")
    await write_audit(
        conn, ctx.tenant_id, ctx.user_id, "grants.task_update", "grant_task", str(task_id)
    )
    return dict(row)


@router.delete("/grants/applications/{application_id}/tasks/{task_id}", status_code=204)
async def delete_task(
    application_id: UUID,
    task_id: UUID,
    ctx: TenantContext = Depends(require_grants),
    conn: asyncpg.Connection = Depends(get_conn),
):
    deleted = await conn.execute(
        "delete from grant_tasks where application_id = $1 and id = $2", application_id, task_id
    )
    if deleted == "DELETE 0":
        raise ApiError(404, "not_found", "Task not found")
    await write_audit(
        conn, ctx.tenant_id, ctx.user_id, "grants.task_delete", "grant_task", str(task_id)
    )
