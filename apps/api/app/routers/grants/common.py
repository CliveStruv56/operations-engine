"""Shared helpers for the Grantwork routers.

`require_grants` comes from the module manifest (`app/modules.py`); the alias
lives here so every Grantwork router imports the gate from one place.

The `visible_*` helpers exist because Postgres checks foreign keys with RLS
bypassed: a cross-tenant `funder_id` or `project_id` would be accepted by the
constraint. Every referenced id is therefore resolved through an RLS-scoped
select first, so a foreign id 404s rather than linking (ASSUMPTIONS #19, and
asserted directly by `test_grantwork_cross_module_link_does_not_widen_
visibility`).
"""

import json
from uuid import UUID

import asyncpg

from app.errors import ApiError
from app.modules import make_feature_gate
from app.storage import ALLOWED_MIMES

require_grants = make_feature_gate("grants")

STAGE_ORDER = ["case", "prospect", "apply", "decision", "deliver", "monitor", "evaluate"]
DOC_UPLOAD_MIMES = {k: v for k, v in ALLOWED_MIMES.items() if v in ("pdf", "docx", "xlsx")}


async def module_application(conn: asyncpg.Connection, application_id: UUID) -> asyncpg.Record:
    """Resolve an application under RLS, or 404. Every subresource route calls
    this first so a foreign id never reaches a child table's query."""
    row = await conn.fetchrow("select * from grant_applications where id = $1", application_id)
    if row is None:
        raise ApiError(404, "not_found", "Application not found")
    return row


async def visible_funder(conn: asyncpg.Connection, funder_id: UUID) -> None:
    if not await conn.fetchval("select 1 from grant_funders where id = $1", funder_id):
        raise ApiError(404, "not_found", "Funder not found")


async def visible_project(conn: asyncpg.Connection, project_id: UUID) -> None:
    if not await conn.fetchval("select 1 from projects where id = $1", project_id):
        raise ApiError(404, "not_found", "Project not found")


def stage_out(row: asyncpg.Record) -> dict:
    out = dict(row)
    out["gate"] = json.loads(out["gate"])
    return out


def doc_out(row: asyncpg.Record) -> dict:
    out = dict(row)
    out["versions"] = json.loads(out["versions"])
    return out
