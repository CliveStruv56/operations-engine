"""The whole workspace as one downloadable ZIP — queued, worker-built.

Gathering runs under the tenant's RLS context like every other job, with one
rule RLS cannot express: other members' private conversations are excluded.
The visibility rule is app code (`_get_owned_conversation` in the API), so a
naive `select * from conversations` here would hand an admin exactly the
chat history the app itself refuses to show them. The exporter's own and
tenant-shared conversations are included; everything else — transcripts and
their generated PDFs alike — stays out.

Assembly and formats live in `export_data.py`; this module owns SQL, S3 and
the job lifecycle only.
"""

import asyncio
import contextlib
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

import asyncpg

from worker.db import tenant_tx
from worker.export_data import (
    ArchiveFile,
    assemble_archive,
    classify_generated,
    document_filename,
)
from worker.storage import download_file, list_keys, upload_file

ZIP_MIME = "application/zip"

#: Module areas exported as whole tables — a backup carries the record, not
#: an interpretation of it, so these are `select *` grouped by module.
GROUNDWORK_TABLES = (
    "proj_projects",
    "proj_stages",
    "proj_tasks",
    "proj_documents",
    "proj_budget_lines",
    "proj_funding_sources",
    "proj_risks",
    "proj_conditions",
    "proj_stakeholders",
)
GRANT_TABLES = (
    "grant_funders",
    "grant_applications",
    "grant_stages",
    "grant_tasks",
    "grant_reporting_periods",
    "grant_documents",
    "grant_conditions",
    "grant_impact_measures",
    "grant_outcomes",
)


async def _rows(conn: asyncpg.Connection, query: str, *args: Any) -> list[dict]:
    return [dict(r) for r in await conn.fetch(query, *args)]


async def gather(
    conn: asyncpg.Connection, exporter_id: UUID
) -> tuple[dict[str, Any], list[dict], set[str]]:
    """(data areas, vault document rows, included conversation ids)."""
    conversations = await _rows(
        conn,
        """
        select c.id, c.title, c.visibility, c.user_id, c.project_id,
               m.email as owner_email, c.created_at, c.updated_at
        from conversations c
        left join memberships m on m.user_id = c.user_id
        where c.visibility = 'tenant' or c.user_id = $1
        order by c.created_at
        """,
        exporter_id,
    )
    conversation_ids = [c["id"] for c in conversations]
    messages = await _rows(
        conn,
        """
        select conversation_id, role, content, citations, model, created_at
        from messages where conversation_id = any($1::uuid[])
        order by created_at
        """,
        conversation_ids,
    )
    for c in conversations:
        c["messages"] = [m for m in messages if m["conversation_id"] == c["id"]]

    documents = await _rows(
        conn,
        """
        select id, title, mime, status, storage_key, project_id, conversation_id, created_at
        from documents order by created_at
        """,
    )

    data: dict[str, Any] = {
        "members": await _rows(
            conn, "select email, role, created_at from memberships order by created_at"
        ),
        "documents": [
            {**d, "archived_as": document_filename(d["title"], str(d["id"]), d["storage_key"])}
            if d["storage_key"]
            else {**d, "archived_as": None}
            for d in documents
        ],
        "conversations": conversations,
        "claims": await _rows(
            conn,
            """
            select c.*, k.label, k.category from claims c
            left join ref_claim_kinds k on k.key = c.kind
            order by c.created_at
            """,
        ),
        "claim_revisions": await _rows(conn, "select * from claim_revisions order by changed_at"),
        "companies": await _rows(conn, "select * from crm_companies order by name"),
        "contacts": await _rows(
            conn,
            """
            select c.*, co.name as company_name from crm_contacts c
            left join crm_companies co on co.id = c.company_id order by c.name
            """,
        ),
        "projects": await _rows(conn, "select * from projects order by created_at"),
        "project_tasks": await _rows(
            conn, "select * from project_tasks order by project_id, position"
        ),
        "groundwork": {t: await _rows(conn, f"select * from {t}") for t in GROUNDWORK_TABLES},
        "grants": {t: await _rows(conn, f"select * from {t}") for t in GRANT_TABLES},
        "community": {
            "profile": next(iter(await _rows(conn, "select * from community_profile")), None),
            "assets": await _rows(conn, "select * from community_assets order by category, name"),
            "statistics": await _rows(conn, "select * from community_statistics order by label"),
        },
        "question_sets": await _rows(
            conn, "select * from tenant_question_sets order by created_at"
        ),
        "audit_log": await _rows(
            conn,
            """
            select user_id, action, target_type, target_id, meta, created_at
            from audit_log order by created_at
            """,
        ),
    }
    # Grant funder names beside their applications, for the CSV.
    funders = {f["id"]: f["name"] for f in data["grants"]["grant_funders"]}
    for app_row in data["grants"]["grant_applications"]:
        app_row["funder_name"] = funders.get(app_row.get("funder_id"))
    return data, documents, {str(c) for c in conversation_ids}


def build_file_list(
    tenant_id: str, documents: list[dict], all_keys: list[str], included_convs: set[str]
) -> list[ArchiveFile]:
    vault = [
        ArchiveFile(
            key=d["storage_key"],
            arcname=f"documents/{document_filename(d['title'], str(d['id']), d['storage_key'])}",
        )
        for d in documents
        if d["storage_key"]
    ]
    vault_keys = {f.key for f in vault}
    return vault + classify_generated(tenant_id, all_keys, vault_keys, included_convs)


# -- arq job ------------------------------------------------------------------


async def _mark_failed(pool: asyncpg.Pool, tenant_id: str, job_id: str, error: str) -> None:
    async with tenant_tx(pool, tenant_id) as conn:
        await conn.execute(
            "update workspace_export_jobs"
            " set status = 'failed', error = $2, updated_at = now() where id = $1",
            UUID(job_id),
            error[:500],
        )


async def build_workspace_export(ctx: dict, tenant_id: str, job_id: str, user_id: str) -> str:
    pool: asyncpg.Pool = ctx["pool"]
    loop = asyncio.get_running_loop()
    generated_at = datetime.now(UTC)

    async with tenant_tx(pool, tenant_id) as conn:
        job = await conn.fetchrow(
            "select * from workspace_export_jobs where id = $1", UUID(job_id)
        )
        if job is None:
            return "gone"
        await conn.execute(
            "update workspace_export_jobs"
            " set status = 'running', updated_at = now() where id = $1",
            UUID(job_id),
        )

    try:
        async with tenant_tx(pool, tenant_id) as conn:
            tenant = await conn.fetchrow(
                "select name, plan, seats, created_at from tenants where id = $1",
                UUID(tenant_id),
            )
            exporter_email = await conn.fetchval(
                "select email from memberships where user_id = $1", UUID(user_id)
            )
            data, documents, included_convs = await gather(conn, UUID(user_id))
        data = {"workspace": dict(tenant) if tenant else {}, **data}

        all_keys = await loop.run_in_executor(None, list_keys, f"{tenant_id}/")
        files = build_file_list(tenant_id, documents, all_keys, included_convs)

        with tempfile.TemporaryDirectory() as tmp:
            zip_path, _ = await loop.run_in_executor(
                None,
                lambda: assemble_archive(
                    Path(tmp),
                    tenant["name"] if tenant else "Workspace",
                    exporter_email or "a workspace admin",
                    generated_at,
                    data,
                    files,
                    download_file,
                ),
            )
            file_key = f"{tenant_id}/exports/{job_id}.zip"
            await loop.run_in_executor(None, upload_file, file_key, str(zip_path), ZIP_MIME)

        async with tenant_tx(pool, tenant_id) as conn:
            await conn.execute(
                """
                update workspace_export_jobs
                set status = 'succeeded', file_key = $2, updated_at = now()
                where id = $1
                """,
                UUID(job_id),
                file_key,
            )
            await conn.execute(
                """
                insert into audit_log (tenant_id, user_id, action, target_type, target_id, meta)
                values ($1, $2, 'tenant.export_rendered', 'workspace_export_job', $3, '{}')
                """,
                UUID(tenant_id),
                UUID(user_id),
                job_id,
            )
        return "succeeded"
    except BaseException as exc:
        reason = (
            "Export was interrupted — try again"
            if isinstance(exc, asyncio.CancelledError)
            else f"Export failed ({type(exc).__name__}: {str(exc)[:160]})"
        )
        with contextlib.suppress(BaseException):
            await _mark_failed(pool, tenant_id, job_id, reason)
        raise
