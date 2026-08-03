"""Award conditions: what the funder attached to the money.

The register is seeded from the template on first award
(`applications.py::_seed_award_conditions`) and edited from there — a real
offer letter always adds its own.
"""

from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends

from app.audit import write_audit
from app.errors import ApiError
from app.grants.schemas import ConditionIn, ConditionOut, ConditionPatch
from app.routers.grants.common import module_application, require_grants
from app.sqlutil import patch_sets
from app.tenant import TenantContext, get_conn

router = APIRouter()


@router.get("/grants/applications/{application_id}/conditions", response_model=list[ConditionOut])
async def list_conditions(
    application_id: UUID,
    ctx: TenantContext = Depends(require_grants),
    conn: asyncpg.Connection = Depends(get_conn),
):
    await module_application(conn, application_id)
    rows = await conn.fetch(
        "select * from grant_conditions where application_id = $1"
        " order by pre_drawdown desc, number",
        application_id,
    )
    return [dict(r) for r in rows]


@router.post(
    "/grants/applications/{application_id}/conditions",
    status_code=201,
    response_model=ConditionOut,
)
async def create_condition(
    application_id: UUID,
    body: ConditionIn,
    ctx: TenantContext = Depends(require_grants),
    conn: asyncpg.Connection = Depends(get_conn),
):
    await module_application(conn, application_id)
    row = await conn.fetchrow(
        """
        insert into grant_conditions (tenant_id, application_id, number, description,
                                      pre_drawdown, due_date, notes)
        values ($1, $2, $3, $4, $5, $6, $7) returning *
        """,
        ctx.tenant_id,
        application_id,
        body.number,
        body.description,
        body.pre_drawdown,
        body.due_date,
        body.notes,
    )
    await write_audit(
        conn,
        ctx.tenant_id,
        ctx.user_id,
        "grants.condition_create",
        "grant_condition",
        str(row["id"]),
    )
    return dict(row)


@router.patch(
    "/grants/applications/{application_id}/conditions/{condition_id}",
    response_model=ConditionOut,
)
async def patch_condition(
    application_id: UUID,
    condition_id: UUID,
    body: ConditionPatch,
    ctx: TenantContext = Depends(require_grants),
    conn: asyncpg.Connection = Depends(get_conn),
):
    updates = body.model_dump(exclude_unset=True)
    if not updates:
        raise ApiError(400, "no_changes", "Nothing to update")
    sets, values = patch_sets("grant_conditions", updates, id_param=2)
    row = await conn.fetchrow(
        f"""update grant_conditions set {sets}
            where application_id = $1 and id = $2 returning *""",
        application_id,
        condition_id,
        *values,
    )
    if row is None:
        raise ApiError(404, "not_found", "Condition not found")
    await write_audit(
        conn,
        ctx.tenant_id,
        ctx.user_id,
        "grants.condition_update",
        "grant_condition",
        str(condition_id),
    )
    return dict(row)


@router.delete("/grants/applications/{application_id}/conditions/{condition_id}", status_code=204)
async def delete_condition(
    application_id: UUID,
    condition_id: UUID,
    ctx: TenantContext = Depends(require_grants),
    conn: asyncpg.Connection = Depends(get_conn),
):
    deleted = await conn.execute(
        "delete from grant_conditions where application_id = $1 and id = $2",
        application_id,
        condition_id,
    )
    if deleted == "DELETE 0":
        raise ApiError(404, "not_found", "Condition not found")
    await write_audit(
        conn,
        ctx.tenant_id,
        ctx.user_id,
        "grants.condition_delete",
        "grant_condition",
        str(condition_id),
    )
