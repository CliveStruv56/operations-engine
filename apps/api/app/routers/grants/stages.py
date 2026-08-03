"""Stages and gates: date planning, gate item toggles, sign-off and advance.

Same mechanics as Groundwork's: only the application's active stage can be
signed off (no stage skipping), a signed-off gate freezes, and doc-kind items
follow the registry rather than being toggled by hand.
"""

import json
from datetime import UTC, datetime
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends

from app.audit import write_audit
from app.errors import ApiError
from app.grants.schemas import SignoffIn, StageOut, StagePatch
from app.routers.grants.common import module_application, require_grants, stage_out
from app.sqlutil import patch_sets
from app.tenant import TenantContext, get_conn

router = APIRouter()


@router.get("/grants/applications/{application_id}/stages", response_model=list[StageOut])
async def list_stages(
    application_id: UUID,
    ctx: TenantContext = Depends(require_grants),
    conn: asyncpg.Connection = Depends(get_conn),
):
    await module_application(conn, application_id)
    rows = await conn.fetch(
        "select * from grant_stages where application_id = $1 order by position", application_id
    )
    return [stage_out(r) for r in rows]


@router.patch("/grants/applications/{application_id}/stages/{stage_id}", response_model=StageOut)
async def patch_stage(
    application_id: UUID,
    stage_id: UUID,
    body: StagePatch,
    ctx: TenantContext = Depends(require_grants),
    conn: asyncpg.Connection = Depends(get_conn),
):
    updates = body.model_dump(exclude_unset=True)
    note = updates.pop("note", None)
    if updates.get("status") == "regressed" and not note:
        raise ApiError(400, "note_required", "Regressing a stage needs a note")
    if not updates and not note:
        raise ApiError(400, "no_changes", "Nothing to update")
    row = await conn.fetchrow(
        "select gate_exceptions from grant_stages where application_id = $1 and id = $2",
        application_id,
        stage_id,
    )
    if row is None:
        raise ApiError(404, "not_found", "Stage not found")
    if note:
        # Stage rows carry no free-notes column; regression and context notes
        # append to gate_exceptions, timestamped, so the audit reads in order.
        stamp = datetime.now(UTC).strftime("%d %b %Y")
        existing = row["gate_exceptions"]
        updates["gate_exceptions"] = (
            f"{existing}\n[{stamp}] {note}" if existing else f"[{stamp}] {note}"
        )
    sets, values = patch_sets("grant_stages", updates)
    updated = await conn.fetchrow(
        f"update grant_stages set {sets} where id = $1 returning *", stage_id, *values
    )
    await write_audit(
        conn, ctx.tenant_id, ctx.user_id, "grants.stage_update", "grant_stage", str(stage_id)
    )
    return stage_out(updated)


@router.post(
    "/grants/applications/{application_id}/stages/{stage_id}/gate/{item_id}/toggle",
    response_model=StageOut,
)
async def toggle_gate_item(
    application_id: UUID,
    stage_id: UUID,
    item_id: str,
    ctx: TenantContext = Depends(require_grants),
    conn: asyncpg.Connection = Depends(get_conn),
):
    row = await conn.fetchrow(
        "select gate, gate_signed_off_at from grant_stages where application_id = $1 and id = $2",
        application_id,
        stage_id,
    )
    if row is None:
        raise ApiError(404, "not_found", "Stage not found")
    if row["gate_signed_off_at"] is not None:
        raise ApiError(
            409, "already_signed_off", "This gate is signed off — its items can no longer change"
        )
    gate = json.loads(row["gate"])
    item = next((i for i in gate if i["id"] == item_id), None)
    if item is None:
        raise ApiError(404, "not_found", "Gate item not found")
    if item["kind"] != "manual":
        raise ApiError(
            400, "computed_item", "This item follows the document registry and cannot be toggled"
        )
    item["done"] = not item["done"]
    item["done_by"] = str(ctx.user_id) if item["done"] else None
    item["done_at"] = datetime.now(UTC).isoformat() if item["done"] else None
    updated = await conn.fetchrow(
        "update grant_stages set gate = $2 where id = $1 returning *", stage_id, json.dumps(gate)
    )
    await write_audit(
        conn, ctx.tenant_id, ctx.user_id, "grants.gate_toggle", "grant_stage", str(stage_id)
    )
    return stage_out(updated)


@router.post(
    "/grants/applications/{application_id}/stages/{stage_id}/signoff", response_model=StageOut
)
async def signoff_stage(
    application_id: UUID,
    stage_id: UUID,
    body: SignoffIn,
    ctx: TenantContext = Depends(require_grants),
    conn: asyncpg.Connection = Depends(get_conn),
):
    row = await conn.fetchrow(
        "select * from grant_stages where application_id = $1 and id = $2",
        application_id,
        stage_id,
    )
    if row is None:
        raise ApiError(404, "not_found", "Stage not found")
    if row["gate_signed_off_at"] is not None:
        raise ApiError(409, "already_signed_off", "This gate is already signed off")
    application = await conn.fetchrow(
        "select stage_current from grant_applications where id = $1", application_id
    )
    if application is None or row["stage_key"] != application["stage_current"]:
        raise ApiError(
            422, "stage_not_active", "Only the application's current stage can be signed off"
        )
    gate = json.loads(row["gate"])
    outstanding = [i["criterion"] for i in gate if not i["done"]]
    if outstanding and not body.exceptions:
        raise ApiError(
            400,
            "gate_incomplete",
            f"{len(outstanding)} gate item(s) outstanding — complete them or record exceptions",
        )
    updated = await conn.fetchrow(
        """
        update grant_stages
        set status = 'passed', gate_signed_off_by = $2, gate_signed_off_at = now(),
            gate_exceptions = coalesce($3, gate_exceptions)
        where id = $1 returning *
        """,
        stage_id,
        ctx.user_id,
        body.exceptions,
    )
    next_stage = await conn.fetchrow(
        """
        update grant_stages set status = 'active'
        where application_id = $1 and position = $2 and status = 'pending'
        returning stage_key
        """,
        application_id,
        row["position"] + 1,
    )
    if next_stage:
        await conn.execute(
            "update grant_applications set stage_current = $2, updated_at = now() where id = $1",
            application_id,
            next_stage["stage_key"],
        )
    await write_audit(
        conn, ctx.tenant_id, ctx.user_id, "grants.gate_signoff", "grant_stage", str(stage_id)
    )
    return stage_out(updated)
