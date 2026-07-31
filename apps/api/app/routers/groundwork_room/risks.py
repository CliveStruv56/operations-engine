"""Risk register: score-ordered list, create, patch."""

from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends

from app.audit import write_audit
from app.errors import ApiError
from app.groundwork.schemas import RiskIn, RiskPatch
from app.routers.groundwork import require_projects
from app.routers.groundwork_room.common import module_project
from app.sqlutil import patch_sets
from app.tenant import TenantContext, get_conn

router = APIRouter()


@router.get("/projects/{project_id}/risks")
async def list_risks(
    project_id: UUID,
    ctx: TenantContext = Depends(require_projects),
    conn: asyncpg.Connection = Depends(get_conn),
):
    await module_project(conn, project_id)
    rows = await conn.fetch(
        """select * from proj_risks where project_id = $1
           order by status = 'closed', likelihood * impact desc""",
        project_id,
    )
    return [dict(r) for r in rows]


@router.post("/projects/{project_id}/risks", status_code=201)
async def create_risk(
    project_id: UUID,
    body: RiskIn,
    ctx: TenantContext = Depends(require_projects),
    conn: asyncpg.Connection = Depends(get_conn),
):
    await module_project(conn, project_id)
    row = await conn.fetchrow(
        """
        insert into proj_risks (tenant_id, project_id, category, description, likelihood,
                                impact, owner_name, mitigation, review_date, source)
        values ($1, $2, $3, $4, $5, $6, $7, $8, $9, 'manual') returning id
        """,
        ctx.tenant_id,
        project_id,
        body.category,
        body.description,
        body.likelihood,
        body.impact,
        body.owner_name,
        body.mitigation,
        body.review_date,
    )
    await write_audit(
        conn, ctx.tenant_id, ctx.user_id, "projects.risk_create", "risk", str(row["id"])
    )
    return {"id": str(row["id"])}


@router.patch("/projects/{project_id}/risks/{risk_id}")
async def patch_risk(
    project_id: UUID,
    risk_id: UUID,
    body: RiskPatch,
    ctx: TenantContext = Depends(require_projects),
    conn: asyncpg.Connection = Depends(get_conn),
):
    updates = body.model_dump(exclude_unset=True)
    if not updates:
        raise ApiError(400, "no_changes", "Nothing to update")
    sets, values = patch_sets("proj_risks", updates, id_param=2)
    row = await conn.fetchrow(
        f"""update proj_risks set {sets}, updated_at = now()
            where project_id = $1 and id = $2 returning id""",
        project_id,
        risk_id,
        *values,
    )
    if row is None:
        raise ApiError(404, "not_found", "Risk not found")
    await write_audit(
        conn, ctx.tenant_id, ctx.user_id, "projects.risk_update", "risk", str(risk_id)
    )
    return {"id": str(risk_id)}
