"""Submit and poll Grantwork draft jobs, plus the impact-card export.

Same shape as Groundwork's: validate kind-specific params, insert the job row
and enqueue inside one tenant transaction (a failed enqueue rolls the row
back, so a Redis outage surfaces as a 503 rather than a job stuck at
'queued'). Polling reads under RLS, so a cross-tenant job id 404s by policy
rather than by app code.
"""

import json
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends

from app.audit import write_audit
from app.errors import ApiError
from app.grants.schemas import DraftIn, DraftJobOut
from app.queue import ingest_queue
from app.routers.grants.common import module_application, require_grants
from app.storage import storage
from app.tenant import TenantContext, get_conn

router = APIRouter()

# A queued/running job older than this is stranded (worker killed mid-job)
# rather than in flight — 2h clears the worker's 3600s job_timeout, so the
# duplicate guard self-heals instead of blocking drafts forever.
IN_FLIGHT_WINDOW = "2 hours"


def _job_out(row: asyncpg.Record, download_url: str | None = None) -> dict:
    return {**dict(row), "cost_usd": float(row["cost_usd"]), "download_url": download_url}


async def _draft_params(conn: asyncpg.Connection, application_id: UUID, body: DraftIn) -> dict:
    if body.kind == "monitoring_report":
        if not body.reporting_period_id:
            raise ApiError(422, "period_required", "Pick the reporting period this return covers")
        exists = await conn.fetchval(
            "select 1 from grant_reporting_periods where id = $1 and application_id = $2",
            body.reporting_period_id,
            application_id,
        )
        if not exists:
            raise ApiError(404, "not_found", "Reporting period not found")
        return {"reporting_period_id": str(body.reporting_period_id)}
    return {"instructions": body.instructions} if body.instructions else {}


@router.post(
    "/grants/applications/{application_id}/drafts", status_code=202, response_model=DraftJobOut
)
async def submit_draft(
    application_id: UUID,
    body: DraftIn,
    ctx: TenantContext = Depends(require_grants),
    conn: asyncpg.Connection = Depends(get_conn),
):
    await module_application(conn, application_id)
    # One in-flight draft per kind: a second click mid-draft doubles the model
    # spend for an identical result, since the register would only version it.
    in_flight = await conn.fetchval(
        f"""
        select 1 from grant_draft_jobs
        where application_id = $1 and kind = $2 and status in ('queued', 'running')
          and created_at > now() - interval '{IN_FLIGHT_WINDOW}'
        """,
        application_id,
        body.kind,
    )
    if in_flight:
        raise ApiError(
            409,
            "draft_in_flight",
            "This draft is already being generated — it lands in the bid pack when done.",
        )
    params = await _draft_params(conn, application_id, body)
    row = await conn.fetchrow(
        """
        insert into grant_draft_jobs (tenant_id, application_id, kind, params, created_by)
        values ($1, $2, $3, $4, $5)
        returning *
        """,
        ctx.tenant_id,
        application_id,
        body.kind,
        json.dumps(params),
        ctx.user_id,
    )
    await write_audit(
        conn,
        ctx.tenant_id,
        ctx.user_id,
        "grants.draft_submit",
        "grant_draft_job",
        str(row["id"]),
        {"kind": body.kind},
    )
    # Enqueue inside the transaction: if Redis is down the row rolls back and
    # the client sees the 503 rather than a job stuck at 'queued'.
    await ingest_queue.enqueue_grant_draft(ctx.tenant_id, application_id, row["id"], ctx.user_id)
    return _job_out(row)


@router.post(
    "/grants/applications/{application_id}/impact-card",
    status_code=202,
    response_model=DraftJobOut,
)
async def submit_impact_card(
    application_id: UUID,
    ctx: TenantContext = Depends(require_grants),
    conn: asyncpg.Connection = Depends(get_conn),
):
    """The funder-facing one-pager. No LLM anywhere in it, so every figure is
    a recorded row — which is why it is safe to send outward when a draft is
    not."""
    await module_application(conn, application_id)
    row = await conn.fetchrow(
        """
        insert into grant_draft_jobs (tenant_id, application_id, kind, created_by)
        values ($1, $2, 'impact_card', $3)
        returning *
        """,
        ctx.tenant_id,
        application_id,
        ctx.user_id,
    )
    await write_audit(
        conn,
        ctx.tenant_id,
        ctx.user_id,
        "grants.impact_card_submit",
        "grant_draft_job",
        str(row["id"]),
    )
    await ingest_queue.enqueue_impact_card(ctx.tenant_id, application_id, row["id"], ctx.user_id)
    return _job_out(row)


@router.get("/grants/applications/{application_id}/drafts", response_model=list[DraftJobOut])
async def list_active_draft_jobs(
    application_id: UUID,
    ctx: TenantContext = Depends(require_grants),
    conn: asyncpg.Connection = Depends(get_conn),
):
    """Queued/running jobs, so a reopened launcher resumes polling an
    in-flight draft instead of offering a duplicate submit."""
    await module_application(conn, application_id)
    rows = await conn.fetch(
        f"""
        select * from grant_draft_jobs
        where application_id = $1 and status in ('queued', 'running')
          and created_at > now() - interval '{IN_FLIGHT_WINDOW}'
        order by created_at desc
        """,
        application_id,
    )
    return [_job_out(row) for row in rows]


@router.get("/grants/drafts/{job_id}", response_model=DraftJobOut)
async def get_draft_job(
    job_id: UUID,
    ctx: TenantContext = Depends(require_grants),
    conn: asyncpg.Connection = Depends(get_conn),
):
    row = await conn.fetchrow("select * from grant_draft_jobs where id = $1", job_id)
    if row is None:  # RLS scoped — cross-tenant ids are invisible
        raise ApiError(404, "not_found", "Draft job not found")
    download_url = None
    if row["status"] == "succeeded" and row["file_key"]:
        download_url = storage.presign_get(row["file_key"])
    return _job_out(row, download_url)
