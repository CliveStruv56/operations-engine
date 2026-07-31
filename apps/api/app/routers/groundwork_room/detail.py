"""Project detail + programme catalogue (literal path, registered first)."""

import json
from datetime import date
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, Query

from app.audit import write_audit
from app.errors import ApiError
from app.groundwork.schemas import GroundworkDetail, GroundworkPatch, ProgrammeOut
from app.routers.groundwork import require_projects
from app.routers.groundwork_room.common import module_project
from app.sqlutil import patch_sets
from app.tenant import TenantContext, get_conn

router = APIRouter()


@router.get("/projects/funding-programmes", response_model=list[ProgrammeOut])
async def funding_programmes(
    nation: str | None = Query(default=None),
    kind: str | None = Query(default=None),
    stage: str | None = Query(default=None),
    status: str | None = Query(default=None),
    ctx: TenantContext = Depends(require_projects),
    conn: asyncpg.Connection = Depends(get_conn),
):
    rows = await conn.fetch("select * from proj_ref_programmes order by name")
    out = []
    for r in rows:
        if nation and nation not in r["nations"] and "uk" not in r["nations"]:
            continue
        if kind and r["kind"] != kind:
            continue
        if stage and stage not in r["stage_fit"]:
            continue
        if status and r["status"] != status:
            continue
        out.append({**dict(r), "stale": r["next_review"] < date.today()})
    return out


@router.get("/projects/{project_id}/groundwork", response_model=GroundworkDetail)
async def project_detail(
    project_id: UUID,
    ctx: TenantContext = Depends(require_projects),
    conn: asyncpg.Connection = Depends(get_conn),
):
    row = await module_project(conn, project_id)
    out = dict(row)
    out["applicability"] = json.loads(out["applicability"])
    out["contract_facts"] = json.loads(out["contract_facts"])
    return out


@router.patch("/projects/{project_id}/groundwork", response_model=GroundworkDetail)
async def patch_project(
    project_id: UUID,
    body: GroundworkPatch,
    ctx: TenantContext = Depends(require_projects),
    conn: asyncpg.Connection = Depends(get_conn),
):
    await module_project(conn, project_id)
    updates = body.model_dump(exclude_unset=True)
    if not updates:
        raise ApiError(400, "no_changes", "Nothing to update")
    for key in ("applicability", "contract_facts"):
        if key in updates:
            updates[key] = json.dumps(updates[key])
    sets, values = patch_sets("proj_projects", updates)
    await conn.execute(
        f"update proj_projects set {sets}, updated_at = now() where id = $1",
        project_id,
        *values,
    )
    await write_audit(
        conn, ctx.tenant_id, ctx.user_id, "projects.update", "project", str(project_id)
    )
    return await project_detail(project_id, ctx, conn)
