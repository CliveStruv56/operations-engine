"""Projects (Slice 4.5): named containers owning documents and chat scope.

Deleting a project never deletes content — documents and conversations fall
back to the unassigned pool (FK on delete set null). Groundwork (the PM
module) extends these rows rather than defining its own project concept.

Every project has a stored kind (`projects.kind`, 0031) from the registry in
`app/projects/kinds.py`. `with_plan` adds a thin task list (`project_tasks`)
and a default brief document to a general project. That is not Groundwork
setup: no stages, gates, or `proj_*` rows — a development project is made by
`POST /projects/{id}/setup`, and the database sets its kind.
"""

import json
from typing import Any
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, Query

from app.audit import write_audit
from app.errors import ApiError
from app.projects.kinds import (
    KINDS_BY_KEY,
    PROJECT_ADDONS,
    PROJECT_KINDS,
    kind_available,
    module_catalogue,
)
from app.routers.project_plan import insert_plan_tasks, seed_project_brief
from app.schemas import (
    ProjectCreate,
    ProjectKindsOut,
    ProjectOut,
    ProjectUpdate,
    WorkspaceModuleOut,
)
from app.sqlutil import patch_sets
from app.tenant import TenantContext, get_conn, require_role

router = APIRouter(tags=["projects"])

_ENRICHED_SQL = """
    select p.*,
           count(distinct d.id)::int as document_count,
           (p.kind = 'development') as is_development,
           pp.stage_current,
           count(distinct pt.id) filter (
               where pt.status in ('todo', 'doing')
           )::int as open_task_count
    from projects p
    left join proj_projects pp on pp.id = p.id
    left join documents d on d.project_id = p.id
    left join project_tasks pt on pt.project_id = p.id
"""


async def tenant_features(conn: asyncpg.Connection, tenant_id: UUID) -> dict[str, Any]:
    raw = await conn.fetchval("select features from tenants where id = $1", tenant_id)
    return json.loads(raw) if raw else {}


def with_availability(row: asyncpg.Record, features: dict[str, Any]) -> dict[str, Any]:
    out = dict(row)
    out["kind_available"] = kind_available(out["kind"], features)
    return out


async def fetch_project(conn: asyncpg.Connection, project_id: UUID) -> asyncpg.Record | None:
    return await conn.fetchrow(f"{_ENRICHED_SQL} where p.id = $1 group by p.id, pp.id", project_id)


async def project_out(conn: asyncpg.Connection, ctx: TenantContext, project_id: UUID) -> dict:
    row = await fetch_project(conn, project_id)
    assert row is not None
    return with_availability(row, await tenant_features(conn, ctx.tenant_id))


@router.get("/project-kinds", response_model=ProjectKindsOut)
async def list_project_kinds(
    ctx: TenantContext = Depends(require_role("member")),
    conn: asyncpg.Connection = Depends(get_conn),
):
    """The kinds and add-ons this workspace can use. The web builds its
    new-project picker and sidebar from this list, so a new kind needs no
    web change beyond an icon."""
    features = await tenant_features(conn, ctx.tenant_id)
    return {
        "kinds": [
            {
                "key": k.key,
                "label": k.label,
                "description": k.description,
                "home": k.home,
                "create": k.create,
                "upgrades_to": list(k.upgrades_to),
                "available": kind_available(k.key, features),
            }
            for k in PROJECT_KINDS
        ],
        "addons": [
            {
                "key": a.key,
                "label": a.label,
                "description": a.description,
                "available": features.get(a.module) is True,
            }
            for a in PROJECT_ADDONS
        ],
    }


@router.get("/modules", response_model=list[WorkspaceModuleOut])
async def list_workspace_modules(
    ctx: TenantContext = Depends(require_role("member")),
    conn: asyncpg.Connection = Depends(get_conn),
):
    """Which modules this workspace has and what each adds — settings' "Your
    modules" list, so a member can see why a kind is missing from the picker."""
    features = await tenant_features(conn, ctx.tenant_id)
    return [{**m, "enabled": features.get(m["flag"]) is True} for m in module_catalogue()]


@router.post("/projects", status_code=201, response_model=ProjectOut)
async def create_project(
    body: ProjectCreate,
    ctx: TenantContext = Depends(require_role("member")),
    conn: asyncpg.Connection = Depends(get_conn),
):
    plan = body.plan_requested
    if not plan and body.tasks:
        raise ApiError(400, "invalid", "Tasks can only be added when creating a planned project")
    # blank/planned are legacy spellings of general; only inline kinds get here.
    kind = "general" if body.kind in ("blank", "planned") else body.kind
    assert KINDS_BY_KEY[kind].create == "inline"
    row = await conn.fetchrow(
        """
        insert into projects (tenant_id, name, description, created_by, has_plan, kind)
        values ($1, $2, $3, $4, $5, $6) returning *
        """,
        ctx.tenant_id,
        body.name,
        body.description,
        ctx.user_id,
        plan,
        kind,
    )
    if plan:
        await seed_project_brief(conn, ctx, row["id"], body.name)
        await insert_plan_tasks(conn, ctx, row["id"], body.tasks)
    await write_audit(conn, ctx.tenant_id, ctx.user_id, "project.create", "project", str(row["id"]))
    return await project_out(conn, ctx, row["id"])


@router.get("/projects", response_model=list[ProjectOut])
async def list_projects(
    kind: str | None = Query(default=None),
    ctx: TenantContext = Depends(require_role("member")),
    conn: asyncpg.Connection = Depends(get_conn),
):
    if kind is not None and kind not in KINDS_BY_KEY:
        raise ApiError(400, "invalid", "Unknown project kind")
    features = await tenant_features(conn, ctx.tenant_id)
    # Most recently updated first: the sidebar lists projects in this order.
    rows = await conn.fetch(
        f"""{_ENRICHED_SQL} where ($1::text is null or p.kind = $1)
        group by p.id, pp.id order by p.archived, p.updated_at desc, p.created_at desc""",
        kind,
    )
    return [with_availability(r, features) for r in rows]


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
    had_plan = False
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
        had_plan = bool(
            await conn.fetchval("select has_plan from projects where id = $1", project_id)
        )
    sets, values = patch_sets("projects", updates)
    row = await conn.fetchrow(
        f"update projects set {sets}, updated_at = now() where id = $1 returning id, name",
        project_id,
        *values,
    )
    if row is None:
        raise ApiError(404, "not_found", "Project not found")
    if updates.get("has_plan") is True and not had_plan:
        # Only on the false->true transition: a planned project whose owner
        # deleted the brief must not get it re-seeded by an unrelated PATCH.
        doc_count = await conn.fetchval(
            "select count(*) from documents where project_id = $1", project_id
        )
        if doc_count == 0:
            await seed_project_brief(conn, ctx, project_id, row["name"])
    await write_audit(
        conn, ctx.tenant_id, ctx.user_id, "project.update", "project", str(project_id)
    )
    return await project_out(conn, ctx, project_id)


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
