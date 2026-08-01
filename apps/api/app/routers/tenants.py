import json
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import asyncpg
from fastapi import APIRouter, Depends

from app.audit import write_audit
from app.auth import AuthUser, get_current_user
from app.config import get_settings
from app.db import db
from app.litellm import litellm_client
from app.schemas import TenantCreate, TenantMeOut, TenantOut, TenantPatch
from app.secrets import encrypt_llm_key
from app.tenant import TenantContext, get_conn, require_role

router = APIRouter(tags=["tenants"])


def _tenant_out(row: asyncpg.Record) -> dict:
    out = dict(row)
    out["brand"] = json.loads(out["brand"])
    out["features"] = json.loads(out["features"])
    return out


@router.post("/tenants", status_code=201, response_model=TenantOut)
async def create_tenant(body: TenantCreate, user: AuthUser = Depends(get_current_user)):
    """Bootstrap: tenant + owner membership + 14-day trial + LiteLLM virtual key."""
    settings = get_settings()
    tenant_id = uuid4()
    trial_ends = datetime.now(UTC) + timedelta(days=settings.trial_days)
    soft_budget = settings.default_seats * settings.default_soft_budget_per_seat_usd
    litellm_key = await litellm_client.create_tenant_key(tenant_id, soft_budget)
    async with db.tenant_tx(user.id, tenant_id) as conn:
        await conn.execute(
            """
            insert into tenants (id, name, plan, seats, soft_budget_usd, trial_ends_at,
                                 litellm_key_encrypted)
            values ($1, $2, 'trial', $3, $4, $5, $6)
            """,
            tenant_id,
            body.name,
            settings.default_seats,
            soft_budget,
            trial_ends,
            encrypt_llm_key(litellm_key),
        )
        await conn.execute(
            "insert into memberships (user_id, tenant_id, role, email)"
            " values ($1, $2, 'owner', $3)",
            user.id,
            tenant_id,
            user.email,
        )
        await write_audit(conn, tenant_id, user.id, "tenant.create", "tenant", str(tenant_id))
        row = await conn.fetchrow("select * from tenants where id = $1", tenant_id)
    return _tenant_out(row)


@router.get("/tenants/me", response_model=TenantMeOut)
async def get_my_tenant(
    ctx: TenantContext = Depends(require_role("member")),
    conn: asyncpg.Connection = Depends(get_conn),
):
    row = await conn.fetchrow("select * from tenants where id = $1", ctx.tenant_id)
    return {**_tenant_out(row), "role": ctx.role}


@router.patch("/tenants/me", response_model=TenantMeOut)
async def patch_my_tenant(
    body: TenantPatch,
    ctx: TenantContext = Depends(require_role("admin")),
    conn: asyncpg.Connection = Depends(get_conn),
):
    await conn.execute(
        """
        update tenants
        set name = coalesce($2, name),
            brand = coalesce($3, brand),
            updated_at = now()
        where id = $1
        """,
        ctx.tenant_id,
        body.name,
        json.dumps(body.brand) if body.brand is not None else None,
    )
    await write_audit(
        conn,
        ctx.tenant_id,
        ctx.user_id,
        "tenant.update",
        "tenant",
        str(ctx.tenant_id),
        meta={"fields": [k for k, v in body.model_dump().items() if v is not None]},
    )
    row = await conn.fetchrow("select * from tenants where id = $1", ctx.tenant_id)
    return {**_tenant_out(row), "role": ctx.role}
