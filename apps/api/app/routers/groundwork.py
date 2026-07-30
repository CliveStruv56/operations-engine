"""Groundwork module W1 (PRD §3): setup, portfolio, project status.

Route shape per docs/groundwork/ASSUMPTIONS.md #2: the core owns
POST/GET /projects (containers); this module attaches to an existing core
project via /projects/{id}/setup and lists via /projects/portfolio.

Module gate: every route 404s unless `tenants.features->>'projects' = 'true'`.
"""

import json
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends

from app.audit import write_audit
from app.errors import ApiError
from app.groundwork.rag import compute_rag
from app.schemas import (
    GroundworkSetup,
    GroundworkSetupOut,
    GroundworkStatusIn,
    PortfolioRow,
)
from app.tenant import TenantContext, get_conn, require_role

router = APIRouter(tags=["groundwork"])

TEMPLATE_KEY = "clh_new_build"


async def require_projects(
    ctx: TenantContext = Depends(require_role("member")),
    conn: asyncpg.Connection = Depends(get_conn),
) -> TenantContext:
    enabled = await conn.fetchval(
        "select features->>'projects' = 'true' from tenants where id = $1", ctx.tenant_id
    )
    if not enabled:
        raise ApiError(404, "not_found", "Not found")
    return ctx


@router.post("/projects/{project_id}/setup", status_code=201, response_model=GroundworkSetupOut)
async def setup_project(
    project_id: UUID,
    body: GroundworkSetup,
    ctx: TenantContext = Depends(require_projects),
    conn: asyncpg.Connection = Depends(get_conn),
):
    core = await conn.fetchrow("select id, name from projects where id = $1", project_id)
    if core is None:  # RLS scoped — cross-tenant ids are invisible
        raise ApiError(404, "not_found", "Project not found")
    if await conn.fetchval("select 1 from proj_projects where id = $1", project_id):
        raise ApiError(409, "already_setup", "This project is already a development project")

    template = await conn.fetchval(
        "select payload from proj_ref_templates where key = $1", TEMPLATE_KEY
    )
    if template is None:
        raise ApiError(503, "not_seeded", "Project templates have not been loaded")
    payload = json.loads(template)
    flags = body.applicability

    await conn.execute(
        """
        insert into proj_projects (id, tenant_id, client_org, delivery_route, homes_planned,
                                   start_date, target_completion, site_address, applicability)
        values ($1, $2, $3, $4, $5, $6, $7, $8, $9)
        """,
        project_id,
        ctx.tenant_id,
        body.client_org,
        body.delivery_route,
        body.homes_planned,
        body.start_date,
        body.target_completion,
        body.site_address,
        flags.model_dump_json(),
    )

    for stage in payload["stages"]:
        gate = [{**item, "done": False} for item in stage["gate"]]
        await conn.execute(
            """
            insert into proj_stages (tenant_id, project_id, stage_key, label, riba_ref,
                                     position, status, gate)
            values ($1, $2, $3, $4, $5, $6, $7, $8)
            """,
            ctx.tenant_id,
            project_id,
            stage["stage_key"],
            stage["label"],
            stage["riba_ref"],
            stage["position"],
            "active" if stage["position"] == 1 else "pending",
            json.dumps(gate),
        )

    tasks = [
        t
        for t in payload["tasks"]
        if not (flags.bng_exempt and t["title"] == payload["bng_task_title"])
    ]
    for key, enabled in (
        ("wales", flags.wales),
        ("hrb", flags.hrb),
        ("conservation_area", flags.conservation_area),
    ):
        if enabled:
            tasks.append(payload["applicability_tasks"][key])
    for position, task in enumerate(tasks):
        await conn.execute(
            """
            insert into proj_tasks (tenant_id, project_id, stage_key, title, details,
                                    is_milestone, tags, position)
            values ($1, $2, $3, $4, $5, $6, $7, $8)
            """,
            ctx.tenant_id,
            project_id,
            task["stage_key"],
            task["title"],
            task.get("details"),
            task.get("is_milestone", False),
            task.get("tags", []),
            position,
        )

    for doc in payload["doc_types"]:
        await conn.execute(
            """
            insert into proj_documents (tenant_id, project_id, doc_type_key, title,
                                        stage_key, ai_draftable)
            values ($1, $2, $3, $4, $5, $6)
            """,
            ctx.tenant_id,
            project_id,
            doc["doc_type_key"],
            doc["title"],
            doc["stage_key"],
            doc["ai_draftable"],
        )

    for risk in payload["risks"]:
        await conn.execute(
            """
            insert into proj_risks (tenant_id, project_id, category, description,
                                    likelihood, impact, mitigation)
            values ($1, $2, $3, $4, $5, $6, $7)
            """,
            ctx.tenant_id,
            project_id,
            risk["category"],
            risk["description"],
            risk["likelihood"],
            risk["impact"],
            risk["mitigation"],
        )

    await write_audit(
        conn, ctx.tenant_id, ctx.user_id, "projects.setup", "project", str(project_id)
    )
    return {
        "project_id": project_id,
        "stage_current": "group",
        "seeded": {
            "stages": len(payload["stages"]),
            "tasks": len(tasks),
            "doc_types": len(payload["doc_types"]),
            "risks": len(payload["risks"]),
        },
    }


@router.get("/projects/portfolio", response_model=list[PortfolioRow])
async def portfolio(
    ctx: TenantContext = Depends(require_projects),
    conn: asyncpg.Connection = Depends(get_conn),
):
    rows = await conn.fetch(
        """
        select g.id, p.name, g.client_org, g.status, g.dormancy_reason, g.stage_current,
               g.homes_planned, g.target_completion, g.updated_at
        from proj_projects g join projects p on p.id = g.id
        order by g.status, p.name
        """
    )
    overdue = {
        r["project_id"]: r
        for r in await conn.fetch(
            """
            select project_id,
                   max(current_date - due_date) filter (where is_milestone) as milestone_days,
                   count(*) filter (where due_date < current_date) as overdue_count
            from proj_tasks
            where status in ('todo', 'doing') and due_date is not null
            group by project_id
            """
        )
    }
    budgets = {
        r["project_id"]: r
        for r in await conn.fetch(
            "select project_id, sum(budget) as budget, sum(forecast) as forecast"
            " from proj_budget_lines group by project_id"
        )
    }
    risks = {
        r["project_id"]: r
        for r in await conn.fetch(
            """
            select project_id, max(likelihood * impact) as max_score, count(*) as open_count
            from proj_risks where status = 'open' group by project_id
            """
        )
    }
    conditions = {
        r["project_id"]: r["outstanding"]
        for r in await conn.fetch(
            """
            select project_id, count(*) as outstanding
            from proj_conditions
            where pre_commencement and status = 'outstanding'
            group by project_id
            """
        )
    }
    milestones = {
        r["project_id"]: r
        for r in await conn.fetch(
            """
            select distinct on (project_id) project_id, title, due_date
            from proj_tasks
            where is_milestone and status in ('todo', 'doing') and due_date is not null
            order by project_id, due_date
            """
        )
    }

    out = []
    for row in rows:
        pid = row["id"]
        od = overdue.get(pid)
        budget = budgets.get(pid)
        risk = risks.get(pid)
        milestone = milestones.get(pid)
        rag = compute_rag(
            worst_milestone_overdue_days=max(0, (od["milestone_days"] or 0) if od else 0),
            budget_total=float(budget["budget"]) if budget else 0.0,
            forecast_total=float(budget["forecast"]) if budget else 0.0,
            max_open_risk_score=(risk["max_score"] or 0) if risk else 0,
        )
        out.append(
            {
                **dict(row),
                "rag": {"programme": rag.programme, "cost": rag.cost, "risk": rag.risk},
                "next_milestone": (
                    {"title": milestone["title"], "due_date": milestone["due_date"]}
                    if milestone
                    else None
                ),
                "open_risks": (risk["open_count"] if risk else 0),
                "outstanding_pre_commencement": conditions.get(pid, 0),
                "overdue_tasks": (od["overdue_count"] if od else 0),
            }
        )
    return out


@router.post("/projects/{project_id}/status")
async def set_status(
    project_id: UUID,
    body: GroundworkStatusIn,
    ctx: TenantContext = Depends(require_projects),
    conn: asyncpg.Connection = Depends(get_conn),
):
    if body.status == "dormant" and not body.dormancy_reason:
        raise ApiError(400, "reason_required", "Making a project dormant needs a reason")
    updated = await conn.execute(
        """
        update proj_projects
        set status = $2,
            dormancy_reason = case when $2 = 'dormant' then $3 else null end,
            updated_at = now()
        where id = $1
        """,
        project_id,
        body.status,
        body.dormancy_reason,
    )
    if updated == "UPDATE 0":
        raise ApiError(404, "not_found", "Project not found")
    await write_audit(
        conn, ctx.tenant_id, ctx.user_id, "projects.status", "project", str(project_id)
    )
    return {"id": str(project_id), "status": body.status}
