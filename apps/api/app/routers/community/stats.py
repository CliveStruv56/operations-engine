"""Community statistics: the numeric series, and the bridge to the register.

A stat that names a `claim_kind` asserts a confirmed claim on every save —
the person saving the figure IS the assertion, so a second confirm screen
would be theatre (the same ruling as typed claims). The claim is not retracted
when the stat is deleted or re-pointed at another kind: a claim is what the
workspace asserts until it is superseded or managed in the register, and the
module feeding it does not own it.
"""

from datetime import date
from typing import Any
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends

from app.audit import write_audit
from app.claims.service import assert_module_claim, load_kinds
from app.community.schemas import StatIn, StatOut, StatPatch
from app.errors import ApiError
from app.routers.community.common import require_community
from app.sqlutil import patch_sets
from app.tenant import TenantContext, get_conn

router = APIRouter()

_FIELDS = (
    "id, label, value, unit, period, as_of, claim_kind, source, source_url,"
    " notes, created_by, created_at, updated_at"
)


def _out(row: asyncpg.Record, claim_id: UUID | None = None) -> dict[str, Any]:
    out = dict(row)
    out["value"] = float(out["value"])
    out["claim_id"] = claim_id
    return out


async def _check_kind(conn: asyncpg.Connection, kind_key: str | None) -> None:
    if kind_key is None:
        return
    if kind_key not in await load_kinds(conn):
        raise ApiError(
            422, "unknown_claim_kind", f"“{kind_key}” is not a kind of fact we recognise"
        )


async def _feed_register(
    conn: asyncpg.Connection, ctx: TenantContext, row: asyncpg.Record
) -> UUID | None:
    if row["claim_kind"] is None:
        return None
    claim = await assert_module_claim(
        conn,
        ctx.tenant_id,
        ctx.user_id,
        row["claim_kind"],
        float(row["value"]),
        period=row["period"],
        as_of=row["as_of"],
        source_ref=row["source_url"],
        today=date.today(),
    )
    return claim.id if claim else None


@router.get("/community/statistics", response_model=list[StatOut])
async def list_stats(
    ctx: TenantContext = Depends(require_community),
    conn: asyncpg.Connection = Depends(get_conn),
):
    rows = await conn.fetch(
        f"select {_FIELDS} from community_statistics order by label, period nulls first"
    )
    return [_out(r) for r in rows]


@router.post("/community/statistics", status_code=201, response_model=StatOut)
async def create_stat(
    body: StatIn,
    ctx: TenantContext = Depends(require_community),
    conn: asyncpg.Connection = Depends(get_conn),
):
    await _check_kind(conn, body.claim_kind)
    try:
        row = await conn.fetchrow(
            f"""
            insert into community_statistics (tenant_id, label, value, unit, period, as_of,
                claim_kind, source, source_url, notes, created_by)
            values ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
            returning {_FIELDS}
            """,
            ctx.tenant_id,
            body.label,
            body.value,
            body.unit,
            body.period,
            body.as_of,
            body.claim_kind,
            body.source,
            body.source_url,
            body.notes,
            ctx.user_id,
        )
    except asyncpg.UniqueViolationError:
        raise ApiError(
            409, "duplicate_statistic", "A statistic already feeds this fact for this period"
        ) from None
    claim_id = await _feed_register(conn, ctx, row)
    await write_audit(
        conn, ctx.tenant_id, ctx.user_id, "community.stat_create", "statistic", str(row["id"])
    )
    return _out(row, claim_id)


@router.patch("/community/statistics/{stat_id}", response_model=StatOut)
async def patch_stat(
    stat_id: UUID,
    body: StatPatch,
    ctx: TenantContext = Depends(require_community),
    conn: asyncpg.Connection = Depends(get_conn),
):
    updates = body.model_dump(exclude_unset=True)
    if not updates:
        raise ApiError(400, "no_changes", "Nothing to update")
    if updates.get("claim_kind") is not None:
        await _check_kind(conn, updates["claim_kind"])
    sets, values = patch_sets("community_statistics", updates)
    try:
        row = await conn.fetchrow(
            f"update community_statistics set {sets}, updated_at = now()"
            f" where id = $1 returning {_FIELDS}",
            stat_id,
            *values,
        )
    except asyncpg.UniqueViolationError:
        raise ApiError(
            409, "duplicate_statistic", "A statistic already feeds this fact for this period"
        ) from None
    if row is None:
        raise ApiError(404, "not_found", "Statistic not found")
    claim_id = await _feed_register(conn, ctx, row)
    await write_audit(
        conn, ctx.tenant_id, ctx.user_id, "community.stat_update", "statistic", str(stat_id)
    )
    return _out(row, claim_id)


@router.delete("/community/statistics/{stat_id}", status_code=204)
async def delete_stat(
    stat_id: UUID,
    ctx: TenantContext = Depends(require_community),
    conn: asyncpg.Connection = Depends(get_conn),
):
    deleted = await conn.execute("delete from community_statistics where id = $1", stat_id)
    if deleted == "DELETE 0":
        raise ApiError(404, "not_found", "Statistic not found")
    await write_audit(
        conn, ctx.tenant_id, ctx.user_id, "community.stat_delete", "statistic", str(stat_id)
    )
