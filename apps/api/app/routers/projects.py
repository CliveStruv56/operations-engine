"""Projects (Slice 4.5): named containers owning documents and chat scope.

Deleting a project never deletes content — documents and conversations fall
back to the unassigned pool (FK on delete set null). Groundwork (the PM
module) extends these rows rather than defining its own project concept.

`kind=planned` adds a thin task list (`project_tasks`) and a default brief
document. That is not Groundwork setup: no stages, gates, or `proj_*` rows.
"""

from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends

from app.audit import write_audit
from app.errors import ApiError
from app.routers.project_plan import insert_plan_tasks, seed_project_brief
from app.schemas import ProjectCreate, ProjectOut, ProjectUpdate
from app.sqlutil import patch_sets
from app.tenant import TenantContext, get_conn, require_role

router = APIRouter(tags=["projects"])

_ENRICHED_SQL = """
    select p.*,
           count(distinct d.id)::int as document_count,
           (pp.id is not null) as is_development,
           count(distinct pt.id) filter (
               where pt.status in ('todo', 'doing')
           )::int as open_task_count
    from projects p
    left join proj_projects pp on pp.id = p.id
    left join documents d on d.project_id = p.id
    left join project_tasks pt on pt.project_id = p.id
"""


async def fetch_project(conn: asyncpg.Connection, project_id: UUID) -> asyncpg.Record | None:
    return await conn.fetchrow(f"{_ENRICHED_SQL} where p.id = $1 group by p.id, pp.id", project_id)


@router.post("/projects", status_code=201, response_model=ProjectOut)
async def create_project(
    body: ProjectCreate,
    ctx: TenantContext = Depends(require_role("member")),
    conn: asyncpg.Connection = Depends(get_conn),
):
    if body.kind == "blank" and body.tasks:
        raise ApiError(400, "invalid", "Tasks can only be added when creating a planned project")
    row = await conn.fetchrow(
        """
        insert into projects (tenant_id, name, description, created_by, has_plan)
        values ($1, $2, $3, $4, $5) returning *
        """,
        ctx.tenant_id,
        body.name,
        body.description,
        ctx.user_id,
        body.kind == "planned",
    )
    if body.kind == "planned":
        await seed_project_brief(conn, ctx, row["id"], body.name)
        await insert_plan_tasks(conn, ctx, row["id"], body.tasks)
    await write_audit(conn, ctx.tenant_id, ctx.user_id, "project.create", "project", str(row["id"]))
    out = await fetch_project(conn, row["id"])
    assert out is not None
    return dict(out)


@router.get("/projects", response_model=list[ProjectOut])
async def list_projects(
    ctx: TenantContext = Depends(require_role("member")),
    conn: asyncpg.Connection = Depends(get_conn),
):
    return [
        dict(r)
        for r in await conn.fetch(
            f"{_ENRICHED_SQL} group by p.id, pp.id order by p.archived, p.created_at desc"
        )
    ]


@router.patch("/projects/{project_id}", response_model=ProjectOut)
async def update_project(
    project_id: UUID,
    body: ProjectUpdate,
    ctx: TenantContext = Depends(require_role("member")),
    conn: asyncpg.Connection = Depends(get_conn),
):
    updates = body.model_dump(exclude_unset=True)
    if not updates:
        raise ApiError(400, "no_changes", "Nothing to update")
    if "has_plan" in updates:
        is_dev = await conn.fetchval(
            "select exists (select 1 from proj_projects where id = $1)", project_id
        )
        if is_dev:
            raise ApiError(
                400, "invalid", "Development projects use the project room, not a core plan"
            )
        if updates["has_plan"] is False:
            raise ApiError(400, "invalid", "A plan cannot be removed once added")
    sets, values = patch_sets("projects", updates)
    row = await conn.fetchrow(
        f"update projects set {sets}, updated_at = now() where id = $1 returning id, name",
        project_id,
        *values,
    )
    if row is None:
        raise ApiError(404, "not_found", "Project not found")
    if updates.get("has_plan") is True:
        doc_count = await conn.fetchval(
            "select count(*) from documents where project_id = $1", project_id
        )
        if doc_count == 0:
            await seed_project_brief(conn, ctx, project_id, row["name"])
    await write_audit(
        conn, ctx.tenant_id, ctx.user_id, "project.update", "project", str(project_id)
    )
    out = await fetch_project(conn, project_id)
    assert out is not None
    return dict(out)


@router.delete("/projects/{project_id}", status_code=204)
async def delete_project(
    project_id: UUID,
    ctx: TenantContext = Depends(require_role("admin")),
    conn: asyncpg.Connection = Depends(get_conn),
):
    deleted = await conn.execute("delete from projects where id = $1", project_id)
    if deleted == "DELETE 0":
        raise ApiError(404, "not_found", "Project not found")
    await write_audit(
        conn, ctx.tenant_id, ctx.user_id, "project.delete", "project", str(project_id)
    )
