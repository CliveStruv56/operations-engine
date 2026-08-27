"""The community profile as a one-page branded PDF — queued, worker-rendered.

Same shape as the answer-PDF export: WeasyPrint's system libraries live only
in the worker image, so the API owns the job lifecycle and nothing else.
Both reads run under RLS, so cross-tenant job ids 404 by policy.
"""

from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends

from app.audit import write_audit
from app.community.schemas import ExportJobOut
from app.errors import ApiError
from app.queue import ingest_queue
from app.routers.community.common import require_community
from app.storage import storage
from app.tenant import TenantContext, get_conn

router = APIRouter()


def _job_out(row: asyncpg.Record, download_url: str | None = None) -> dict:
    return {**dict(row), "download_url": download_url}


@router.post("/community/profile/pdf", status_code=202, response_model=ExportJobOut)
async def export_profile_pdf(
    ctx: TenantContext = Depends(require_community),
    conn: asyncpg.Connection = Depends(get_conn),
):
    # A PDF of nothing helps nobody: the place must at least be named first.
    if await conn.fetchval("select 1 from community_profile") is None:
        raise ApiError(404, "no_profile", "Describe the place before exporting it")
    if not storage.enabled:
        raise ApiError(503, "storage_unavailable", "File storage is not configured")
    # A second click mid-render spends nothing extra, but reusing the
    # in-flight job keeps the button honest about what it is waiting for.
    existing = await conn.fetchrow(
        """
        select * from community_export_jobs
        where kind = 'profile_pdf' and status in ('queued', 'running')
          and created_at > now() - interval '10 minutes'
        """
    )
    if existing:
        return _job_out(existing)
    row = await conn.fetchrow(
        """
        insert into community_export_jobs (tenant_id, created_by)
        values ($1, $2) returning *
        """,
        ctx.tenant_id,
        ctx.user_id,
    )
    await write_audit(
        conn,
        ctx.tenant_id,
        ctx.user_id,
        "community.profile_pdf_submit",
        "community_export_job",
        str(row["id"]),
    )
    # Enqueue inside the transaction: if Redis is down the job row rolls back
    # and the client sees the 503 rather than a stuck "queued" job.
    await ingest_queue.enqueue_community_pdf(ctx.tenant_id, row["id"], ctx.user_id)
    return _job_out(row)


@router.get("/community/exports/{job_id}", response_model=ExportJobOut)
async def get_export_job(
    job_id: UUID,
    ctx: TenantContext = Depends(require_community),
    conn: asyncpg.Connection = Depends(get_conn),
):
    row = await conn.fetchrow("select * from community_export_jobs where id = $1", job_id)
    if row is None:  # RLS scoped — cross-tenant ids are invisible
        raise ApiError(404, "not_found", "Export job not found")
    download_url = None
    if row["status"] == "succeeded" and row["file_key"]:
        download_url = storage.presign_get(row["file_key"])
    return _job_out(row, download_url)
