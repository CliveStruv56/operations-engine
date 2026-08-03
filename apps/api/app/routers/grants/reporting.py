"""Reporting periods and the tenant-wide obligation calendar.

The calendar is the module's reason to exist: a charity's exposure is not the
bid it is writing, it is the four monitoring returns it forgot were due. It
reads across every application, so it is a top-level route rather than a
subresource.
"""

from datetime import date
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends

from app.audit import write_audit
from app.errors import ApiError
from app.grants.analytics import return_rag
from app.grants.schemas import (
    CalendarRow,
    ReportingPeriodIn,
    ReportingPeriodOut,
    ReportingPeriodPatch,
)
from app.routers.grants.common import module_application, require_grants
from app.sqlutil import patch_sets
from app.tenant import TenantContext, get_conn

router = APIRouter()

OPEN_STATUSES = ("upcoming", "open", "drafting")


def _period_out(row: asyncpg.Record, today: date) -> dict:
    return {
        **dict(row),
        "overdue": (
            row["status"] in OPEN_STATUSES
            and row["due_date"] is not None
            and row["due_date"] < today
        ),
    }


@router.get("/grants/reporting-calendar", response_model=list[CalendarRow])
async def reporting_calendar(
    ctx: TenantContext = Depends(require_grants),
    conn: asyncpg.Connection = Depends(get_conn),
):
    """Every obligation not yet accepted, soonest first, with its RAG."""
    rows = await conn.fetch(
        """
        select r.*, a.title as application_title, f.name as funder_name
        from grant_reporting_periods r
        join grant_applications a on a.id = r.application_id
        left join grant_funders f on f.id = a.funder_id
        where r.status not in ('accepted', 'na')
        order by r.due_date nulls last, r.period_end
        """
    )
    today = date.today()
    return [
        {
            **_period_out(row, today),
            "application_title": row["application_title"],
            "funder_name": row["funder_name"],
            "rag": return_rag(row["due_date"], row["status"], today),
        }
        for row in rows
    ]


@router.get(
    "/grants/applications/{application_id}/reporting-periods",
    response_model=list[ReportingPeriodOut],
)
async def list_periods(
    application_id: UUID,
    ctx: TenantContext = Depends(require_grants),
    conn: asyncpg.Connection = Depends(get_conn),
):
    await module_application(conn, application_id)
    rows = await conn.fetch(
        "select * from grant_reporting_periods where application_id = $1 order by period_start",
        application_id,
    )
    today = date.today()
    return [_period_out(r, today) for r in rows]


@router.post(
    "/grants/applications/{application_id}/reporting-periods",
    status_code=201,
    response_model=ReportingPeriodOut,
)
async def create_period(
    application_id: UUID,
    body: ReportingPeriodIn,
    ctx: TenantContext = Depends(require_grants),
    conn: asyncpg.Connection = Depends(get_conn),
):
    await module_application(conn, application_id)
    if body.period_end < body.period_start:
        raise ApiError(422, "bad_period", "The period must end on or after it starts")
    try:
        row = await conn.fetchrow(
            """
            insert into grant_reporting_periods (tenant_id, application_id, label, period_start,
                                                 period_end, due_date, notes)
            values ($1, $2, $3, $4, $5, $6, $7) returning *
            """,
            ctx.tenant_id,
            application_id,
            body.label,
            body.period_start,
            body.period_end,
            body.due_date,
            body.notes,
        )
    except asyncpg.UniqueViolationError:
        raise ApiError(
            409, "duplicate_period", "This application already has a period with that label"
        ) from None
    await write_audit(
        conn,
        ctx.tenant_id,
        ctx.user_id,
        "grants.period_create",
        "grant_reporting_period",
        str(row["id"]),
    )
    return _period_out(row, date.today())


@router.patch(
    "/grants/applications/{application_id}/reporting-periods/{period_id}",
    response_model=ReportingPeriodOut,
)
async def patch_period(
    application_id: UUID,
    period_id: UUID,
    body: ReportingPeriodPatch,
    ctx: TenantContext = Depends(require_grants),
    conn: asyncpg.Connection = Depends(get_conn),
):
    updates = body.model_dump(exclude_unset=True)
    if not updates:
        raise ApiError(400, "no_changes", "Nothing to update")
    sets, values = patch_sets("grant_reporting_periods", updates, id_param=2)
    try:
        row = await conn.fetchrow(
            f"""update grant_reporting_periods set {sets}, updated_at = now()
                where application_id = $1 and id = $2 returning *""",
            application_id,
            period_id,
            *values,
        )
    except asyncpg.UniqueViolationError:
        raise ApiError(
            409, "duplicate_period", "This application already has a period with that label"
        ) from None
    if row is None:
        raise ApiError(404, "not_found", "Reporting period not found")
    await write_audit(
        conn,
        ctx.tenant_id,
        ctx.user_id,
        "grants.period_update",
        "grant_reporting_period",
        str(period_id),
    )
    return _period_out(row, date.today())


@router.delete(
    "/grants/applications/{application_id}/reporting-periods/{period_id}", status_code=204
)
async def delete_period(
    application_id: UUID,
    period_id: UUID,
    ctx: TenantContext = Depends(require_grants),
    conn: asyncpg.Connection = Depends(get_conn),
):
    """Outcomes recorded against the period go with it; any monitoring return
    already drafted for it does not (the registry FK is `set null`)."""
    deleted = await conn.execute(
        "delete from grant_reporting_periods where application_id = $1 and id = $2",
        application_id,
        period_id,
    )
    if deleted == "DELETE 0":
        raise ApiError(404, "not_found", "Reporting period not found")
    await write_audit(
        conn,
        ctx.tenant_id,
        ctx.user_id,
        "grants.period_delete",
        "grant_reporting_period",
        str(period_id),
    )
