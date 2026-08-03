"""Impact measures and the outcomes recorded against them.

This is the pair the monitoring return renders from. Figures in a draft come
from these rows as real tables and never from model output, so an outcome
value is a fact the user entered, not a number a model produced.
"""

from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends

from app.audit import write_audit
from app.errors import ApiError
from app.grants.schemas import (
    MeasureIn,
    MeasureOut,
    MeasurePatch,
    OutcomeIn,
    OutcomeOut,
)
from app.routers.grants.common import module_application, require_grants
from app.sqlutil import patch_sets
from app.tenant import TenantContext, get_conn

router = APIRouter()

_OUTCOME_SELECT = """
select o.*, m.name as measure_name, m.unit, m.target
from grant_outcomes o
join grant_impact_measures m on m.id = o.measure_id
"""


@router.get("/grants/applications/{application_id}/measures", response_model=list[MeasureOut])
async def list_measures(
    application_id: UUID,
    ctx: TenantContext = Depends(require_grants),
    conn: asyncpg.Connection = Depends(get_conn),
):
    await module_application(conn, application_id)
    rows = await conn.fetch(
        "select * from grant_impact_measures where application_id = $1 order by position, name",
        application_id,
    )
    return [dict(r) for r in rows]


@router.post(
    "/grants/applications/{application_id}/measures", status_code=201, response_model=MeasureOut
)
async def create_measure(
    application_id: UUID,
    body: MeasureIn,
    ctx: TenantContext = Depends(require_grants),
    conn: asyncpg.Connection = Depends(get_conn),
):
    await module_application(conn, application_id)
    position = await conn.fetchval(
        "select coalesce(max(position), 0) + 1 from grant_impact_measures"
        " where application_id = $1",
        application_id,
    )
    try:
        row = await conn.fetchrow(
            """
            insert into grant_impact_measures (tenant_id, application_id, name, definition,
                                               unit, baseline, target, position, notes)
            values ($1, $2, $3, $4, $5, $6, $7, $8, $9) returning *
            """,
            ctx.tenant_id,
            application_id,
            body.name,
            body.definition,
            body.unit,
            body.baseline,
            body.target,
            position,
            body.notes,
        )
    except asyncpg.UniqueViolationError:
        raise ApiError(
            409, "duplicate_measure", "This application already has a measure with that name"
        ) from None
    await write_audit(
        conn,
        ctx.tenant_id,
        ctx.user_id,
        "grants.measure_create",
        "grant_impact_measure",
        str(row["id"]),
    )
    return dict(row)


@router.patch(
    "/grants/applications/{application_id}/measures/{measure_id}", response_model=MeasureOut
)
async def patch_measure(
    application_id: UUID,
    measure_id: UUID,
    body: MeasurePatch,
    ctx: TenantContext = Depends(require_grants),
    conn: asyncpg.Connection = Depends(get_conn),
):
    updates = body.model_dump(exclude_unset=True)
    if not updates:
        raise ApiError(400, "no_changes", "Nothing to update")
    sets, values = patch_sets("grant_impact_measures", updates, id_param=2)
    try:
        row = await conn.fetchrow(
            f"""update grant_impact_measures set {sets}
                where application_id = $1 and id = $2 returning *""",
            application_id,
            measure_id,
            *values,
        )
    except asyncpg.UniqueViolationError:
        raise ApiError(
            409, "duplicate_measure", "This application already has a measure with that name"
        ) from None
    if row is None:
        raise ApiError(404, "not_found", "Measure not found")
    await write_audit(
        conn,
        ctx.tenant_id,
        ctx.user_id,
        "grants.measure_update",
        "grant_impact_measure",
        str(measure_id),
    )
    return dict(row)


@router.delete("/grants/applications/{application_id}/measures/{measure_id}", status_code=204)
async def delete_measure(
    application_id: UUID,
    measure_id: UUID,
    ctx: TenantContext = Depends(require_grants),
    conn: asyncpg.Connection = Depends(get_conn),
):
    """Deleting a measure takes its recorded outcomes with it — the values
    have no meaning without the measure that defined them."""
    deleted = await conn.execute(
        "delete from grant_impact_measures where application_id = $1 and id = $2",
        application_id,
        measure_id,
    )
    if deleted == "DELETE 0":
        raise ApiError(404, "not_found", "Measure not found")
    await write_audit(
        conn,
        ctx.tenant_id,
        ctx.user_id,
        "grants.measure_delete",
        "grant_impact_measure",
        str(measure_id),
    )


@router.get(
    "/grants/applications/{application_id}/reporting-periods/{period_id}/outcomes",
    response_model=list[OutcomeOut],
)
async def list_outcomes(
    application_id: UUID,
    period_id: UUID,
    ctx: TenantContext = Depends(require_grants),
    conn: asyncpg.Connection = Depends(get_conn),
):
    await _visible_period(conn, application_id, period_id)
    rows = await conn.fetch(
        f"{_OUTCOME_SELECT} where o.reporting_period_id = $1 order by m.position, m.name",
        period_id,
    )
    return [dict(r) for r in rows]


@router.put(
    "/grants/applications/{application_id}/reporting-periods/{period_id}/outcomes/{measure_id}",
    response_model=OutcomeOut,
)
async def record_outcome(
    application_id: UUID,
    period_id: UUID,
    measure_id: UUID,
    body: OutcomeIn,
    ctx: TenantContext = Depends(require_grants),
    conn: asyncpg.Connection = Depends(get_conn),
):
    """Upsert: one value per measure per period, so re-recording corrects
    rather than duplicating (the table's unique constraint says the same)."""
    await _visible_period(conn, application_id, period_id)
    if not await conn.fetchval(
        "select 1 from grant_impact_measures where id = $1 and application_id = $2",
        measure_id,
        application_id,
    ):
        raise ApiError(404, "not_found", "Measure not found")
    row = await conn.fetchrow(
        """
        insert into grant_outcomes (tenant_id, measure_id, reporting_period_id, value,
                                    narrative, evidence_notes, recorded_by)
        values ($1, $2, $3, $4, $5, $6, $7)
        on conflict (measure_id, reporting_period_id) do update
        set value = excluded.value, narrative = excluded.narrative,
            evidence_notes = excluded.evidence_notes, recorded_by = excluded.recorded_by,
            recorded_at = now()
        returning id
        """,
        ctx.tenant_id,
        measure_id,
        period_id,
        body.value,
        body.narrative,
        body.evidence_notes,
        ctx.user_id,
    )
    await write_audit(
        conn,
        ctx.tenant_id,
        ctx.user_id,
        "grants.outcome_record",
        "grant_outcome",
        str(row["id"]),
        {"measure_id": str(measure_id), "reporting_period_id": str(period_id)},
    )
    return dict(await conn.fetchrow(f"{_OUTCOME_SELECT} where o.id = $1", row["id"]))


async def _visible_period(conn: asyncpg.Connection, application_id: UUID, period_id: UUID) -> None:
    """Both ids are checked together: a period id that belongs to another of
    the tenant's applications must not be writable through this one."""
    await module_application(conn, application_id)
    if not await conn.fetchval(
        "select 1 from grant_reporting_periods where id = $1 and application_id = $2",
        period_id,
        application_id,
    ):
        raise ApiError(404, "not_found", "Reporting period not found")
