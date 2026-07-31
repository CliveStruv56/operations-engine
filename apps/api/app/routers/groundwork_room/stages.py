"""Stages & gates: date planning, gate item toggles, gate sign-off + advance."""

import json
from datetime import UTC, datetime
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends

from app.audit import write_audit
from app.errors import ApiError
from app.groundwork.schemas import SignoffIn, StageOut, StagePatch
from app.routers.groundwork import require_projects
from app.routers.groundwork_room.common import module_project, stage_out
from app.sqlutil import patch_sets
from app.tenant import TenantContext, get_conn

router = APIRouter()


@router.get("/projects/{project_id}/stages", response_model=list[StageOut])
async def list_stages(
    project_id: UUID,
    ctx: TenantContext = Depends(require_projects),
    conn: asyncpg.Connection = Depends(get_conn),
):
    await module_project(conn, project_id)
    rows = await conn.fetch(
        "select * from proj_stages where project_id = $1 order by position", project_id
    )
    return [stage_out(r) for r in rows]


@router.patch("/projects/{project_id}/stages/{stage_id}", response_model=StageOut)
async def patch_stage(
    project_id: UUID,
    stage_id: UUID,
    body: StagePatch,
    ctx: TenantContext = Depends(require_projects),
    conn: asyncpg.Connection = Depends(get_conn),
):
    updates = body.model_dump(exclude_unset=True)
    note = updates.pop("note", None)
    if updates.get("status") == "regressed" and not note:
        raise ApiError(400, "note_required", "Regressing a stage needs a note")
    if not updates and not note:
        raise ApiError(400, "no_changes", "Nothing to update")
    if note:
        # Stage rows have no free-notes column (PRD §1); regression/context
        # notes append to gate_exceptions, timestamped.
        stamp = datetime.now(UTC).strftime("%d %b %Y")
        updates["gate_exceptions"] = None  # placeholder replaced below
    row = await conn.fetchrow(
        "select gate_exceptions from proj_stages where project_id = $1 and id = $2",
        project_id,
        stage_id,
    )
    if row is None:
        raise ApiError(404, "not_found", "Stage not found")
    if note:
        existing = row["gate_exceptions"]
        updates["gate_exceptions"] = (
            f"{existing}\n[{stamp}] {note}" if existing else f"[{stamp}] {note}"
        )
    sets, values = patch_sets("proj_stages", updates)
    updated = await conn.fetchrow(
        f"update proj_stages set {sets} where id = $1 returning *", stage_id, *values
    )
    await write_audit(
        conn, ctx.tenant_id, ctx.user_id, "projects.stage_update", "stage", str(stage_id)
    )
    return stage_out(updated)


@router.post(
    "/projects/{project_id}/stages/{stage_id}/gate/{item_id}/toggle",
    response_model=StageOut,
)
async def toggle_gate_item(
    project_id: UUID,
    stage_id: UUID,
    item_id: str,
    ctx: TenantContext = Depends(require_projects),
    conn: asyncpg.Connection = Depends(get_conn),
):
    row = await conn.fetchrow(
        "select gate, gate_signed_off_at from proj_stages where project_id = $1 and id = $2",
        project_id,
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
        "update proj_stages set gate = $2 where id = $1 returning *", stage_id, json.dumps(gate)
    )
    await write_audit(
        conn, ctx.tenant_id, ctx.user_id, "projects.gate_toggle", "stage", str(stage_id)
    )
    return stage_out(updated)


@router.post("/projects/{project_id}/stages/{stage_id}/signoff", response_model=StageOut)
async def signoff_stage(
    project_id: UUID,
    stage_id: UUID,
    body: SignoffIn,
    ctx: TenantContext = Depends(require_projects),
    conn: asyncpg.Connection = Depends(get_conn),
):
    row = await conn.fetchrow(
        "select * from proj_stages where project_id = $1 and id = $2", project_id, stage_id
    )
    if row is None:
        raise ApiError(404, "not_found", "Stage not found")
    if row["gate_signed_off_at"] is not None:
        raise ApiError(409, "already_signed_off", "This gate is already signed off")
    # Only the project's active stage can be signed off — no stage skipping.
    project = await conn.fetchrow(
        "select stage_current from proj_projects where id = $1", project_id
    )
    if project is None or row["stage_key"] != project["stage_current"]:
        raise ApiError(
            422,
            "stage_not_active",
            "Only the project's current stage can be signed off",
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
        update proj_stages
        set status = 'passed', gate_signed_off_by = $2, gate_signed_off_at = now(),
            gate_exceptions = coalesce($3, gate_exceptions)
        where id = $1 returning *
        """,
        stage_id,
        ctx.user_id,
        body.exceptions,
    )
    # Advance: activate the next pending stage and move the project pointer.
    next_stage = await conn.fetchrow(
        """
        update proj_stages set status = 'active'
        where project_id = $1 and position = $2 and status = 'pending'
        returning stage_key
        """,
        project_id,
        row["position"] + 1,
    )
    if next_stage:
        await conn.execute(
            "update proj_projects set stage_current = $2, updated_at = now() where id = $1",
            project_id,
            next_stage["stage_key"],
        )
    await write_audit(
        conn, ctx.tenant_id, ctx.user_id, "projects.gate_signoff", "stage", str(stage_id)
    )
    return stage_out(updated)
