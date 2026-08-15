"""Export a chat answer as a branded PDF — queued, worker-rendered.

Unlike the synchronous slides export, PDF rendering needs WeasyPrint's system
libraries, which live only in the worker image — so this follows the
health-card shape instead: insert a job row and enqueue in the same tenant
transaction, then poll. Both reads run under RLS, so cross-tenant job ids 404
by policy, not app code.
"""

from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends

from app.audit import write_audit
from app.errors import ApiError
from app.queue import ingest_queue
from app.routers.conversations import _get_owned_conversation
from app.schemas import ConversationExportJobOut
from app.storage import storage
from app.tenant import TenantContext, get_conn, require_role

router = APIRouter(tags=["conversations"])


def _job_out(row: asyncpg.Record, download_url: str | None = None) -> dict:
    return {**dict(row), "download_url": download_url}


@router.post(
    "/conversations/{conversation_id}/messages/{message_id}/pdf",
    status_code=202,
    response_model=ConversationExportJobOut,
)
async def export_answer_pdf(
    conversation_id: UUID,
    message_id: UUID,
    ctx: TenantContext = Depends(require_role("member")),
    conn: asyncpg.Connection = Depends(get_conn),
):
    # Ownership before capability: a cross-tenant id must 404 whatever else
    # is misconfigured.
    await _get_owned_conversation(conn, ctx, conversation_id)
    message = await conn.fetchrow(
        "select role from messages where id = $1 and conversation_id = $2",
        message_id,
        conversation_id,
    )
    if message is None or message["role"] != "assistant":
        raise ApiError(404, "not_found", "Message not found")
    if not storage.enabled:
        raise ApiError(503, "storage_unavailable", "File storage is not configured")
    # A second click mid-render would spend nothing extra (no LLM), but it
    # would race the same storage key — reuse the in-flight job instead.
    existing = await conn.fetchrow(
        """
        select * from conversation_export_jobs
        where message_id = $1 and kind = 'pdf' and status in ('queued', 'running')
          and created_at > now() - interval '10 minutes'
        """,
        message_id,
    )
    if existing:
        return _job_out(existing)
    row = await conn.fetchrow(
        """
        insert into conversation_export_jobs (tenant_id, conversation_id, message_id, created_by)
        values ($1, $2, $3, $4)
        returning *
        """,
        ctx.tenant_id,
        conversation_id,
        message_id,
        ctx.user_id,
    )
    await write_audit(
        conn,
        ctx.tenant_id,
        ctx.user_id,
        "message.pdf_export",
        "message",
        str(message_id),
    )
    # Enqueue inside the transaction: if Redis is down the job row rolls back
    # and the client sees the 503 rather than a stuck "queued" job.
    await ingest_queue.enqueue_answer_pdf(ctx.tenant_id, row["id"], ctx.user_id)
    return _job_out(row)


@router.get("/conversations/exports/{job_id}", response_model=ConversationExportJobOut)
async def get_export_job(
    job_id: UUID,
    ctx: TenantContext = Depends(require_role("member")),
    conn: asyncpg.Connection = Depends(get_conn),
):
    row = await conn.fetchrow("select * from conversation_export_jobs where id = $1", job_id)
    if row is None:  # RLS scoped — cross-tenant ids are invisible
        raise ApiError(404, "not_found", "Export job not found")
    download_url = None
    if row["status"] == "succeeded" and row["file_key"]:
        download_url = storage.presign_get(row["file_key"])
    return _job_out(row, download_url)
