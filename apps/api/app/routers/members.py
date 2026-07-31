from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends

from app.audit import write_audit
from app.errors import ApiError
from app.schemas import MemberOut
from app.tenant import TenantContext, get_conn, require_role

router = APIRouter(tags=["members"])


@router.get("/members", response_model=list[MemberOut])
async def list_members(
    ctx: TenantContext = Depends(require_role("member")),
    conn: asyncpg.Connection = Depends(get_conn),
):
    rows = await conn.fetch(
        "select id, user_id, role, created_at from memberships"
        " where tenant_id = $1 order by created_at",
        ctx.tenant_id,
    )
    return [dict(r) for r in rows]


@router.delete("/members/{membership_id}", status_code=204)
async def remove_member(
    membership_id: UUID,
    ctx: TenantContext = Depends(require_role("admin")),
    conn: asyncpg.Connection = Depends(get_conn),
):
    target = await conn.fetchrow(
        "select id, user_id, role from memberships where id = $1", membership_id
    )
    if target is None:
        raise ApiError(404, "not_found", "Membership not found")
    if target["role"] == "owner":
        if ctx.role != "owner":
            raise ApiError(403, "insufficient_role", "Only an owner can remove an owner")
        # Lock the tenant's owner rows (ordered, to avoid deadlocks) so
        # concurrent removals serialise — otherwise two requests can each
        # delete "the other" last owner and leave the tenant ownerless.
        owners = await conn.fetch(
            "select id from memberships where tenant_id = $1 and role = 'owner'"
            " order by id for update",
            ctx.tenant_id,
        )
        if len(owners) <= 1:
            raise ApiError(409, "last_owner", "Cannot remove the last owner")
        if not any(o["id"] == membership_id for o in owners):
            # Deleted or demoted after our initial read.
            raise ApiError(404, "not_found", "Membership not found")
    deleted = await conn.fetchval(
        "delete from memberships where id = $1 returning id", membership_id
    )
    if deleted is None:
        raise ApiError(404, "not_found", "Membership not found")
    await write_audit(
        conn,
        ctx.tenant_id,
        ctx.user_id,
        "member.remove",
        "membership",
        str(membership_id),
        meta={"removed_user_id": str(target["user_id"])},
    )
