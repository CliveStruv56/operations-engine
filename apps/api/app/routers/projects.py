"""Projects (Slice 4.5): named containers owning documents and chat scope.

Deleting a project never deletes content — documents and conversations fall
back to the unassigned pool (FK on delete set null). Groundwork (the PM
module) extends these rows rather than defining its own project concept.
"""

from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends

from app.audit import write_audit
from app.errors import ApiError
from app.schemas import ProjectCreate, ProjectOut, ProjectUpdate
from app.sqlutil import patch_sets
from app.tenant import TenantContext, get_conn, require_role

router = APIRouter(tags=["projects"])

_LIST_SQL = """
    select p.*, count(d.id) as document_count, (pp.id is not null) as is_development
    from projects p
    left join proj_projects pp on pp.id = p.id
    left join documents d on d.project_id = p.id
    group by p.id, pp.id
    order by p.archived, p.created_at desc
"""


@router.post("/projects", status_code=201, response_model=ProjectOut)
async def create_project(
    body: ProjectCreate,
    ctx: TenantContext = Depends(require_role("member")),
    conn: asyncpg.Connection = Depends(get_conn),
):
    row = await conn.fetchrow(
        """
        insert into projects (tenant_id, name, description, created_by)
        values ($1, $2, $3, $4) returning *
        """,
        ctx.tenant_id,
        body.name,
        body.description,
        ctx.user_id,
    )
    await write_audit(conn, ctx.tenant_id, ctx.user_id, "project.create", "project", str(row["id"]))
    return {**dict(row), "document_count": 0}


@router.get("/projects", response_model=list[ProjectOut])
async def list_projects(
    ctx: TenantContext = Depends(require_role("member")),
    conn: asyncpg.Connection = Depends(get_conn),
):
    return [dict(r) for r in await conn.fetch(_LIST_SQL)]


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
    sets, values = patch_sets("projects", updates)
    row = await conn.fetchrow(
        f"update projects set {sets}, updated_at = now() where id = $1 returning *",
        project_id,
        *values,
    )
    if row is None:
        raise ApiError(404, "not_found", "Project not found")
    count = await conn.fetchval("select count(*) from documents where project_id = $1", project_id)
    is_dev = await conn.fetchval(
        "select exists (select 1 from proj_projects where id = $1)", project_id
    )
    await write_audit(
        conn, ctx.tenant_id, ctx.user_id, "project.update", "project", str(project_id)
    )
    return {**dict(row), "document_count": count, "is_development": is_dev}


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
