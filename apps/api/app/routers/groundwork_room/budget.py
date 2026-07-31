"""Budget: whole-table read and replace with computed totals."""

from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends

from app.audit import write_audit
from app.groundwork.schemas import BudgetLineIn, BudgetOut
from app.routers.groundwork import require_projects
from app.routers.groundwork_room.common import module_project
from app.tenant import TenantContext, get_conn

router = APIRouter()


@router.get("/projects/{project_id}/budget", response_model=BudgetOut)
async def get_budget(
    project_id: UUID,
    ctx: TenantContext = Depends(require_projects),
    conn: asyncpg.Connection = Depends(get_conn),
):
    await module_project(conn, project_id)
    rows = await conn.fetch(
        "select * from proj_budget_lines where project_id = $1 order by position", project_id
    )
    lines = [
        {
            **dict(r),
            "budget": float(r["budget"]),
            "forecast": float(r["forecast"]),
            "actual": float(r["actual"]),
        }
        for r in rows
    ]
    budget = sum(line["budget"] for line in lines)
    forecast = sum(line["forecast"] for line in lines)
    actual = sum(line["actual"] for line in lines)
    return {
        "lines": lines,
        "totals": {
            "budget": budget,
            "forecast": forecast,
            "actual": actual,
            "variance": forecast - budget,
        },
    }


@router.put("/projects/{project_id}/budget", response_model=BudgetOut)
async def put_budget(
    project_id: UUID,
    body: list[BudgetLineIn],
    ctx: TenantContext = Depends(require_projects),
    conn: asyncpg.Connection = Depends(get_conn),
):
    await module_project(conn, project_id)
    await conn.execute("delete from proj_budget_lines where project_id = $1", project_id)
    for position, line in enumerate(body):
        await conn.execute(
            """
            insert into proj_budget_lines (tenant_id, project_id, category, label,
                                           budget, forecast, actual, note, position)
            values ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            """,
            ctx.tenant_id,
            project_id,
            line.category,
            line.label,
            line.budget,
            line.forecast,
            line.actual,
            line.note,
            position,
        )
    await write_audit(
        conn, ctx.tenant_id, ctx.user_id, "projects.budget_update", "project", str(project_id)
    )
    return await get_budget(project_id, ctx, conn)
