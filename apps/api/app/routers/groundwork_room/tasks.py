"""Tasks: filtered list, CRUD, bulk complete."""

from datetime import UTC, datetime
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, Query

from app.audit import write_audit
from app.errors import ApiError
from app.groundwork.schemas import BulkCompleteIn, TaskIn, TaskOut, TaskPatch
from app.routers.groundwork import require_projects
from app.routers.groundwork_room.common import module_project
from app.sqlutil import patch_sets
from app.tenant import TenantContext, get_conn

router = APIRouter()


@router.get("/projects/{project_id}/tasks", response_model=list[TaskOut])
async def list_tasks(
    project_id: UUID,
    stage_key: str | None = Query(default=None),
    status: str | None = Query(default=None),
    overdue: bool = Query(default=False),
    ctx: TenantContext = Depends(require_projects),
    conn: asyncpg.Connection = Depends(get_conn),
):
    await module_project(conn, project_id)
    clauses: list[str] = ["project_id = $1"]
    args: list = [project_id]
    if stage_key:
        args.append(stage_key)
        clauses.append(f"stage_key = ${len(args)}")
    if status:
        args.append(status)
        clauses.append(f"status = ${len(args)}")
    if overdue:
        clauses.append("due_date < current_date and status in ('todo','doing')")
    rows = await conn.fetch(
        f"select * from proj_tasks where {' and '.join(clauses)} order by position, due_date",
        *args,
    )
    return [dict(r) for r in rows]


@router.post("/projects/{project_id}/tasks", status_code=201, response_model=TaskOut)
async def create_task(
    project_id: UUID,
    body: TaskIn,
    ctx: TenantContext = Depends(require_projects),
    conn: asyncpg.Connection = Depends(get_conn),
):
    await module_project(conn, project_id)
    position = await conn.fetchval(
        "select coalesce(max(position), 0) + 1 from proj_tasks where project_id = $1", project_id
    )
    row = await conn.fetchrow(
        """
        insert into proj_tasks (tenant_id, project_id, stage_key, title, details, owner_name,
                                due_date, is_milestone, tags, source, position)
        values ($1, $2, $3, $4, $5, $6, $7, $8, $9, 'manual', $10) returning *
        """,
        ctx.tenant_id,
        project_id,
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
        conn, ctx.tenant_id, ctx.user_id, "projects.task_create", "task", str(row["id"])
    )
    return dict(row)


@router.patch("/projects/{project_id}/tasks/{task_id}", response_model=TaskOut)
async def patch_task(
    project_id: UUID,
    task_id: UUID,
    body: TaskPatch,
    ctx: TenantContext = Depends(require_projects),
    conn: asyncpg.Connection = Depends(get_conn),
):
    updates = body.model_dump(exclude_unset=True)
    if not updates:
        raise ApiError(400, "no_changes", "Nothing to update")
    if updates.get("status") == "done":
        updates["completed_at"] = datetime.now(UTC)
    elif "status" in updates:
        updates["completed_at"] = None
    sets, values = patch_sets("proj_tasks", updates, id_param=2)
    row = await conn.fetchrow(
        f"update proj_tasks set {sets} where project_id = $1 and id = $2 returning *",
        project_id,
        task_id,
        *values,
    )
    if row is None:
        raise ApiError(404, "not_found", "Task not found")
    await write_audit(
        conn, ctx.tenant_id, ctx.user_id, "projects.task_update", "task", str(task_id)
    )
    return dict(row)


@router.delete("/projects/{project_id}/tasks/{task_id}", status_code=204)
async def delete_task(
    project_id: UUID,
    task_id: UUID,
    ctx: TenantContext = Depends(require_projects),
    conn: asyncpg.Connection = Depends(get_conn),
):
    deleted = await conn.execute(
        "delete from proj_tasks where project_id = $1 and id = $2", project_id, task_id
    )
    if deleted == "DELETE 0":
        raise ApiError(404, "not_found", "Task not found")
    await write_audit(
        conn, ctx.tenant_id, ctx.user_id, "projects.task_delete", "task", str(task_id)
    )


@router.post("/projects/{project_id}/tasks/bulk-complete")
async def bulk_complete_tasks(
    project_id: UUID,
    body: BulkCompleteIn,
    ctx: TenantContext = Depends(require_projects),
    conn: asyncpg.Connection = Depends(get_conn),
):
    updated = await conn.execute(
        """
        update proj_tasks set status = 'done', completed_at = now()
        where project_id = $1 and id = any($2) and status <> 'done'
        """,
        project_id,
        body.ids,
    )
    await write_audit(
        conn, ctx.tenant_id, ctx.user_id, "projects.task_bulk_complete", "project", str(project_id)
    )
    return {"completed": int(updated.split()[-1])}
