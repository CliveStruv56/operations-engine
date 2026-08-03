"""Applications: create + seed the spine, portfolio, detail, status.

An application is a standalone row rather than a core-project extension
(ASSUMPTIONS #23) — a charity's portfolio is many and churns, where a
Groundwork project is few and long-lived. `project_id` is the optional soft
link back to a core project when a bid funds one.
"""

import json
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, Query

from app.audit import write_audit
from app.errors import ApiError
from app.grants.analytics import weighted_value
from app.grants.schemas import (
    ApplicationCreatedOut,
    ApplicationIn,
    ApplicationOut,
    ApplicationPatch,
    ApplicationStatusIn,
    PortfolioRow,
)
from app.routers.grants.common import module_application, require_grants, visible_funder
from app.routers.grants.common import visible_project as _visible_project
from app.sqlutil import patch_sets
from app.tenant import TenantContext, get_conn

router = APIRouter()

_SELECT = """
select a.*, f.name as funder_name, p.name as project_name
from grant_applications a
left join grant_funders f on f.id = a.funder_id
left join projects p on p.id = a.project_id
"""


@router.post("/grants/applications", status_code=201, response_model=ApplicationCreatedOut)
async def create_application(
    body: ApplicationIn,
    ctx: TenantContext = Depends(require_grants),
    conn: asyncpg.Connection = Depends(get_conn),
):
    """Create the application and seed its spine from the template library."""
    if body.funder_id is not None:
        await visible_funder(conn, body.funder_id)
    if body.project_id is not None:
        await _visible_project(conn, body.project_id)

    template = await conn.fetchval(
        "select payload from grant_ref_templates where key = $1", body.application_type
    )
    if template is None:
        raise ApiError(503, "not_seeded", "Application templates have not been loaded")
    payload = json.loads(template)

    row = await conn.fetchrow(
        """
        insert into grant_applications (tenant_id, funder_id, project_id, title, reference,
                                        application_type, programme_key, stage_current,
                                        amount_requested, restricted, deadline, start_date,
                                        end_date, reporting_note, notes, created_by)
        values ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16)
        returning id
        """,
        ctx.tenant_id,
        body.funder_id,
        body.project_id,
        body.title,
        body.reference,
        body.application_type,
        body.programme_key,
        payload["stages"][0]["stage_key"],
        body.amount_requested,
        body.restricted,
        body.deadline,
        body.start_date,
        body.end_date,
        body.reporting_note,
        body.notes,
        ctx.user_id,
    )
    application_id = row["id"]

    for stage in payload["stages"]:
        await conn.execute(
            """
            insert into grant_stages (tenant_id, application_id, stage_key, label,
                                      position, status, gate)
            values ($1, $2, $3, $4, $5, $6, $7)
            """,
            ctx.tenant_id,
            application_id,
            stage["stage_key"],
            stage["label"],
            stage["position"],
            "active" if stage["position"] == 1 else "pending",
            json.dumps([{**item, "done": False} for item in stage["gate"]]),
        )

    for position, task in enumerate(payload["tasks"]):
        await conn.execute(
            """
            insert into grant_tasks (tenant_id, application_id, stage_key, title, details,
                                     is_milestone, tags, position)
            values ($1, $2, $3, $4, $5, $6, $7, $8)
            """,
            ctx.tenant_id,
            application_id,
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
            insert into grant_documents (tenant_id, application_id, doc_type_key, title,
                                         stage_key, ai_draftable)
            values ($1, $2, $3, $4, $5, $6)
            """,
            ctx.tenant_id,
            application_id,
            doc["doc_type_key"],
            doc["title"],
            doc["stage_key"],
            doc["ai_draftable"],
        )

    await write_audit(
        conn,
        ctx.tenant_id,
        ctx.user_id,
        "grants.application_create",
        "grant_application",
        str(application_id),
        {"application_type": body.application_type},
    )
    return {
        "id": application_id,
        "stage_current": payload["stages"][0]["stage_key"],
        "seeded": {
            "stages": len(payload["stages"]),
            "tasks": len(payload["tasks"]),
            "doc_types": len(payload["doc_types"]),
        },
    }


@router.get("/grants/applications", response_model=list[PortfolioRow])
async def portfolio(
    status: str | None = Query(default=None, max_length=20),
    funder_id: UUID | None = None,
    ctx: TenantContext = Depends(require_grants),
    conn: asyncpg.Connection = Depends(get_conn),
):
    clauses: list[str] = []
    params: list[object] = []
    if status:
        params.append(status)
        clauses.append(f"a.status = ${len(params)}")
    if funder_id:
        params.append(funder_id)
        clauses.append(f"a.funder_id = ${len(params)}")
    where = f"where {' and '.join(clauses)}" if clauses else ""
    rows = await conn.fetch(
        f"""
        select a.id, a.title, a.funder_id, f.name as funder_name, a.status, a.stage_current,
               a.amount_requested, a.amount_awarded, a.restricted, a.deadline, a.updated_at
        from grant_applications a
        left join grant_funders f on f.id = a.funder_id
        {where}
        order by a.status, a.deadline nulls last, a.title
        """,
        *params,
    )
    conditions = {
        r["application_id"]: r["open_count"]
        for r in await conn.fetch(
            """
            select application_id, count(*) as open_count from grant_conditions
            where status in ('outstanding', 'partially_discharged')
            group by application_id
            """
        )
    }
    returns = {
        r["application_id"]: r
        for r in await conn.fetch(
            """
            select application_id,
                   count(*) filter (where due_date < current_date) as overdue_count,
                   min(due_date) as next_due
            from grant_reporting_periods
            where status in ('upcoming', 'open', 'drafting') and due_date is not null
            group by application_id
            """
        )
    }
    out = []
    for row in rows:
        due = returns.get(row["id"])
        out.append(
            {
                **dict(row),
                "weighted_value": weighted_value(
                    row["status"],
                    row["stage_current"],
                    row["amount_requested"],
                    row["amount_awarded"],
                ),
                "open_conditions": conditions.get(row["id"], 0),
                "overdue_returns": (due["overdue_count"] if due else 0),
                "next_return_due": (due["next_due"] if due else None),
            }
        )
    return out


@router.get("/grants/applications/{application_id}", response_model=ApplicationOut)
async def get_application(
    application_id: UUID,
    ctx: TenantContext = Depends(require_grants),
    conn: asyncpg.Connection = Depends(get_conn),
):
    row = await conn.fetchrow(f"{_SELECT} where a.id = $1", application_id)
    if row is None:
        raise ApiError(404, "not_found", "Application not found")
    return dict(row)


@router.patch("/grants/applications/{application_id}", response_model=ApplicationOut)
async def patch_application(
    application_id: UUID,
    body: ApplicationPatch,
    ctx: TenantContext = Depends(require_grants),
    conn: asyncpg.Connection = Depends(get_conn),
):
    updates = body.model_dump(exclude_unset=True)
    if not updates:
        raise ApiError(400, "no_changes", "Nothing to update")
    if updates.get("funder_id") is not None:
        await visible_funder(conn, updates["funder_id"])
    if updates.get("project_id") is not None:
        await _visible_project(conn, updates["project_id"])
    sets, values = patch_sets("grant_applications", updates)
    row = await conn.fetchrow(
        f"update grant_applications set {sets}, updated_at = now() where id = $1 returning id",
        application_id,
        *values,
    )
    if row is None:
        raise ApiError(404, "not_found", "Application not found")
    await write_audit(
        conn,
        ctx.tenant_id,
        ctx.user_id,
        "grants.application_update",
        "grant_application",
        str(application_id),
    )
    return dict(await conn.fetchrow(f"{_SELECT} where a.id = $1", application_id))


@router.post("/grants/applications/{application_id}/status", response_model=ApplicationOut)
async def set_status(
    application_id: UUID,
    body: ApplicationStatusIn,
    ctx: TenantContext = Depends(require_grants),
    conn: asyncpg.Connection = Depends(get_conn),
):
    """Move the application through the pipeline.

    An award is the moment the funder's standard conditions become real, so
    this is where the template's common conditions are seeded — never at
    creation, when the application has no offer and no conditions to meet.
    """
    application = await module_application(conn, application_id)
    awarding = body.status == "awarded"
    if awarding and body.amount_awarded is None and not application["amount_awarded"]:
        raise ApiError(422, "amount_required", "Recording an award needs the amount offered")

    await conn.execute(
        """
        update grant_applications
        set status = $2,
            amount_awarded = coalesce($3, amount_awarded),
            decision_at = coalesce($4, decision_at),
            submitted_at = coalesce($5, submitted_at),
            notes = coalesce($6, notes),
            updated_at = now()
        where id = $1
        """,
        application_id,
        body.status,
        body.amount_awarded,
        body.decision_at,
        body.submitted_at,
        body.notes,
    )
    seeded = 0
    if awarding:
        seeded = await _seed_award_conditions(conn, ctx, application_id, application)
    await write_audit(
        conn,
        ctx.tenant_id,
        ctx.user_id,
        "grants.application_status",
        "grant_application",
        str(application_id),
        {"status": body.status, "conditions_seeded": seeded},
    )
    return dict(await conn.fetchrow(f"{_SELECT} where a.id = $1", application_id))


@router.delete("/grants/applications/{application_id}", status_code=204)
async def delete_application(
    application_id: UUID,
    ctx: TenantContext = Depends(require_grants),
    conn: asyncpg.Connection = Depends(get_conn),
):
    deleted = await conn.execute("delete from grant_applications where id = $1", application_id)
    if deleted == "DELETE 0":
        raise ApiError(404, "not_found", "Application not found")
    await write_audit(
        conn,
        ctx.tenant_id,
        ctx.user_id,
        "grants.application_delete",
        "grant_application",
        str(application_id),
    )


async def _seed_award_conditions(
    conn: asyncpg.Connection,
    ctx: TenantContext,
    application_id: UUID,
    application: asyncpg.Record,
) -> int:
    """Seed the template's common conditions on first award only.

    Idempotent by design: a re-recorded award must not duplicate the register,
    and conditions the user has already edited are theirs, not ours.
    """
    if await conn.fetchval(
        "select 1 from grant_conditions where application_id = $1", application_id
    ):
        return 0
    template = await conn.fetchval(
        "select payload from grant_ref_templates where key = $1",
        application["application_type"],
    )
    if template is None:
        return 0
    conditions = json.loads(template).get("conditions", [])
    for condition in conditions:
        await conn.execute(
            """
            insert into grant_conditions (tenant_id, application_id, number, description,
                                          pre_drawdown)
            values ($1, $2, $3, $4, $5)
            """,
            ctx.tenant_id,
            application_id,
            condition["number"],
            condition["description"],
            condition.get("pre_drawdown", False),
        )
    return len(conditions)
