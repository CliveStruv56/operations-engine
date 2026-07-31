"""Groundwork W2 (PRD §3): project detail, stages & gates, tasks, document
registry with versioned uploads, budget, funding + programme catalogue,
risks, conditions, stakeholders, activity.

All routes sit behind the module feature flag (require_projects) and RLS.
Route order matters: literal paths (portfolio, funding-programmes) are
registered in groundwork.py / here before the {project_id} matcher is hit.
"""

import json
from datetime import UTC, date, datetime
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, Query

from app.audit import write_audit
from app.errors import ApiError
from app.groundwork.gates import recompute_doc_gates
from app.groundwork.schemas import (
    ActivityOut,
    BudgetLineIn,
    BudgetOut,
    BulkCompleteIn,
    ConditionIn,
    ConditionPatch,
    DocUploadCompleteIn,
    DocUploadIn,
    DocUploadOut,
    FundingIn,
    FundingPatch,
    GroundworkDetail,
    GroundworkPatch,
    ModuleDocOut,
    ModuleDocPatch,
    ProgrammeOut,
    RiskIn,
    RiskPatch,
    SignoffIn,
    StageOut,
    StagePatch,
    StakeholderIn,
    StakeholderPatch,
    TaskIn,
    TaskOut,
    TaskPatch,
)
from app.routers.groundwork import require_projects
from app.sqlutil import patch_sets
from app.storage import ALLOWED_MIMES, MAX_UPLOAD_BYTES, storage
from app.tenant import TenantContext, get_conn

router = APIRouter(tags=["groundwork"])

STAGE_ORDER = ["group", "site", "plan", "build", "live"]
DOC_UPLOAD_MIMES = {k: v for k, v in ALLOWED_MIMES.items() if v in ("pdf", "docx", "xlsx")}


async def _module_project(conn: asyncpg.Connection, project_id: UUID) -> asyncpg.Record:
    row = await conn.fetchrow(
        """
        select g.*, p.name from proj_projects g
        join projects p on p.id = g.id where g.id = $1
        """,
        project_id,
    )
    if row is None:
        raise ApiError(404, "not_found", "Project not found")
    return row


def _stage_out(row: asyncpg.Record) -> dict:
    out = dict(row)
    out["gate"] = json.loads(out["gate"])
    return out


def _doc_out(row: asyncpg.Record) -> dict:
    out = dict(row)
    out["versions"] = json.loads(out["versions"])
    return out


# -- detail ------------------------------------------------------------------


@router.get("/projects/funding-programmes", response_model=list[ProgrammeOut])
async def funding_programmes(
    nation: str | None = Query(default=None),
    kind: str | None = Query(default=None),
    stage: str | None = Query(default=None),
    status: str | None = Query(default=None),
    ctx: TenantContext = Depends(require_projects),
    conn: asyncpg.Connection = Depends(get_conn),
):
    rows = await conn.fetch("select * from proj_ref_programmes order by name")
    out = []
    for r in rows:
        if nation and nation not in r["nations"] and "uk" not in r["nations"]:
            continue
        if kind and r["kind"] != kind:
            continue
        if stage and stage not in r["stage_fit"]:
            continue
        if status and r["status"] != status:
            continue
        out.append({**dict(r), "stale": r["next_review"] < date.today()})
    return out


@router.get("/projects/{project_id}/groundwork", response_model=GroundworkDetail)
async def project_detail(
    project_id: UUID,
    ctx: TenantContext = Depends(require_projects),
    conn: asyncpg.Connection = Depends(get_conn),
):
    row = await _module_project(conn, project_id)
    out = dict(row)
    out["applicability"] = json.loads(out["applicability"])
    out["contract_facts"] = json.loads(out["contract_facts"])
    return out


@router.patch("/projects/{project_id}/groundwork", response_model=GroundworkDetail)
async def patch_project(
    project_id: UUID,
    body: GroundworkPatch,
    ctx: TenantContext = Depends(require_projects),
    conn: asyncpg.Connection = Depends(get_conn),
):
    await _module_project(conn, project_id)
    updates = body.model_dump(exclude_unset=True)
    if not updates:
        raise ApiError(400, "no_changes", "Nothing to update")
    for key in ("applicability", "contract_facts"):
        if key in updates:
            updates[key] = json.dumps(updates[key])
    sets, values = patch_sets("proj_projects", updates)
    await conn.execute(
        f"update proj_projects set {sets}, updated_at = now() where id = $1",
        project_id,
        *values,
    )
    await write_audit(
        conn, ctx.tenant_id, ctx.user_id, "projects.update", "project", str(project_id)
    )
    return await project_detail(project_id, ctx, conn)


# -- stages & gates ----------------------------------------------------------


@router.get("/projects/{project_id}/stages", response_model=list[StageOut])
async def list_stages(
    project_id: UUID,
    ctx: TenantContext = Depends(require_projects),
    conn: asyncpg.Connection = Depends(get_conn),
):
    await _module_project(conn, project_id)
    rows = await conn.fetch(
        "select * from proj_stages where project_id = $1 order by position", project_id
    )
    return [_stage_out(r) for r in rows]


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
    return _stage_out(updated)


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
    return _stage_out(updated)


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
    return _stage_out(updated)


# -- tasks -------------------------------------------------------------------


@router.get("/projects/{project_id}/tasks", response_model=list[TaskOut])
async def list_tasks(
    project_id: UUID,
    stage_key: str | None = Query(default=None),
    status: str | None = Query(default=None),
    overdue: bool = Query(default=False),
    ctx: TenantContext = Depends(require_projects),
    conn: asyncpg.Connection = Depends(get_conn),
):
    await _module_project(conn, project_id)
    clauses: list[str] = ["project_id = $1"]
    args: list = [project_id]
    if stage_key:
        args.append(stage_key)
        clauses.append(f"stage_key = ${len(args)}")
    if status:
        args.append(status)
        clauses.append(f"status = ${len(args)}")
    if overdue:
        clauses.append("due_date < current_date and status in ('todo','doing')")
    rows = await conn.fetch(
        f"select * from proj_tasks where {' and '.join(clauses)} order by position, due_date",
        *args,
    )
    return [dict(r) for r in rows]


@router.post("/projects/{project_id}/tasks", status_code=201, response_model=TaskOut)
async def create_task(
    project_id: UUID,
    body: TaskIn,
    ctx: TenantContext = Depends(require_projects),
    conn: asyncpg.Connection = Depends(get_conn),
):
    await _module_project(conn, project_id)
    position = await conn.fetchval(
        "select coalesce(max(position), 0) + 1 from proj_tasks where project_id = $1", project_id
    )
    row = await conn.fetchrow(
        """
        insert into proj_tasks (tenant_id, project_id, stage_key, title, details, owner_name,
                                due_date, is_milestone, tags, source, position)
        values ($1, $2, $3, $4, $5, $6, $7, $8, $9, 'manual', $10) returning *
        """,
        ctx.tenant_id,
        project_id,
        body.stage_key,
        body.title,
        body.details,
        body.owner_name,
        body.due_date,
        body.is_milestone,
        body.tags,
        position,
    )
    await write_audit(
        conn, ctx.tenant_id, ctx.user_id, "projects.task_create", "task", str(row["id"])
    )
    return dict(row)


@router.patch("/projects/{project_id}/tasks/{task_id}", response_model=TaskOut)
async def patch_task(
    project_id: UUID,
    task_id: UUID,
    body: TaskPatch,
    ctx: TenantContext = Depends(require_projects),
    conn: asyncpg.Connection = Depends(get_conn),
):
    updates = body.model_dump(exclude_unset=True)
    if not updates:
        raise ApiError(400, "no_changes", "Nothing to update")
    if updates.get("status") == "done":
        updates["completed_at"] = datetime.now(UTC)
    elif "status" in updates:
        updates["completed_at"] = None
    sets, values = patch_sets("proj_tasks", updates, id_param=2)
    row = await conn.fetchrow(
        f"update proj_tasks set {sets} where project_id = $1 and id = $2 returning *",
        project_id,
        task_id,
        *values,
    )
    if row is None:
        raise ApiError(404, "not_found", "Task not found")
    await write_audit(
        conn, ctx.tenant_id, ctx.user_id, "projects.task_update", "task", str(task_id)
    )
    return dict(row)


@router.delete("/projects/{project_id}/tasks/{task_id}", status_code=204)
async def delete_task(
    project_id: UUID,
    task_id: UUID,
    ctx: TenantContext = Depends(require_projects),
    conn: asyncpg.Connection = Depends(get_conn),
):
    deleted = await conn.execute(
        "delete from proj_tasks where project_id = $1 and id = $2", project_id, task_id
    )
    if deleted == "DELETE 0":
        raise ApiError(404, "not_found", "Task not found")
    await write_audit(
        conn, ctx.tenant_id, ctx.user_id, "projects.task_delete", "task", str(task_id)
    )


@router.post("/projects/{project_id}/tasks/bulk-complete")
async def bulk_complete_tasks(
    project_id: UUID,
    body: BulkCompleteIn,
    ctx: TenantContext = Depends(require_projects),
    conn: asyncpg.Connection = Depends(get_conn),
):
    updated = await conn.execute(
        """
        update proj_tasks set status = 'done', completed_at = now()
        where project_id = $1 and id = any($2) and status <> 'done'
        """,
        project_id,
        body.ids,
    )
    await write_audit(
        conn, ctx.tenant_id, ctx.user_id, "projects.task_bulk_complete", "project", str(project_id)
    )
    return {"completed": int(updated.split()[-1])}


# -- document registry -------------------------------------------------------


@router.get("/projects/{project_id}/documents", response_model=list[ModuleDocOut])
async def list_registry(
    project_id: UUID,
    ctx: TenantContext = Depends(require_projects),
    conn: asyncpg.Connection = Depends(get_conn),
):
    await _module_project(conn, project_id)
    rows = await conn.fetch(
        "select * from proj_documents where project_id = $1 order by stage_key, doc_type_key",
        project_id,
    )
    return [_doc_out(r) for r in rows]


@router.patch("/projects/{project_id}/documents/{doc_id}", response_model=ModuleDocOut)
async def patch_registry_doc(
    project_id: UUID,
    doc_id: UUID,
    body: ModuleDocPatch,
    ctx: TenantContext = Depends(require_projects),
    conn: asyncpg.Connection = Depends(get_conn),
):
    updates = body.model_dump(exclude_unset=True)
    if not updates:
        raise ApiError(400, "no_changes", "Nothing to update")
    if updates.get("vault_document_id") is not None:
        # Only unassigned vault documents or ones already in this project can
        # back a registry entry — no cross-project links.
        ok = await conn.fetchval(
            "select 1 from documents where id = $1 and (project_id is null or project_id = $2)",
            updates["vault_document_id"],
            project_id,
        )
        if not ok:
            raise ApiError(404, "not_found", "Vault document not found in this project")
    sets, values = patch_sets("proj_documents", updates, id_param=2)
    row = await conn.fetchrow(
        f"""update proj_documents set {sets}, updated_at = now()
            where project_id = $1 and id = $2 returning *""",
        project_id,
        doc_id,
        *values,
    )
    if row is None:
        raise ApiError(404, "not_found", "Registry document not found")
    if "status" in updates:
        await recompute_doc_gates(conn, project_id, row["doc_type_key"], row["status"])
    await write_audit(
        conn, ctx.tenant_id, ctx.user_id, "projects.document_update", "proj_document", str(doc_id)
    )
    return _doc_out(row)


@router.post("/projects/{project_id}/documents/{doc_id}/upload", response_model=DocUploadOut)
async def upload_registry_version(
    project_id: UUID,
    doc_id: UUID,
    body: DocUploadIn,
    ctx: TenantContext = Depends(require_projects),
    conn: asyncpg.Connection = Depends(get_conn),
):
    doc = await conn.fetchrow(
        "select * from proj_documents where project_id = $1 and id = $2", project_id, doc_id
    )
    if doc is None:
        raise ApiError(404, "not_found", "Registry document not found")
    if body.mime not in DOC_UPLOAD_MIMES:
        raise ApiError(400, "unsupported_type", "Supported types: pdf, docx, xlsx")
    if body.size_bytes > MAX_UPLOAD_BYTES:
        raise ApiError(400, "too_large", "Files are limited to 50 MB")
    version = len(json.loads(doc["versions"])) + 1
    key = (
        f"{ctx.tenant_id}/projects/{project_id}/docs/{doc_id}/"
        f"v{version}-{body.filename.replace('/', '_')}"
    )
    return {"upload_url": storage.presign_put(key, body.mime), "file_key": key}


@router.post(
    "/projects/{project_id}/documents/{doc_id}/upload/complete", response_model=ModuleDocOut
)
async def complete_registry_upload(
    project_id: UUID,
    doc_id: UUID,
    body: DocUploadCompleteIn,
    ctx: TenantContext = Depends(require_projects),
):
    from app.db import db

    size = await storage.object_size(body.file_key)
    if size is None:
        raise ApiError(400, "not_uploaded", "No file has been uploaded for this version")
    async with db.tenant_tx(ctx.user_id, ctx.tenant_id) as conn:
        doc = await conn.fetchrow(
            "select * from proj_documents where project_id = $1 and id = $2", project_id, doc_id
        )
        if doc is None:
            raise ApiError(404, "not_found", "Registry document not found")
        if not body.file_key.startswith(f"{ctx.tenant_id}/projects/{project_id}/docs/{doc_id}/"):
            raise ApiError(400, "bad_key", "Upload key does not belong to this document")
        versions = json.loads(doc["versions"])
        versions.append(
            {
                "version": len(versions) + 1,
                "file_key": body.file_key,
                "created_at": datetime.now(UTC).isoformat(),
                "created_by": str(ctx.user_id),
                "note": body.note,
            }
        )
        row = await conn.fetchrow(
            """
            update proj_documents set versions = $3, current_file_key = $4, updated_at = now()
            where project_id = $1 and id = $2 returning *
            """,
            project_id,
            doc_id,
            json.dumps(versions),
            body.file_key,
        )
        await write_audit(
            conn,
            ctx.tenant_id,
            ctx.user_id,
            "projects.document_upload",
            "proj_document",
            str(doc_id),
        )
    return _doc_out(row)


@router.get("/projects/{project_id}/documents/{doc_id}/download")
async def download_registry_doc(
    project_id: UUID,
    doc_id: UUID,
    ctx: TenantContext = Depends(require_projects),
    conn: asyncpg.Connection = Depends(get_conn),
):
    doc = await conn.fetchrow(
        "select current_file_key from proj_documents where project_id = $1 and id = $2",
        project_id,
        doc_id,
    )
    if doc is None or not doc["current_file_key"]:
        raise ApiError(404, "not_found", "No file uploaded for this document")
    return {"download_url": storage.presign_get(doc["current_file_key"])}


# -- budget ------------------------------------------------------------------


@router.get("/projects/{project_id}/budget", response_model=BudgetOut)
async def get_budget(
    project_id: UUID,
    ctx: TenantContext = Depends(require_projects),
    conn: asyncpg.Connection = Depends(get_conn),
):
    await _module_project(conn, project_id)
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
    await _module_project(conn, project_id)
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


# -- funding -----------------------------------------------------------------


@router.get("/projects/{project_id}/funding")
async def list_funding(
    project_id: UUID,
    ctx: TenantContext = Depends(require_projects),
    conn: asyncpg.Connection = Depends(get_conn),
):
    await _module_project(conn, project_id)
    rows = await conn.fetch(
        "select * from proj_funding_sources where project_id = $1 order by name", project_id
    )
    return [
        {
            **dict(r),
            "drawdown_schedule": json.loads(r["drawdown_schedule"]),
            "amount_sought": float(r["amount_sought"]) if r["amount_sought"] is not None else None,
            "amount_secured": float(r["amount_secured"])
            if r["amount_secured"] is not None
            else None,
        }
        for r in rows
    ]


@router.post("/projects/{project_id}/funding", status_code=201)
async def create_funding(
    project_id: UUID,
    body: FundingIn,
    ctx: TenantContext = Depends(require_projects),
    conn: asyncpg.Connection = Depends(get_conn),
):
    await _module_project(conn, project_id)
    row = await conn.fetchrow(
        """
        insert into proj_funding_sources (tenant_id, project_id, programme_key, name, funder,
            kind, amount_sought, amount_secured, status, conditions, drawdown_schedule, notes)
        values ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12) returning id
        """,
        ctx.tenant_id,
        project_id,
        body.programme_key,
        body.name,
        body.funder,
        body.kind,
        body.amount_sought,
        body.amount_secured,
        body.status,
        body.conditions,
        json.dumps(body.drawdown_schedule),
        body.notes,
    )
    await write_audit(
        conn, ctx.tenant_id, ctx.user_id, "projects.funding_create", "funding", str(row["id"])
    )
    return {"id": str(row["id"])}


@router.patch("/projects/{project_id}/funding/{funding_id}")
async def patch_funding(
    project_id: UUID,
    funding_id: UUID,
    body: FundingPatch,
    ctx: TenantContext = Depends(require_projects),
    conn: asyncpg.Connection = Depends(get_conn),
):
    updates = body.model_dump(exclude_unset=True)
    if not updates:
        raise ApiError(400, "no_changes", "Nothing to update")
    if "drawdown_schedule" in updates:
        updates["drawdown_schedule"] = json.dumps(updates["drawdown_schedule"])
    sets, values = patch_sets("proj_funding_sources", updates, id_param=2)
    row = await conn.fetchrow(
        f"""update proj_funding_sources set {sets}, updated_at = now()
            where project_id = $1 and id = $2 returning id""",
        project_id,
        funding_id,
        *values,
    )
    if row is None:
        raise ApiError(404, "not_found", "Funding source not found")
    await write_audit(
        conn, ctx.tenant_id, ctx.user_id, "projects.funding_update", "funding", str(funding_id)
    )
    return {"id": str(funding_id)}


@router.delete("/projects/{project_id}/funding/{funding_id}", status_code=204)
async def delete_funding(
    project_id: UUID,
    funding_id: UUID,
    ctx: TenantContext = Depends(require_projects),
    conn: asyncpg.Connection = Depends(get_conn),
):
    deleted = await conn.execute(
        "delete from proj_funding_sources where project_id = $1 and id = $2",
        project_id,
        funding_id,
    )
    if deleted == "DELETE 0":
        raise ApiError(404, "not_found", "Funding source not found")
    await write_audit(
        conn, ctx.tenant_id, ctx.user_id, "projects.funding_delete", "funding", str(funding_id)
    )


# -- risks / conditions / stakeholders ---------------------------------------


@router.get("/projects/{project_id}/risks")
async def list_risks(
    project_id: UUID,
    ctx: TenantContext = Depends(require_projects),
    conn: asyncpg.Connection = Depends(get_conn),
):
    await _module_project(conn, project_id)
    rows = await conn.fetch(
        """select * from proj_risks where project_id = $1
           order by status = 'closed', likelihood * impact desc""",
        project_id,
    )
    return [dict(r) for r in rows]


@router.post("/projects/{project_id}/risks", status_code=201)
async def create_risk(
    project_id: UUID,
    body: RiskIn,
    ctx: TenantContext = Depends(require_projects),
    conn: asyncpg.Connection = Depends(get_conn),
):
    await _module_project(conn, project_id)
    row = await conn.fetchrow(
        """
        insert into proj_risks (tenant_id, project_id, category, description, likelihood,
                                impact, owner_name, mitigation, review_date, source)
        values ($1, $2, $3, $4, $5, $6, $7, $8, $9, 'manual') returning id
        """,
        ctx.tenant_id,
        project_id,
        body.category,
        body.description,
        body.likelihood,
        body.impact,
        body.owner_name,
        body.mitigation,
        body.review_date,
    )
    await write_audit(
        conn, ctx.tenant_id, ctx.user_id, "projects.risk_create", "risk", str(row["id"])
    )
    return {"id": str(row["id"])}


@router.patch("/projects/{project_id}/risks/{risk_id}")
async def patch_risk(
    project_id: UUID,
    risk_id: UUID,
    body: RiskPatch,
    ctx: TenantContext = Depends(require_projects),
    conn: asyncpg.Connection = Depends(get_conn),
):
    updates = body.model_dump(exclude_unset=True)
    if not updates:
        raise ApiError(400, "no_changes", "Nothing to update")
    sets, values = patch_sets("proj_risks", updates, id_param=2)
    row = await conn.fetchrow(
        f"""update proj_risks set {sets}, updated_at = now()
            where project_id = $1 and id = $2 returning id""",
        project_id,
        risk_id,
        *values,
    )
    if row is None:
        raise ApiError(404, "not_found", "Risk not found")
    await write_audit(
        conn, ctx.tenant_id, ctx.user_id, "projects.risk_update", "risk", str(risk_id)
    )
    return {"id": str(risk_id)}


@router.get("/projects/{project_id}/conditions")
async def list_conditions(
    project_id: UUID,
    ctx: TenantContext = Depends(require_projects),
    conn: asyncpg.Connection = Depends(get_conn),
):
    await _module_project(conn, project_id)
    rows = await conn.fetch(
        """select * from proj_conditions where project_id = $1
           order by pre_commencement desc, number""",
        project_id,
    )
    return [dict(r) for r in rows]


@router.post("/projects/{project_id}/conditions", status_code=201)
async def create_condition(
    project_id: UUID,
    body: ConditionIn,
    ctx: TenantContext = Depends(require_projects),
    conn: asyncpg.Connection = Depends(get_conn),
):
    await _module_project(conn, project_id)
    row = await conn.fetchrow(
        """
        insert into proj_conditions (tenant_id, project_id, application_ref, number,
                                     description, pre_commencement)
        values ($1, $2, $3, $4, $5, $6) returning id
        """,
        ctx.tenant_id,
        project_id,
        body.application_ref,
        body.number,
        body.description,
        body.pre_commencement,
    )
    await write_audit(
        conn, ctx.tenant_id, ctx.user_id, "projects.condition_create", "condition", str(row["id"])
    )
    return {"id": str(row["id"])}


@router.patch("/projects/{project_id}/conditions/{condition_id}")
async def patch_condition(
    project_id: UUID,
    condition_id: UUID,
    body: ConditionPatch,
    ctx: TenantContext = Depends(require_projects),
    conn: asyncpg.Connection = Depends(get_conn),
):
    updates = body.model_dump(exclude_unset=True)
    if not updates:
        raise ApiError(400, "no_changes", "Nothing to update")
    sets, values = patch_sets("proj_conditions", updates, id_param=2)
    row = await conn.fetchrow(
        f"update proj_conditions set {sets} where project_id = $1 and id = $2 returning id",
        project_id,
        condition_id,
        *values,
    )
    if row is None:
        raise ApiError(404, "not_found", "Condition not found")
    await write_audit(
        conn,
        ctx.tenant_id,
        ctx.user_id,
        "projects.condition_update",
        "condition",
        str(condition_id),
    )
    return {"id": str(condition_id)}


@router.delete("/projects/{project_id}/conditions/{condition_id}", status_code=204)
async def delete_condition(
    project_id: UUID,
    condition_id: UUID,
    ctx: TenantContext = Depends(require_projects),
    conn: asyncpg.Connection = Depends(get_conn),
):
    deleted = await conn.execute(
        "delete from proj_conditions where project_id = $1 and id = $2",
        project_id,
        condition_id,
    )
    if deleted == "DELETE 0":
        raise ApiError(404, "not_found", "Condition not found")
    await write_audit(
        conn,
        ctx.tenant_id,
        ctx.user_id,
        "projects.condition_delete",
        "condition",
        str(condition_id),
    )


@router.get("/projects/{project_id}/stakeholders")
async def list_stakeholders(
    project_id: UUID,
    ctx: TenantContext = Depends(require_projects),
    conn: asyncpg.Connection = Depends(get_conn),
):
    await _module_project(conn, project_id)
    rows = await conn.fetch(
        "select * from proj_stakeholders where project_id = $1 order by role, name", project_id
    )
    return [dict(r) for r in rows]


@router.post("/projects/{project_id}/stakeholders", status_code=201)
async def create_stakeholder(
    project_id: UUID,
    body: StakeholderIn,
    ctx: TenantContext = Depends(require_projects),
    conn: asyncpg.Connection = Depends(get_conn),
):
    await _module_project(conn, project_id)
    row = await conn.fetchrow(
        """
        insert into proj_stakeholders (tenant_id, project_id, name, org, role, email,
                                       phone, notes, last_contact)
        values ($1, $2, $3, $4, $5, $6, $7, $8, $9) returning id
        """,
        ctx.tenant_id,
        project_id,
        body.name,
        body.org,
        body.role,
        body.email,
        body.phone,
        body.notes,
        body.last_contact,
    )
    await write_audit(
        conn,
        ctx.tenant_id,
        ctx.user_id,
        "projects.stakeholder_create",
        "stakeholder",
        str(row["id"]),
    )
    return {"id": str(row["id"])}


@router.patch("/projects/{project_id}/stakeholders/{stakeholder_id}")
async def patch_stakeholder(
    project_id: UUID,
    stakeholder_id: UUID,
    body: StakeholderPatch,
    ctx: TenantContext = Depends(require_projects),
    conn: asyncpg.Connection = Depends(get_conn),
):
    updates = body.model_dump(exclude_unset=True)
    if not updates:
        raise ApiError(400, "no_changes", "Nothing to update")
    sets, values = patch_sets("proj_stakeholders", updates, id_param=2)
    row = await conn.fetchrow(
        f"update proj_stakeholders set {sets} where project_id = $1 and id = $2 returning id",
        project_id,
        stakeholder_id,
        *values,
    )
    if row is None:
        raise ApiError(404, "not_found", "Stakeholder not found")
    await write_audit(
        conn,
        ctx.tenant_id,
        ctx.user_id,
        "projects.stakeholder_update",
        "stakeholder",
        str(stakeholder_id),
    )
    return {"id": str(stakeholder_id)}


@router.delete("/projects/{project_id}/stakeholders/{stakeholder_id}", status_code=204)
async def delete_stakeholder(
    project_id: UUID,
    stakeholder_id: UUID,
    ctx: TenantContext = Depends(require_projects),
    conn: asyncpg.Connection = Depends(get_conn),
):
    deleted = await conn.execute(
        "delete from proj_stakeholders where project_id = $1 and id = $2",
        project_id,
        stakeholder_id,
    )
    if deleted == "DELETE 0":
        raise ApiError(404, "not_found", "Stakeholder not found")
    await write_audit(
        conn,
        ctx.tenant_id,
        ctx.user_id,
        "projects.stakeholder_delete",
        "stakeholder",
        str(stakeholder_id),
    )


# -- activity ----------------------------------------------------------------


@router.get("/projects/{project_id}/activity", response_model=list[ActivityOut])
async def project_activity(
    project_id: UUID,
    ctx: TenantContext = Depends(require_projects),
    conn: asyncpg.Connection = Depends(get_conn),
):
    await _module_project(conn, project_id)
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
