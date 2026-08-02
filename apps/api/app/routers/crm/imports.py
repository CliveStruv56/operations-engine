"""CSV import: bulk-create/update contacts, auto-creating companies."""

import asyncpg
from fastapi import APIRouter, Depends

from app.audit import write_audit
from app.crm.importer import MAX_ROWS, ImportResult, apply_rows, parse_csv
from app.crm.schemas import ImportIn, ImportOut
from app.errors import ApiError
from app.routers.crm.common import require_contacts
from app.tenant import TenantContext, get_conn

router = APIRouter()


@router.post("/contacts/import", response_model=ImportOut)
async def import_contacts(
    body: ImportIn,
    ctx: TenantContext = Depends(require_contacts),
    conn: asyncpg.Connection = Depends(get_conn),
):
    result = ImportResult()
    rows = parse_csv(body.csv, result)
    if len(rows) > MAX_ROWS:
        raise ApiError(400, "too_many_rows", f"CSV imports are capped at {MAX_ROWS} rows")
    applied = await apply_rows(conn, ctx.tenant_id, ctx.user_id, rows)
    applied.skipped += result.skipped
    applied.errors = (result.errors + applied.errors)[:20]
    await write_audit(
        conn,
        ctx.tenant_id,
        ctx.user_id,
        "crm.import",
        "contact",
        None,
        {
            "created": applied.created,
            "updated": applied.updated,
            "skipped": applied.skipped,
            "companies_created": applied.companies_created,
        },
    )
    return applied
