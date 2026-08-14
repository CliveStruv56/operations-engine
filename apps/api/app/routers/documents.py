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
from app.litellm import litellm_client
from app.queue import ingest_queue
from app.ratelimit import rate_limiter
from app.retrieval import retrieve
from app.schemas import (
    DocumentCreate,
    DocumentCreateOut,
    DocumentOut,
    DocumentUpdate,
    VaultSearchHit,
    VaultSearchIn,
)
from app.secrets import decrypt_llm_key
from app.sqlutil import patch_sets
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

    if body.project_id is not None:
        exists = await conn.fetchval("select 1 from projects where id = $1", body.project_id)
        if not exists:
            raise ApiError(404, "not_found", "Project not found")

    document_id = uuid4()
    key = f"{ctx.tenant_id}/{document_id}.{ALLOWED_MIMES[body.mime]}"
    upload_url = storage.presign_put(key, body.mime)
    await conn.execute(
        """
        insert into documents (id, tenant_id, title, storage_key, mime, project_id, created_by)
        values ($1, $2, $3, $4, $5, $6, $7)
        """,
        document_id,
        ctx.tenant_id,
        body.title,
        key,
        body.mime,
        body.project_id,
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
                " updated_at = now() where id = $1 and status = 'uploaded'",
                document_id,
            )
        raise ApiError(400, "too_large", "Files are limited to 50 MB")

    # Guarded claim: exactly one concurrent complete flips uploaded → parsing.
    # Enqueue inside the transaction so a failed enqueue rolls the claim back.
    async with db.tenant_tx(ctx.user_id, ctx.tenant_id) as conn:
        row = await conn.fetchrow(
            """
            update documents set status = 'parsing', error = null, updated_at = now()
            where id = $1 and status = 'uploaded' returning *
            """,
            document_id,
        )
        if row is None:
            raise ApiError(409, "invalid_state", "Document is already being processed")
        await write_audit(
            conn, ctx.tenant_id, ctx.user_id, "document.complete", "document", str(document_id)
        )
        await ingest_queue.enqueue_ingest(ctx.tenant_id, document_id, ctx.user_id)
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


@router.patch("/documents/{document_id}", response_model=DocumentOut)
async def update_document(
    document_id: UUID,
    body: DocumentUpdate,
    ctx: TenantContext = Depends(require_role("member")),
    conn: asyncpg.Connection = Depends(get_conn),
):
    """Assign to a project / mark as one of its primary documents."""
    updates = body.model_dump(exclude_unset=True)
    if not updates:
        raise ApiError(400, "no_changes", "Nothing to update")
    if updates.get("project_id") is not None:
        exists = await conn.fetchval("select 1 from projects where id = $1", body.project_id)
        if not exists:
            raise ApiError(404, "not_found", "Project not found")
    await _get_document(conn, document_id)
    sets, values = patch_sets("documents", updates)
    row = await conn.fetchrow(
        f"update documents set {sets}, updated_at = now() where id = $1 returning *",
        document_id,
        *values,
    )
    await write_audit(
        conn, ctx.tenant_id, ctx.user_id, "document.update", "document", str(document_id)
    )
    return dict(row)


@router.delete("/documents/{document_id}", status_code=204)
async def delete_document(
    document_id: UUID,
    ctx: TenantContext = Depends(require_role("member")),
):
    async with db.tenant_tx(ctx.user_id, ctx.tenant_id) as conn:
        doc = await conn.fetchrow("select * from documents where id = $1 for update", document_id)
        if doc is None:  # RLS already scoped the select to the tenant
            raise ApiError(404, "not_found", "Document not found")
        if ctx.role == "member" and doc["created_by"] != ctx.user_id:
            raise ApiError(403, "forbidden", "Only admins can delete documents added by others")

        # Object first, row second: a leftover row is retryable, an orphaned
        # object with no row is invisible (GDPR delete must not strand files).
        # The row lock serialises concurrent deletes for the storage call.
        if doc["storage_key"]:
            await storage.delete_object(doc["storage_key"])
        await conn.execute("delete from documents where id = $1", document_id)  # cascades chunks
        await write_audit(
            conn, ctx.tenant_id, ctx.user_id, "document.delete", "document", str(document_id)
        )


@router.post("/vault/search", response_model=list[VaultSearchHit])
async def vault_search(
    body: VaultSearchIn,
    ctx: TenantContext = Depends(require_role("admin")),
):
    """Raw fused retrieval results — admin debug surface for tuning (spec §6)."""
    async with db.tenant_tx(ctx.user_id, ctx.tenant_id) as conn:
        virtual_key = decrypt_llm_key(
            await conn.fetchval(
                "select litellm_key_encrypted from tenants where id = $1", ctx.tenant_id
            )
        )
    if not virtual_key:
        raise ApiError(503, "llm_unavailable", "No model key is provisioned for this workspace")
    embedding, _ = await litellm_client.embed_query(virtual_key, body.query)
    async with db.tenant_tx(ctx.user_id, ctx.tenant_id) as conn:
        chunks = await retrieve(conn, embedding, body.query)
    return [
        {
            "chunk_id": c.chunk_id,
            "document_id": c.document_id,
            "title": c.title,
            "heading_path": c.heading_path,
            "page_start": c.page_start,
            "page_end": c.page_end,
            "content": c.content,
            "score": c.score,
        }
        for c in chunks
    ]


@router.post("/documents/{document_id}/reprocess", response_model=DocumentOut)
async def reprocess_document(
    document_id: UUID,
    ctx: TenantContext = Depends(require_role("member")),
):
    # Guarded claim, same shape as complete_upload: one concurrent reprocess
    # wins; a failed enqueue rolls the status change back.
    async with db.tenant_tx(ctx.user_id, ctx.tenant_id) as conn:
        doc = await _get_document(conn, document_id)
        if not doc["storage_key"]:
            # Seeded notes (the planned-project brief) have chunks but no
            # stored file: reprocessing would wipe the chunks and then fail
            # in the worker with nothing to re-read.
            raise ApiError(
                409,
                "no_source",
                "This document was created in the app — there is no file to re-index",
            )
        row = await conn.fetchrow(
            """
            update documents set status = 'parsing', error = null, updated_at = now()
            where id = $1 and status in ('ready', 'failed') returning *
            """,
            document_id,
        )
        if row is None:
            raise ApiError(409, "invalid_state", f"Document is currently {doc['status']}")
        await write_audit(
            conn, ctx.tenant_id, ctx.user_id, "document.reprocess", "document", str(document_id)
        )
        await ingest_queue.enqueue_ingest(ctx.tenant_id, document_id, ctx.user_id)
    return dict(row)
