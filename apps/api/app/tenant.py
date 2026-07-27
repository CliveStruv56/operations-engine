from collections.abc import AsyncIterator
from dataclasses import dataclass
from uuid import UUID

import asyncpg
from fastapi import Depends, Request

from app.auth import AuthUser, get_current_user
from app.db import db
from app.errors import ApiError

ROLE_ORDER = {"member": 0, "admin": 1, "owner": 2}


@dataclass(frozen=True)
class TenantContext:
    user_id: UUID
    tenant_id: UUID
    role: str


async def resolve_tenant(
    request: Request, user: AuthUser = Depends(get_current_user)
) -> TenantContext:
    """Spec §3 tenant resolution: X-Tenant-Id header (must match a membership)
    → sole-membership fallback → 400 with membership list."""
    async with db.user_tx(user.id) as conn:
        rows = await conn.fetch(
            """
            select m.tenant_id, m.role, t.name
            from memberships m
            join tenants t on t.id = m.tenant_id
            where m.user_id = $1
            order by m.created_at
            """,
            user.id,
        )
    header = request.headers.get("X-Tenant-Id")
    if header:
        try:
            wanted = UUID(header)
        except ValueError as exc:
            raise ApiError(400, "invalid_tenant_id", "X-Tenant-Id is not a UUID") from exc
        for row in rows:
            if row["tenant_id"] == wanted:
                return TenantContext(user_id=user.id, tenant_id=wanted, role=row["role"])
        raise ApiError(403, "not_a_member", "You are not a member of this tenant")
    if len(rows) == 1:
        row = rows[0]
        return TenantContext(user_id=user.id, tenant_id=row["tenant_id"], role=row["role"])
    raise ApiError(
        400,
        "tenant_required",
        "Pass X-Tenant-Id to select a tenant",
        memberships=[
            {"tenant_id": str(r["tenant_id"]), "name": r["name"], "role": r["role"]} for r in rows
        ],
    )


async def get_conn(
    ctx: TenantContext = Depends(resolve_tenant),
) -> AsyncIterator[asyncpg.Connection]:
    """One tenant-scoped transaction per request."""
    async with db.tenant_tx(ctx.user_id, ctx.tenant_id) as conn:
        yield conn


def require_role(minimum: str):
    async def _check(ctx: TenantContext = Depends(resolve_tenant)) -> TenantContext:
        if ROLE_ORDER[ctx.role] < ROLE_ORDER[minimum]:
            raise ApiError(403, "insufficient_role", f"Requires {minimum} role")
        return ctx

    return _check
