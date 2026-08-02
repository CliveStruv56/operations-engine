"""Operator console: platform-admin-only tenant onboarding and fleet view.

Identity is the login email against PLATFORM_ADMIN_EMAILS — no tenant
context, no membership. Creation reuses the bootstrap pattern (tenant_tx
scoped to the freshly minted tenant id); only the fleet listing crosses
tenants, via the fenced db.platform_tx() owner connection.
"""

import json
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends

from app.audit import write_audit
from app.auth import AuthUser, get_current_user, is_platform_admin
from app.config import get_settings
from app.db import db
from app.errors import ApiError
from app.litellm import litellm_client
from app.routers.invites import INVITE_TTL_DAYS
from app.schemas import (
    AdminInviteOut,
    AdminOwnerInviteIn,
    AdminTenantCreate,
    AdminTenantCreatedOut,
    AdminTenantRow,
)
from app.secrets import encrypt_llm_key

router = APIRouter(tags=["admin"])


async def require_platform_admin(user: AuthUser = Depends(get_current_user)) -> AuthUser:
    if not is_platform_admin(user.email):
        raise ApiError(403, "platform_admin_required", "This endpoint is for the platform operator")
    return user


async def _create_owner_invite(conn, tenant_id: UUID, email: str, created_by: UUID) -> dict:
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(UTC) + timedelta(days=INVITE_TTL_DAYS)
    row = await conn.fetchrow(
        """
        insert into invites (tenant_id, email, role, token, expires_at, created_by)
        values ($1, $2, 'owner', $3, $4, $5)
        returning id, email, role, token, expires_at
        """,
        tenant_id,
        email,
        token,
        expires_at,
        created_by,
    )
    await write_audit(
        conn,
        tenant_id,
        created_by,
        "invite.create",
        "invite",
        str(row["id"]),
        meta={"email": email, "role": "owner", "platform_admin": True},
    )
    return dict(row)


@router.post("/admin/tenants", status_code=201, response_model=AdminTenantCreatedOut)
async def admin_create_tenant(
    body: AdminTenantCreate,
    user: AuthUser = Depends(require_platform_admin),
):
    """Create a client workspace and an owner invite to hand it over. The
    operator gets no membership — support access goes through this console."""
    settings = get_settings()
    tenant_id = uuid4()
    seats = body.seats or settings.default_seats
    trial_days = body.trial_days if body.trial_days is not None else settings.trial_days
    trial_ends = datetime.now(UTC) + timedelta(days=trial_days)
    soft_budget = seats * settings.default_soft_budget_per_seat_usd
    litellm_key = await litellm_client.create_tenant_key(tenant_id, soft_budget)
    brand = {"accent": body.brand_accent} if body.brand_accent else {}
    async with db.tenant_tx(user.id, tenant_id) as conn:
        row = await conn.fetchrow(
            """
            insert into tenants (id, name, plan, seats, soft_budget_usd, trial_ends_at,
                                 litellm_key_encrypted, features, brand)
            values ($1, $2, 'trial', $3, $4, $5, $6, $7, $8)
            returning id, name, seats, trial_ends_at, features, brand
            """,
            tenant_id,
            body.name,
            seats,
            soft_budget,
            trial_ends,
            encrypt_llm_key(litellm_key),
            json.dumps(body.features),
            json.dumps(brand),
        )
        await write_audit(
            conn,
            tenant_id,
            user.id,
            "tenant.create",
            "tenant",
            str(tenant_id),
            meta={"platform_admin": True, "owner_email": body.owner_email},
        )
        invite = await _create_owner_invite(conn, tenant_id, body.owner_email, user.id)
    out = dict(row)
    out["features"] = json.loads(out["features"])
    out["brand"] = json.loads(out["brand"])
    out["invite"] = invite
    return out


@router.post(
    "/admin/tenants/{tenant_id}/owner-invite", status_code=201, response_model=AdminInviteOut
)
async def admin_reissue_owner_invite(
    tenant_id: UUID,
    body: AdminOwnerInviteIn,
    user: AuthUser = Depends(require_platform_admin),
):
    """Fresh owner invite for an existing workspace (links expire after a
    week; clients lose emails)."""
    async with db.tenant_tx(user.id, tenant_id) as conn:
        if not await conn.fetchval("select 1 from tenants where id = $1", tenant_id):
            raise ApiError(404, "not_found", "Workspace not found")
        return await _create_owner_invite(conn, tenant_id, body.email, user.id)


@router.get("/admin/tenants", response_model=list[AdminTenantRow])
async def admin_list_tenants(user: AuthUser = Depends(require_platform_admin)):
    async with db.platform_tx() as conn:
        rows = await conn.fetch(
            """
            select t.id, t.name, t.plan, t.seats, t.trial_ends_at, t.created_at, t.features,
                   (select count(*) from memberships m where m.tenant_id = t.id)::int
                       as member_count,
                   (select count(*) from invites i
                     where i.tenant_id = t.id and i.accepted_at is null
                       and i.expires_at > now())::int as pending_invites,
                   coalesce((select sum(u.cost_usd) from usage_events u
                     where u.tenant_id = t.id
                       and u.created_at >= date_trunc('month', now())), 0)::float
                       as month_cost_usd,
                   coalesce((select count(*) from usage_events u
                     where u.tenant_id = t.id
                       and u.created_at >= date_trunc('month', now())), 0)::int
                       as month_requests
            from tenants t order by t.created_at desc
            """
        )
    out = []
    for r in rows:
        d = dict(r)
        d["features"] = json.loads(d["features"])
        out.append(d)
    return out
