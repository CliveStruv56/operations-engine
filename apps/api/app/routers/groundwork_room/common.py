"""Shared helpers for the Groundwork project-room routers."""

import json
from uuid import UUID

import asyncpg

from app.errors import ApiError
from app.storage import ALLOWED_MIMES

STAGE_ORDER = ["group", "site", "plan", "build", "live"]
DOC_UPLOAD_MIMES = {k: v for k, v in ALLOWED_MIMES.items() if v in ("pdf", "docx", "xlsx")}


async def module_project(conn: asyncpg.Connection, project_id: UUID) -> asyncpg.Record:
    row = await conn.fetchrow(
        """
        select g.*, p.name from proj_projects g
        join projects p on p.id = g.id where g.id = $1
        """,
        project_id,
    )
    if row is None:
        raise ApiError(404, "not_found", "Project not found")
    return row


def stage_out(row: asyncpg.Record) -> dict:
    out = dict(row)
    out["gate"] = json.loads(out["gate"])
    return out


def doc_out(row: asyncpg.Record) -> dict:
    out = dict(row)
    out["versions"] = json.loads(out["versions"])
    return out
