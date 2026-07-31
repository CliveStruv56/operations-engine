"""Groundwork W3 (PRD §5): submit and poll AI draft jobs.

POST /projects/{project_id}/drafts — validate kind-specific params, insert
the job row and enqueue in the same tenant transaction (a failed enqueue
rolls the row back, mirroring the vault upload flow).
GET /projects/drafts/{job_id} — poll the job row; once succeeded, include a
presigned download URL. Both read under RLS, so cross-tenant job ids 404 by
policy, not app code.
"""

import json
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends

from app.audit import write_audit
from app.errors import ApiError
from app.groundwork.schemas import DraftIn, DraftJobOut
from app.queue import ingest_queue
from app.routers.groundwork import require_projects
from app.routers.groundwork_room.common import module_project
from app.storage import storage
from app.tenant import TenantContext, get_conn

router = APIRouter(tags=["groundwork"])

# A queued/running job older than this is treated as stranded (worker killed
# mid-job) rather than in flight — 2h clears the worker's 3600s job_timeout,
# so the duplicate guard self-heals instead of blocking drafts forever.
IN_FLIGHT_WINDOW = "2 hours"


def _job_out(row: asyncpg.Record, download_url: str | None = None) -> dict:
    return {**dict(row), "cost_usd": float(row["cost_usd"]), "download_url": download_url}


async def _draft_params(conn: asyncpg.Connection, project_id: UUID, body: DraftIn) -> dict:
    if body.kind == "monthly_report":
        if not body.month:
            raise ApiError(422, "month_required", "Pick the month the report covers")
        return {"month": body.month}
    if body.kind == "funding_bid":
        if not body.funding_source_id:
            raise ApiError(422, "funding_source_required", "Pick the funding source to bid for")
        exists = await conn.fetchval(
            "select 1 from proj_funding_sources where id = $1 and project_id = $2",
            body.funding_source_id,
            project_id,
        )
        if not exists:
            raise ApiError(404, "not_found", "Funding source not found")
        return {"funding_source_id": str(body.funding_source_id)}
    return {"instructions": body.instructions} if body.instructions else {}


@router.post("/projects/{project_id}/drafts", status_code=202, response_model=DraftJobOut)
async def submit_draft(
    project_id: UUID,
    body: DraftIn,
    ctx: TenantContext = Depends(require_projects),
    conn: asyncpg.Connection = Depends(get_conn),
):
    await module_project(conn, project_id)
    # One in-flight draft per document kind: a second click mid-draft doubles
    # the LLM spend for an identical result (the register would just version it).
    in_flight = await conn.fetchval(
        f"""
        select 1 from proj_draft_jobs
        where project_id = $1 and kind = $2 and status in ('queued', 'running')
          and created_at > now() - interval '{IN_FLIGHT_WINDOW}'
        """,
        project_id,
        body.kind,
    )
    if in_flight:
        raise ApiError(
            409,
            "draft_in_flight",
            "This draft is already being generated — it lands in the document "
            "registry when done.",
        )
    params = await _draft_params(conn, project_id, body)
    row = await conn.fetchrow(
        """
        insert into proj_draft_jobs (tenant_id, project_id, kind, params, created_by)
        values ($1, $2, $3, $4, $5)
        returning *
        """,
        ctx.tenant_id,
        project_id,
        body.kind,
        json.dumps(params),
        ctx.user_id,
    )
    await write_audit(
        conn,
        ctx.tenant_id,
        ctx.user_id,
        "projects.draft_submit",
        "proj_draft_job",
        str(row["id"]),
        {"kind": body.kind},
    )
    # Enqueue inside the transaction: if Redis is down the job row rolls back
    # and the client sees the 503 rather than a stuck "queued" job.
    await ingest_queue.enqueue_draft(ctx.tenant_id, project_id, row["id"], ctx.user_id)
    return _job_out(row)


@router.post("/projects/{project_id}/health-card", status_code=202, response_model=DraftJobOut)
async def submit_health_card(
    project_id: UUID,
    ctx: TenantContext = Depends(require_projects),
    conn: asyncpg.Connection = Depends(get_conn),
):
    await module_project(conn, project_id)
    row = await conn.fetchrow(
        """
        insert into proj_draft_jobs (tenant_id, project_id, kind, created_by)
        values ($1, $2, 'health_card', $3)
        returning *
        """,
        ctx.tenant_id,
        project_id,
        ctx.user_id,
    )
    await write_audit(
        conn,
        ctx.tenant_id,
        ctx.user_id,
        "projects.health_card_submit",
        "proj_draft_job",
        str(row["id"]),
    )
    await ingest_queue.enqueue_health_card(ctx.tenant_id, project_id, row["id"], ctx.user_id)
    return _job_out(row)


@router.get("/projects/{project_id}/drafts", response_model=list[DraftJobOut])
async def list_active_draft_jobs(
    project_id: UUID,
    ctx: TenantContext = Depends(require_projects),
    conn: asyncpg.Connection = Depends(get_conn),
):
    """Queued/running jobs for the project — lets a reopened launcher resume
    polling an in-flight draft instead of offering a duplicate submit."""
    await module_project(conn, project_id)
    rows = await conn.fetch(
        f"""
        select * from proj_draft_jobs
        where project_id = $1 and status in ('queued', 'running')
          and created_at > now() - interval '{IN_FLIGHT_WINDOW}'
        order by created_at desc
        """,
        project_id,
    )
    return [_job_out(row) for row in rows]


@router.get("/projects/drafts/{job_id}", response_model=DraftJobOut)
async def get_draft_job(
    job_id: UUID,
    ctx: TenantContext = Depends(require_projects),
    conn: asyncpg.Connection = Depends(get_conn),
):
    row = await conn.fetchrow("select * from proj_draft_jobs where id = $1", job_id)
    if row is None:  # RLS scoped — cross-tenant ids are invisible
        raise ApiError(404, "not_found", "Draft job not found")
    download_url = None
    if row["status"] == "succeeded" and row["file_key"]:
        download_url = storage.presign_get(row["file_key"])
    return _job_out(row, download_url)
