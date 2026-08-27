"""The whole workspace as one downloadable archive — queued, worker-built.

The first self-serve backup/offboarding path: vault documents, generated
artefacts and every register, zipped by the worker and downloaded through a
short-lived presigned URL. Same lifecycle as the answer-PDF export; the API
owns the job row and nothing else. Both reads run under RLS, so cross-tenant
job ids 404 by policy.

Admin-and-up: the archive holds every member's shared work, so requesting it
is a workspace act, not a member one. Other members' private chats are
excluded by the worker — the exporter's role does not widen what the app
itself would show them.
"""

import re
from datetime import date
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends

from app.audit import write_audit
from app.errors import ApiError
from app.queue import ingest_queue
from app.schemas import WorkspaceExportJobOut
from app.storage import storage
from app.tenant import TenantContext, get_conn, require_role

router = APIRouter(tags=["tenants"])


def _job_out(row: asyncpg.Record, download_url: str | None = None) -> dict:
    return {**dict(row), "download_url": download_url}


def archive_filename(tenant_name: str, created: date) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", tenant_name.lower()).strip("-") or "workspace"
    return f"flowgrid-export-{slug}-{created.isoformat()}.zip"


@router.post("/tenants/me/export", status_code=202, response_model=WorkspaceExportJobOut)
async def export_workspace(
    ctx: TenantContext = Depends(require_role("admin")),
    conn: asyncpg.Connection = Depends(get_conn),
):
    if not storage.enabled:
        raise ApiError(503, "storage_unavailable", "File storage is not configured")
    # An archive can take minutes; a second click mid-build reuses the job
    # rather than racing a duplicate over the same ground.
    existing = await conn.fetchrow(
        """
        select * from workspace_export_jobs
        where status in ('queued', 'running')
          and created_at > now() - interval '10 minutes'
        """
    )
    if existing:
        return _job_out(existing)
    row = await conn.fetchrow(
        """
        insert into workspace_export_jobs (tenant_id, created_by)
        values ($1, $2) returning *
        """,
        ctx.tenant_id,
        ctx.user_id,
    )
    await write_audit(
        conn,
        ctx.tenant_id,
        ctx.user_id,
        "tenant.export_submit",
        "workspace_export_job",
        str(row["id"]),
    )
    # Enqueue inside the transaction: if Redis is down the job row rolls back
    # and the client sees the 503 rather than a stuck "queued" job.
    await ingest_queue.enqueue_workspace_export(ctx.tenant_id, row["id"], ctx.user_id)
    return _job_out(row)


@router.get("/tenants/me/exports/{job_id}", response_model=WorkspaceExportJobOut)
async def get_export_job(
    job_id: UUID,
    ctx: TenantContext = Depends(require_role("admin")),
    conn: asyncpg.Connection = Depends(get_conn),
):
    row = await conn.fetchrow("select * from workspace_export_jobs where id = $1", job_id)
    if row is None:  # RLS scoped — cross-tenant ids are invisible
        raise ApiError(404, "not_found", "Export job not found")
    download_url = None
    if row["status"] == "succeeded" and row["file_key"]:
        name = await conn.fetchval("select name from tenants where id = $1", ctx.tenant_id)
        download_url = storage.presign_get(
            row["file_key"],
            filename=archive_filename(name or "workspace", row["created_at"].date()),
        )
    return _job_out(row, download_url)
