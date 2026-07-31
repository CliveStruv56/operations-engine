"""Recent activity: audit-log slice scoped to a project's resources."""

from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends

from app.groundwork.schemas import ActivityOut
from app.routers.groundwork import require_projects
from app.routers.groundwork_room.common import module_project
from app.tenant import TenantContext, get_conn

router = APIRouter()


@router.get("/projects/{project_id}/activity", response_model=list[ActivityOut])
async def project_activity(
    project_id: UUID,
    ctx: TenantContext = Depends(require_projects),
    conn: asyncpg.Connection = Depends(get_conn),
):
    await module_project(conn, project_id)
    rows = await conn.fetch(
        """
        select action, user_id, created_at from audit_log
        where action like 'projects.%' and (
            target_id = $1
            or target_id in (select id::text from proj_stages where project_id = $2)
            or target_id in (select id::text from proj_tasks where project_id = $2)
            or target_id in (select id::text from proj_documents where project_id = $2)
            or target_id in (select id::text from proj_funding_sources where project_id = $2)
            or target_id in (select id::text from proj_risks where project_id = $2)
            or target_id in (select id::text from proj_conditions where project_id = $2)
            or target_id in (select id::text from proj_stakeholders where project_id = $2)
        )
        order by created_at desc limit 20
        """,
        str(project_id),
        project_id,
    )
    return [dict(r) for r in rows]
