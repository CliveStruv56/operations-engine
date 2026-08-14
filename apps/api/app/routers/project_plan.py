"""Thin task list on a core (sidebar) project.

Path is `/projects/{id}/plan-tasks` so it never collides with Groundwork's
`/projects/{id}/tasks` (which requires the development extension and a stage).
"""

from datetime import UTC, datetime
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends

from app.audit import write_audit
from app.errors import ApiError
from app.schemas import PlanTaskIn, PlanTaskOut, PlanTaskPatch, PlanTaskSeed
from app.sqlutil import patch_sets
from app.tenant import TenantContext, get_conn, require_role

router = APIRouter(tags=["projects"])

_SELECT = """
    select t.*, m.email as assignee_email
    from project_tasks t
    left join memberships m on m.id = t.assignee_membership_id
"""


async def require_core_project(conn: asyncpg.Connection, project_id: UUID) -> asyncpg.Record:
    row = await conn.fetchrow("select id, has_plan from projects where id = $1", project_id)
    if row is None:
        raise ApiError(404, "not_found", "Project not found")
    return row


async def require_membership(conn: asyncpg.Connection, membership_id: UUID | None) -> None:
    if membership_id is None:
        return
    found = await conn.fetchval("select 1 from memberships where id = $1", membership_id)
    if not found:
        raise ApiError(404, "not_found", "Member not found")


async def seed_project_brief(
    conn: asyncpg.Connection, ctx: TenantContext, project_id: UUID, name: str
) -> None:
    """A primary vault note so chat has something to ground on from day one.

    No object-storage write: tests and CI run with storage disabled, and the
    brief is a few lines of text, not an uploaded file. Status is `ready` with
    a keyword chunk so the vault lists it immediately.
    """
    content = (
        f"# {name}\n\n"
        "This is the project brief. Replace or add documents that describe the work, "
        "then use chat to ask about them.\n"
    )
    doc_id = await conn.fetchval(
        """
        insert into documents (
            tenant_id, title, mime, status, project_id, is_primary, created_by
        )
        values ($1, 'Project brief', 'text/markdown', 'ready', $2, true, $3)
        returning id
        """,
        ctx.tenant_id,
        project_id,
        ctx.user_id,
    )
    await conn.execute(
        """
        insert into doc_chunks (tenant_id, document_id, content, page_start, page_end)
        values ($1, $2, $3, 1, 1)
        """,
        ctx.tenant_id,
        doc_id,
        content,
    )


async def insert_plan_tasks(
    conn: asyncpg.Connection,
    ctx: TenantContext,
    project_id: UUID,
    tasks: list[PlanTaskSeed],
) -> list[asyncpg.Record]:
    rows: list[asyncpg.Record] = []
    for position, task in enumerate(tasks, start=1):
        await require_membership(conn, task.assignee_membership_id)
        row = await conn.fetchrow(
            """
            insert into project_tasks (
                tenant_id, project_id, title, due_date, assignee_membership_id, position
            )
            values ($1, $2, $3, $4, $5, $6) returning *
            """,
            ctx.tenant_id,
            project_id,
            task.title,
            task.due_date,
            task.assignee_membership_id,
            position,
        )
        rows.append(row)
    return rows


@router.get("/projects/{project_id}/plan-tasks", response_model=list[PlanTaskOut])
async def list_plan_tasks(
    project_id: UUID,
    _ctx: TenantContext = Depends(require_role("member")),
    conn: asyncpg.Connection = Depends(get_conn),
):
    await require_core_project(conn, project_id)
    rows = await conn.fetch(
        f"{_SELECT} where t.project_id = $1 order by t.position, t.created_at",
        project_id,
    )
    return [dict(r) for r in rows]


@router.post("/projects/{project_id}/plan-tasks", status_code=201, response_model=PlanTaskOut)
async def create_plan_task(
    project_id: UUID,
    body: PlanTaskIn,
    ctx: TenantContext = Depends(require_role("member")),
    conn: asyncpg.Connection = Depends(get_conn),
):
    project = await require_core_project(conn, project_id)
    if not project["has_plan"]:
        raise ApiError(400, "no_plan", "This project has documents only — recreate it with a plan")
    await require_membership(conn, body.assignee_membership_id)
    position = await conn.fetchval(
        "select coalesce(max(position), 0) + 1 from project_tasks where project_id = $1",
        project_id,
    )
    row = await conn.fetchrow(
        """
        insert into project_tasks (
            tenant_id, project_id, title, due_date, assignee_membership_id, position
        )
        values ($1, $2, $3, $4, $5, $6) returning id
        """,
        ctx.tenant_id,
        project_id,
        body.title,
        body.due_date,
        body.assignee_membership_id,
        position,
    )
    await write_audit(
        conn, ctx.tenant_id, ctx.user_id, "project.task_create", "project_task", str(row["id"])
    )
    out = await conn.fetchrow(f"{_SELECT} where t.id = $1", row["id"])
    assert out is not None
    return dict(out)


@router.patch("/projects/{project_id}/plan-tasks/{task_id}", response_model=PlanTaskOut)
async def update_plan_task(
    project_id: UUID,
    task_id: UUID,
    body: PlanTaskPatch,
    ctx: TenantContext = Depends(require_role("member")),
    conn: asyncpg.Connection = Depends(get_conn),
):
    await require_core_project(conn, project_id)
    updates = body.model_dump(exclude_unset=True)
    if not updates:
        raise ApiError(400, "no_changes", "Nothing to update")
    if "assignee_membership_id" in updates:
        await require_membership(conn, updates["assignee_membership_id"])
    if updates.get("status") == "done":
        updates.setdefault("completed_at", datetime.now(UTC))
    elif "status" in updates:
        updates["completed_at"] = None
    sets, values = patch_sets("project_tasks", updates, id_param=2)
    row = await conn.fetchrow(
        f"update project_tasks set {sets} where project_id = $1 and id = $2 returning id",
        project_id,
        task_id,
        *values,
    )
    if row is None:
        raise ApiError(404, "not_found", "Task not found")
    await write_audit(
        conn, ctx.tenant_id, ctx.user_id, "project.task_update", "project_task", str(task_id)
    )
    out = await conn.fetchrow(f"{_SELECT} where t.id = $1", task_id)
    assert out is not None
    return dict(out)


@router.delete("/projects/{project_id}/plan-tasks/{task_id}", status_code=204)
async def delete_plan_task(
    project_id: UUID,
    task_id: UUID,
    ctx: TenantContext = Depends(require_role("member")),
    conn: asyncpg.Connection = Depends(get_conn),
):
    await require_core_project(conn, project_id)
    deleted = await conn.fetchval(
        "delete from project_tasks where project_id = $1 and id = $2 returning id",
        project_id,
        task_id,
    )
    if deleted is None:
        raise ApiError(404, "not_found", "Task not found")
    await write_audit(
        conn, ctx.tenant_id, ctx.user_id, "project.task_delete", "project_task", str(task_id)
    )
