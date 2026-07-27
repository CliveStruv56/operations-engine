import secrets
from datetime import UTC, datetime, timedelta

import asyncpg
from fastapi import APIRouter, Depends

from app.audit import write_audit
from app.auth import AuthUser, get_current_user
from app.db import db
from app.errors import ApiError
from app.schemas import InviteAccept, InviteAcceptOut, InviteCreate, InviteOut
from app.tenant import TenantContext, get_conn, require_role

router = APIRouter(tags=["invites"])

INVITE_TTL_DAYS = 7


@router.post("/invites", status_code=201, response_model=InviteOut)
async def create_invite(
    body: InviteCreate,
    ctx: TenantContext = Depends(require_role("admin")),
    conn: asyncpg.Connection = Depends(get_conn),
):
    # Seat enforcement (spec §8): members + pending invites ≤ seats.
    seats, members, pending = await conn.fetchrow(
        """
        select t.seats,
               (select count(*) from memberships m where m.tenant_id = t.id),
               (select count(*) from invites i
                 where i.tenant_id = t.id and i.accepted_at is null and i.expires_at > now())
        from tenants t where t.id = $1
        """,
        ctx.tenant_id,
    )
    if members + pending >= seats:
        raise ApiError(409, "seat_limit", f"All {seats} seats are taken or reserved")
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(UTC) + timedelta(days=INVITE_TTL_DAYS)
    row = await conn.fetchrow(
        """
        insert into invites (tenant_id, email, role, token, expires_at, created_by)
        values ($1, $2, $3, $4, $5, $6)
        returning id, email, role, token, expires_at
        """,
        ctx.tenant_id,
        body.email,
        body.role,
        token,
        expires_at,
        ctx.user_id,
    )
    await write_audit(
        conn,
        ctx.tenant_id,
        ctx.user_id,
        "invite.create",
        "invite",
        str(row["id"]),
        meta={"email": body.email, "role": body.role},
    )
    # Resend delivery is wired in Slice 5; the token is returned for now.
    return dict(row)


@router.post("/invites/accept", response_model=InviteAcceptOut)
async def accept_invite(body: InviteAccept, user: AuthUser = Depends(get_current_user)):
    # accept_invite() is SECURITY DEFINER: it validates the token and creates
    # the membership without a tenant context, which RLS otherwise forbids.
    async with db.user_tx(user.id) as conn:
        try:
            row = await conn.fetchrow("select * from accept_invite($1, $2)", body.token, user.id)
        except asyncpg.RaiseError as exc:
            raise ApiError(400, "invalid_invite", "Invite is invalid or expired") from exc
    tenant_id, role = row["out_tenant_id"], row["out_role"]
    async with db.tenant_tx(user.id, tenant_id) as conn:
        await write_audit(
            conn,
            tenant_id,
            user.id,
            "invite.accept",
            "tenant",
            str(tenant_id),
            meta={"role": role},
        )
    return {"tenant_id": tenant_id, "role": role}
