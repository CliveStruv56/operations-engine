"""Functional flows: bootstrap, tenant resolution, roles, seats, invites."""

from datetime import UTC, datetime
from uuid import uuid4

from tests.conftest import auth, seed_tenant


async def test_bootstrap_creates_trial_tenant_with_owner(client):
    user = uuid4()
    resp = await client.post("/api/v1/tenants", json={"name": "Acme"}, headers=auth(user))
    assert resp.status_code == 201
    body = resp.json()
    assert body["plan"] == "trial"
    assert body["seats"] == 3
    trial_ends = datetime.fromisoformat(body["trial_ends_at"])
    assert 13 <= (trial_ends - datetime.now(UTC)).days <= 14

    me = await client.get("/api/v1/tenants/me", headers=auth(user))
    assert me.status_code == 200
    assert me.json()["role"] == "owner"


async def test_sole_membership_fallback_and_multi_tenant_400(client):
    user = uuid4()
    r1 = await client.post("/api/v1/tenants", json={"name": "One"}, headers=auth(user))
    # Sole membership: no header needed.
    assert (await client.get("/api/v1/tenants/me", headers=auth(user))).status_code == 200

    await client.post("/api/v1/tenants", json={"name": "Two"}, headers=auth(user))
    resp = await client.get("/api/v1/tenants/me", headers=auth(user))
    assert resp.status_code == 400
    err = resp.json()["error"]
    assert err["code"] == "tenant_required"
    assert {m["name"] for m in err["memberships"]} == {"One", "Two"}

    # Header selects explicitly.
    tenant_one = r1.json()["id"]
    resp = await client.get("/api/v1/tenants/me", headers={**auth(user), "X-Tenant-Id": tenant_one})
    assert resp.status_code == 200
    assert resp.json()["id"] == tenant_one


async def test_member_cannot_patch_tenant_or_invite(client):
    tenant = await seed_tenant(client, f"roles-{uuid4().hex[:6]}")
    member = uuid4()
    accepted = await client.post(
        "/api/v1/invites/accept", json={"token": tenant.invite_token}, headers=auth(member)
    )
    assert accepted.status_code == 200

    headers = auth(member, tenant.id)
    resp = await client.patch("/api/v1/tenants/me", json={"name": "hax"}, headers=headers)
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "insufficient_role"

    resp = await client.post("/api/v1/invites", json={"email": "x@example.com"}, headers=headers)
    assert resp.status_code == 403

    resp = await client.delete(f"/api/v1/members/{tenant.membership_id}", headers=headers)
    assert resp.status_code == 403


async def test_admin_can_patch_brand(client):
    tenant = await seed_tenant(client, f"brand-{uuid4().hex[:6]}")
    headers = auth(tenant.owner_id, tenant.id)
    resp = await client.patch(
        "/api/v1/tenants/me",
        json={"brand": {"primary": "#123456", "logo_url": "https://x/logo.png"}},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["brand"]["primary"] == "#123456"


async def test_seat_enforcement_on_invites(client):
    tenant = await seed_tenant(client, f"seats-{uuid4().hex[:6]}")
    headers = auth(tenant.owner_id, tenant.id)
    # Seeded state: 1 member + 1 pending invite of 3 seats -> one seat left.
    resp = await client.post(
        "/api/v1/invites", json={"email": "second@example.com"}, headers=headers
    )
    assert resp.status_code == 201
    resp = await client.post(
        "/api/v1/invites", json={"email": "toomany@example.com"}, headers=headers
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "seat_limit"


async def test_last_owner_cannot_be_removed(client):
    tenant = await seed_tenant(client, f"owner-{uuid4().hex[:6]}")
    headers = auth(tenant.owner_id, tenant.id)
    resp = await client.delete(f"/api/v1/members/{tenant.membership_id}", headers=headers)
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "last_owner"


async def test_invalid_invite_token_rejected(client):
    resp = await client.post(
        "/api/v1/invites/accept", json={"token": "nonsense"}, headers=auth(uuid4())
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "invalid_invite"


async def test_mutations_write_audit_log(client, two_tenants):
    a, _ = two_tenants
    from app.db import db

    async with db.tenant_tx(a.owner_id, a.id) as conn:
        actions = {
            r["action"]
            for r in await conn.fetch("select action from audit_log where tenant_id = $1", a.id)
        }
    assert {"tenant.create", "invite.create"} <= actions
