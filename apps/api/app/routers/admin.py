"""Operator console: platform-admin-only tenant onboarding, fleet view, and
the curated question-set catalogue.

Identity is the login email against PLATFORM_ADMIN_EMAILS — no tenant
context, no membership. Creation reuses the bootstrap pattern (tenant_tx
scoped to the freshly minted tenant id).

Two things here cross tenants, both via the fenced db.platform_tx() owner
connection: the fleet listing, and publishing a workspace's transcribed
funder form into `ref_question_sets` — a table with no tenant to scope it to
and no write path for the runtime role (ASSUMPTIONS #28).
"""

import json
import logging
import secrets
from datetime import UTC, date, datetime, timedelta
from uuid import UUID, uuid4

import httpx
from fastapi import APIRouter, Depends

from app.audit import write_audit
from app.auth import AuthUser, get_current_user, is_platform_admin
from app.config import get_settings
from app.db import db
from app.errors import ApiError
from app.litellm import litellm_client
from app.refdata.promote import list_candidates, promote, withdraw
from app.refdata.questions import get_platform_set, list_platform_sets
from app.refdata.schemas import PromoteCandidate, PromoteIn, QuestionSetOut
from app.routers.invites import INVITE_TTL_DAYS
from app.schemas import (
    AdminFeaturesIn,
    AdminFeaturesOut,
    AdminInviteOut,
    AdminOwnerInviteIn,
    AdminSuspendIn,
    AdminTenantCreate,
    AdminTenantCreatedOut,
    AdminTenantOut,
    AdminTenantPatch,
    AdminTenantRow,
)
from app.secrets import decrypt_llm_key, encrypt_llm_key
from app.sqlutil import patch_sets

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


@router.patch("/admin/tenants/{tenant_id}/features", response_model=AdminFeaturesOut)
async def admin_update_features(
    tenant_id: UUID,
    body: AdminFeaturesIn,
    user: AuthUser = Depends(require_platform_admin),
):
    """Switch modules on or off for an existing workspace.

    Creation was the only way to set `features`, so selling a module to a
    live client meant hand-editing jsonb in the database. Modules are the
    packaging lever for the plan tiers, so that had to become an operation.

    Merge rather than replace: the body names only what changes, so enabling
    one module can never silently drop another. Setting a flag false is how
    a module is withdrawn — the gates test `= 'true'`, so the routes 404 and
    the nav item disappears on the client's next load. Nothing is deleted;
    the module's rows survive a re-enable.

    Runs in tenant_tx scoped to the target tenant, as tenant creation does —
    the `tenant_update` policy accepts `id = app_current_tenant()`, so this
    needs no owner-role connection and platform_tx stays read-only.
    """
    async with db.tenant_tx(user.id, tenant_id) as conn:
        row = await conn.fetchrow(
            "update tenants set features = features || $2::jsonb where id = $1"
            " returning id, features",
            tenant_id,
            json.dumps(body.features),
        )
        if row is None:
            raise ApiError(404, "not_found", "Workspace not found")
        await write_audit(
            conn,
            tenant_id,
            user.id,
            "tenant.features_change",
            "tenant",
            str(tenant_id),
            meta={"platform_admin": True, "changed": body.features},
        )
    return {"id": row["id"], "features": json.loads(row["features"])}


_TENANT_COLS = (
    "id, name, plan, seats, trial_ends_at, features, brand, suspended_at, suspended_reason"
)


def _tenant_out(row) -> dict:
    out = dict(row)
    out["features"] = json.loads(out["features"])
    out["brand"] = json.loads(out["brand"])
    return out


@router.patch("/admin/tenants/{tenant_id}", response_model=AdminTenantOut)
async def admin_update_tenant(
    tenant_id: UUID,
    body: AdminTenantPatch,
    user: AuthUser = Depends(require_platform_admin),
):
    """Edit a workspace after creation — name, seats, trial end, plan, accent.

    Creation was previously the only chance to set any of these, so a typo in
    a client's name or a pilot needing another fortnight meant editing the
    database by hand.

    Only the fields present in the request body change, so two operators
    editing different fields cannot overwrite each other. Changing seats also
    moves `soft_budget_usd` (seats x the per-seat cap) to keep the gateway's
    fair-use ceiling in step with what the client is paying for, and re-syncs
    the LiteLLM key's own max_budget — best effort: the seat change has
    landed, so a dark gateway logs a warning rather than failing the edit.
    """
    updates = body.changes()
    if not updates:
        raise ApiError(400, "no_changes", "Send at least one field to change")
    accent = updates.pop("brand_accent", None)

    async with db.tenant_tx(user.id, tenant_id) as conn:
        current = await conn.fetchrow(
            "select brand, seats, litellm_key_encrypted from tenants where id = $1", tenant_id
        )
        if current is None:
            raise ApiError(404, "not_found", "Workspace not found")

        if "seats" in updates:
            per_seat = get_settings().default_soft_budget_per_seat_usd
            updates["soft_budget_usd"] = updates["seats"] * per_seat
        if accent is not None:
            brand = json.loads(current["brand"])
            brand["accent"] = accent
            updates["brand"] = json.dumps(brand)

        sets, params = patch_sets("tenants", updates)
        row = await conn.fetchrow(
            f"update tenants set {sets}, updated_at = now() where id = $1 returning {_TENANT_COLS}",
            tenant_id,
            *params,
        )
        await write_audit(
            conn,
            tenant_id,
            user.id,
            "tenant.update",
            "tenant",
            str(tenant_id),
            meta={"platform_admin": True, "fields": sorted(body.changes())},
        )
    if "soft_budget_usd" in updates:
        # Outside the transaction: a gateway round trip, after the row change
        # is already committed.
        try:
            await litellm_client.update_key_budget(
                decrypt_llm_key(current["litellm_key_encrypted"]) or "",
                updates["soft_budget_usd"],
            )
        except (httpx.HTTPError, ApiError):
            logging.getLogger("app.admin").warning(
                "tenant %s: seat change committed but the LiteLLM key budget"
                " re-sync failed — the gateway still enforces the old ceiling",
                tenant_id,
            )
    return _tenant_out(row)


@router.post("/admin/tenants/{tenant_id}/suspend", response_model=AdminTenantOut)
async def admin_suspend_tenant(
    tenant_id: UUID,
    body: AdminSuspendIn,
    user: AuthUser = Depends(require_platform_admin),
):
    """Take a workspace dark, reversibly.

    Tenant resolution 403s `tenant_suspended` for every member from the next
    request, which also means no suspended tenant can reach the LiteLLM
    gateway and spend. Nothing is deleted: rows, uploads and the tenant's key
    all survive, so resume restores the workspace exactly.

    This is not deletion. A real purge has to reach outside Postgres — the R2
    prefix and the LiteLLM virtual key — and is deliberately a separate job.
    """
    async with db.tenant_tx(user.id, tenant_id) as conn:
        row = await conn.fetchrow(
            "update tenants set suspended_at = now(), suspended_reason = $2,"
            f" updated_at = now() where id = $1 returning {_TENANT_COLS}",
            tenant_id,
            body.reason,
        )
        if row is None:
            raise ApiError(404, "not_found", "Workspace not found")
        await write_audit(
            conn,
            tenant_id,
            user.id,
            "tenant.suspend",
            "tenant",
            str(tenant_id),
            meta={"platform_admin": True, "reason": body.reason},
        )
    return _tenant_out(row)


@router.post("/admin/tenants/{tenant_id}/resume", response_model=AdminTenantOut)
async def admin_resume_tenant(
    tenant_id: UUID,
    user: AuthUser = Depends(require_platform_admin),
):
    """Lift a suspension. Idempotent — resuming an active workspace is a no-op."""
    async with db.tenant_tx(user.id, tenant_id) as conn:
        row = await conn.fetchrow(
            "update tenants set suspended_at = null, suspended_reason = null,"
            f" updated_at = now() where id = $1 returning {_TENANT_COLS}",
            tenant_id,
        )
        if row is None:
            raise ApiError(404, "not_found", "Workspace not found")
        await write_audit(
            conn,
            tenant_id,
            user.id,
            "tenant.resume",
            "tenant",
            str(tenant_id),
            meta={"platform_admin": True},
        )
    return _tenant_out(row)


@router.get("/admin/tenants", response_model=list[AdminTenantRow])
async def admin_list_tenants(user: AuthUser = Depends(require_platform_admin)):
    async with db.platform_tx() as conn:
        rows = await conn.fetch(
            """
            select t.id, t.name, t.plan, t.seats, t.trial_ends_at, t.created_at, t.features,
                   t.brand, t.suspended_at, t.suspended_reason,
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
    return [_tenant_out(r) for r in rows]


# -- the platform question-set catalogue -------------------------------------
#
# The curated library every workspace drafts against. A workspace transcribes
# a funder's form for itself; the operator decides which of those become
# everybody's. Both halves run on the owner connection: `ref_question_sets`
# has no tenant to scope it to and is read-only to the runtime role.


@router.get("/admin/question-sets/candidates", response_model=list[PromoteCandidate])
async def admin_list_promote_candidates(user: AuthUser = Depends(require_platform_admin)):
    """Every workspace's transcribed forms — where published ones come from."""
    async with db.platform_tx() as conn:
        return await list_candidates(conn)


@router.get("/admin/question-sets", response_model=list[QuestionSetOut])
async def admin_list_catalogue(user: AuthUser = Depends(require_platform_admin)):
    async with db.platform_tx() as conn:
        return await list_platform_sets(conn, date.today())


@router.post("/admin/question-sets/promote", status_code=201, response_model=QuestionSetOut)
async def admin_promote_question_set(
    body: PromoteIn, user: AuthUser = Depends(require_platform_admin)
):
    """Publish a workspace's form to the catalogue.

    Audited against the source tenant rather than the operator's own (they
    have none): the row that matters later is which workspace's transcription
    became everybody's, and who signed it off.
    """
    async with db.platform_tx() as conn:
        meta = await promote(conn, body)
        await write_audit(
            conn,
            body.tenant_id,
            user.id,
            "question_sets.promote",
            "ref_question_set",
            body.key,
            {**meta, "platform_admin": True, "by": user.email},
        )
        published = await get_platform_set(conn, body.key, date.today())
    assert published is not None  # just written in the same transaction
    return published


@router.delete("/admin/question-sets/{key}", status_code=204)
async def admin_withdraw_question_set(key: str, user: AuthUser = Depends(require_platform_admin)):
    """Withdraw a form from the catalogue.

    Workspaces keep the answer sheets they already drafted — those live on the
    job row — and any workspace that transcribed its own copy is untouched.
    """
    async with db.platform_tx() as conn:
        await withdraw(conn, key)
