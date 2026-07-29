"""Vault documents (spec §5, §6): presigned upload → complete → async ingest.

The API never touches file bytes — the browser PUTs straight to storage with
a presigned URL, and `complete` verifies the object server-side (existence +
size) before queueing ingestion. Status lifecycle:
uploaded → parsing → embedding → ready | failed.
"""

from uuid import UUID, uuid4

import asyncpg
from fastapi import APIRouter, Depends, Query

from app.audit import write_audit
from app.db import db
from app.errors import ApiError
from app.queue import ingest_queue
from app.ratelimit import rate_limiter
from app.schemas import DocumentCreate, DocumentCreateOut, DocumentOut
from app.storage import ALLOWED_MIMES, MAX_UPLOAD_BYTES, storage
from app.tenant import TenantContext, get_conn, require_role

router = APIRouter(tags=["documents"])


async def _get_document(conn: asyncpg.Connection, document_id: UUID) -> asyncpg.Record:
    row = await conn.fetchrow("select * from documents where id = $1", document_id)
    if row is None:  # RLS already scoped the select to the tenant
        raise ApiError(404, "not_found", "Document not found")
    return row


@router.post("/documents", status_code=201, response_model=DocumentCreateOut)
async def create_document(
    body: DocumentCreate,
    ctx: TenantContext = Depends(require_role("member")),
    conn: asyncpg.Connection = Depends(get_conn),
):
    if body.mime not in ALLOWED_MIMES:
        raise ApiError(
            400,
            "unsupported_type",
            f"Supported types: {', '.join(sorted(set(ALLOWED_MIMES.values())))}",
        )
    if body.size_bytes > MAX_UPLOAD_BYTES:
        raise ApiError(400, "too_large", "Files are limited to 50 MB")
    await rate_limiter.check_upload(ctx.tenant_id)

    document_id = uuid4()
    key = f"{ctx.tenant_id}/{document_id}.{ALLOWED_MIMES[body.mime]}"
    upload_url = storage.presign_put(key, body.mime)
    await conn.execute(
        """
        insert into documents (id, tenant_id, title, storage_key, mime, created_by)
        values ($1, $2, $3, $4, $5, $6)
        """,
        document_id,
        ctx.tenant_id,
        body.title,
        key,
        body.mime,
        ctx.user_id,
    )
    await write_audit(
        conn, ctx.tenant_id, ctx.user_id, "document.create", "document", str(document_id)
    )
    return {"id": document_id, "upload_url": upload_url}


@router.post("/documents/{document_id}/complete", response_model=DocumentOut)
async def complete_upload(
    document_id: UUID,
    ctx: TenantContext = Depends(require_role("member")),
):
    async with db.tenant_tx(ctx.user_id, ctx.tenant_id) as conn:
        doc = await _get_document(conn, document_id)
        if doc["status"] != "uploaded":
            raise ApiError(409, "invalid_state", f"Document is already {doc['status']}")

    # Server-side validation of the presigned upload (spec §9.3) — outside the
    # transaction: it's a network call.
    size = await storage.object_size(doc["storage_key"])
    if size is None:
        raise ApiError(400, "not_uploaded", "No file has been uploaded for this document")
    if size > MAX_UPLOAD_BYTES:
        await storage.delete_object(doc["storage_key"])
        async with db.tenant_tx(ctx.user_id, ctx.tenant_id) as conn:
            await conn.execute(
                "update documents set status = 'failed', error = 'File exceeds 50 MB',"
                " updated_at = now() where id = $1",
                document_id,
            )
        raise ApiError(400, "too_large", "Files are limited to 50 MB")

    await ingest_queue.enqueue_ingest(ctx.tenant_id, document_id, ctx.user_id)
    async with db.tenant_tx(ctx.user_id, ctx.tenant_id) as conn:
        row = await conn.fetchrow(
            """
            update documents set status = 'parsing', error = null, updated_at = now()
            where id = $1 returning *
            """,
            document_id,
        )
        await write_audit(
            conn, ctx.tenant_id, ctx.user_id, "document.complete", "document", str(document_id)
        )
    return dict(row)


@router.get("/documents", response_model=list[DocumentOut])
async def list_documents(
    status: str | None = Query(default=None),
    ctx: TenantContext = Depends(require_role("member")),
    conn: asyncpg.Connection = Depends(get_conn),
):
    if status is not None:
        rows = await conn.fetch(
            "select * from documents where status = $1 order by created_at desc", status
        )
    else:
        rows = await conn.fetch("select * from documents order by created_at desc")
    return [dict(r) for r in rows]


@router.get("/documents/{document_id}", response_model=DocumentOut)
async def get_document(
    document_id: UUID,
    ctx: TenantContext = Depends(require_role("member")),
    conn: asyncpg.Connection = Depends(get_conn),
):
    return dict(await _get_document(conn, document_id))


@router.delete("/documents/{document_id}", status_code=204)
async def delete_document(
    document_id: UUID,
    ctx: TenantContext = Depends(require_role("member")),
):
    async with db.tenant_tx(ctx.user_id, ctx.tenant_id) as conn:
        doc = await _get_document(conn, document_id)
        if ctx.role == "member" and doc["created_by"] != ctx.user_id:
            raise ApiError(403, "forbidden", "Only admins can delete documents added by others")

    # Object first, row second: a leftover row is retryable, an orphaned
    # object with no row is invisible (GDPR delete must not strand files).
    if doc["storage_key"]:
        await storage.delete_object(doc["storage_key"])
    async with db.tenant_tx(ctx.user_id, ctx.tenant_id) as conn:
        await conn.execute("delete from documents where id = $1", document_id)  # cascades chunks
        await write_audit(
            conn, ctx.tenant_id, ctx.user_id, "document.delete", "document", str(document_id)
        )


@router.post("/documents/{document_id}/reprocess", response_model=DocumentOut)
async def reprocess_document(
    document_id: UUID,
    ctx: TenantContext = Depends(require_role("member")),
):
    async with db.tenant_tx(ctx.user_id, ctx.tenant_id) as conn:
        doc = await _get_document(conn, document_id)
        if doc["status"] not in ("ready", "failed"):
            raise ApiError(409, "invalid_state", f"Document is currently {doc['status']}")

    await ingest_queue.enqueue_ingest(ctx.tenant_id, document_id, ctx.user_id)
    async with db.tenant_tx(ctx.user_id, ctx.tenant_id) as conn:
        row = await conn.fetchrow(
            """
            update documents set status = 'parsing', error = null, updated_at = now()
            where id = $1 returning *
            """,
            document_id,
        )
        await write_audit(
            conn, ctx.tenant_id, ctx.user_id, "document.reprocess", "document", str(document_id)
        )
    return dict(row)
