"""The bid pack registry: status, vault links, versioned uploads, downloads.

Versions are append-only and status is advanced by a human — the drafting
engine only ever sets `drafting`, never `final` or `submitted`.
"""

import json
from datetime import UTC, datetime
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends

from app.audit import write_audit
from app.errors import ApiError
from app.grants.gates import recompute_doc_gates
from app.grants.schemas import (
    DocUploadCompleteIn,
    DocUploadIn,
    DocUploadOut,
    RegistryDocOut,
    RegistryDocPatch,
)
from app.routers.grants.common import (
    DOC_UPLOAD_MIMES,
    doc_out,
    module_application,
    require_grants,
)
from app.sqlutil import patch_sets
from app.storage import MAX_UPLOAD_BYTES, storage
from app.tenant import TenantContext, get_conn

router = APIRouter()


@router.get("/grants/applications/{application_id}/documents", response_model=list[RegistryDocOut])
async def list_registry(
    application_id: UUID,
    ctx: TenantContext = Depends(require_grants),
    conn: asyncpg.Connection = Depends(get_conn),
):
    await module_application(conn, application_id)
    rows = await conn.fetch(
        "select * from grant_documents where application_id = $1 order by stage_key, doc_type_key",
        application_id,
    )
    return [doc_out(r) for r in rows]


@router.patch(
    "/grants/applications/{application_id}/documents/{doc_id}", response_model=RegistryDocOut
)
async def patch_registry_doc(
    application_id: UUID,
    doc_id: UUID,
    body: RegistryDocPatch,
    ctx: TenantContext = Depends(require_grants),
    conn: asyncpg.Connection = Depends(get_conn),
):
    updates = body.model_dump(exclude_unset=True)
    if not updates:
        raise ApiError(400, "no_changes", "Nothing to update")
    if updates.get("vault_document_id") is not None:
        # RLS-scoped: a vault document from another tenant is invisible here,
        # so a foreign id 404s rather than backing a registry entry.
        ok = await conn.fetchval(
            "select 1 from documents where id = $1", updates["vault_document_id"]
        )
        if not ok:
            raise ApiError(404, "not_found", "Vault document not found")
    sets, values = patch_sets("grant_documents", updates, id_param=2)
    row = await conn.fetchrow(
        f"""update grant_documents set {sets}, updated_at = now()
            where application_id = $1 and id = $2 returning *""",
        application_id,
        doc_id,
        *values,
    )
    if row is None:
        raise ApiError(404, "not_found", "Registry document not found")
    if "status" in updates:
        await recompute_doc_gates(conn, application_id, row["doc_type_key"], row["status"])
    await write_audit(
        conn,
        ctx.tenant_id,
        ctx.user_id,
        "grants.document_update",
        "grant_document",
        str(doc_id),
    )
    return doc_out(row)


@router.post(
    "/grants/applications/{application_id}/documents/{doc_id}/upload",
    response_model=DocUploadOut,
)
async def upload_registry_version(
    application_id: UUID,
    doc_id: UUID,
    body: DocUploadIn,
    ctx: TenantContext = Depends(require_grants),
    conn: asyncpg.Connection = Depends(get_conn),
):
    doc = await conn.fetchrow(
        "select * from grant_documents where application_id = $1 and id = $2",
        application_id,
        doc_id,
    )
    if doc is None:
        raise ApiError(404, "not_found", "Registry document not found")
    if body.mime not in DOC_UPLOAD_MIMES:
        raise ApiError(400, "unsupported_type", "Supported types: pdf, docx, xlsx")
    if body.size_bytes > MAX_UPLOAD_BYTES:
        raise ApiError(400, "too_large", "Files are limited to 50 MB")
    version = len(json.loads(doc["versions"])) + 1
    key = (
        f"{ctx.tenant_id}/grants/{application_id}/docs/{doc_id}/"
        f"v{version}-{body.filename.replace('/', '_')}"
    )
    return {"upload_url": storage.presign_put(key, body.mime), "file_key": key}


@router.post(
    "/grants/applications/{application_id}/documents/{doc_id}/upload/complete",
    response_model=RegistryDocOut,
)
async def complete_registry_upload(
    application_id: UUID,
    doc_id: UUID,
    body: DocUploadCompleteIn,
    ctx: TenantContext = Depends(require_grants),
):
    from app.db import db

    # The object-size check is a network call, so it happens before the tenant
    # transaction opens — same shape as the Groundwork registry upload.
    size = await storage.object_size(body.file_key)
    if size is None:
        raise ApiError(400, "not_uploaded", "No file has been uploaded for this version")
    async with db.tenant_tx(ctx.user_id, ctx.tenant_id) as conn:
        doc = await conn.fetchrow(
            "select * from grant_documents where application_id = $1 and id = $2",
            application_id,
            doc_id,
        )
        if doc is None:
            raise ApiError(404, "not_found", "Registry document not found")
        if not body.file_key.startswith(f"{ctx.tenant_id}/grants/{application_id}/docs/{doc_id}/"):
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
            update grant_documents set versions = $3, current_file_key = $4, updated_at = now()
            where application_id = $1 and id = $2 returning *
            """,
            application_id,
            doc_id,
            json.dumps(versions),
            body.file_key,
        )
        await write_audit(
            conn,
            ctx.tenant_id,
            ctx.user_id,
            "grants.document_upload",
            "grant_document",
            str(doc_id),
        )
    return doc_out(row)


@router.get("/grants/applications/{application_id}/documents/{doc_id}/download")
async def download_registry_doc(
    application_id: UUID,
    doc_id: UUID,
    ctx: TenantContext = Depends(require_grants),
    conn: asyncpg.Connection = Depends(get_conn),
):
    doc = await conn.fetchrow(
        "select current_file_key from grant_documents where application_id = $1 and id = $2",
        application_id,
        doc_id,
    )
    if doc is None or not doc["current_file_key"]:
        raise ApiError(404, "not_found", "No file uploaded for this document")
    return {"download_url": storage.presign_get(doc["current_file_key"])}
