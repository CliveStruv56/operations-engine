"""Document registry: status/vault links, versioned uploads, downloads."""

import json
from datetime import UTC, datetime
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends

from app.audit import write_audit
from app.errors import ApiError
from app.groundwork.gates import recompute_doc_gates
from app.groundwork.schemas import (
    DocUploadCompleteIn,
    DocUploadIn,
    DocUploadOut,
    ModuleDocOut,
    ModuleDocPatch,
)
from app.routers.groundwork import require_projects
from app.routers.groundwork_room.common import DOC_UPLOAD_MIMES, doc_out, module_project
from app.sqlutil import patch_sets
from app.storage import MAX_UPLOAD_BYTES, storage
from app.tenant import TenantContext, get_conn

router = APIRouter()


@router.get("/projects/{project_id}/documents", response_model=list[ModuleDocOut])
async def list_registry(
    project_id: UUID,
    ctx: TenantContext = Depends(require_projects),
    conn: asyncpg.Connection = Depends(get_conn),
):
    await module_project(conn, project_id)
    rows = await conn.fetch(
        "select * from proj_documents where project_id = $1 order by stage_key, doc_type_key",
        project_id,
    )
    return [doc_out(r) for r in rows]


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
    return doc_out(row)


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
    return doc_out(row)


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
