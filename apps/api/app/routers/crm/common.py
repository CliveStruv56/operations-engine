"""CRM module gate: every route 404s unless `tenants.features->>'contacts'`."""

import asyncpg
from fastapi import Depends

from app.errors import ApiError
from app.tenant import TenantContext, get_conn, require_role


async def require_contacts(
    ctx: TenantContext = Depends(require_role("member")),
    conn: asyncpg.Connection = Depends(get_conn),
) -> TenantContext:
    enabled = await conn.fetchval(
        "select features->>'contacts' = 'true' from tenants where id = $1", ctx.tenant_id
    )
    if not enabled:
        raise ApiError(404, "not_found", "Not found")
    return ctx
