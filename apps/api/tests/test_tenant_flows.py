"""Functional flows: bootstrap, tenant resolution, roles, seats, invites."""

from datetime import UTC, datetime
from uuid import uuid4

from tests.conftest import auth, make_token, seed_tenant


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


async def test_brand_validation_and_logo_upload_guards(client):
    tenant = await seed_tenant(client, f"logo-{uuid4().hex[:6]}")
    headers = auth(tenant.owner_id, tenant.id)

    resp = await client.patch(
        "/api/v1/tenants/me", json={"brand": {"accent": "green"}}, headers=headers
    )
    assert resp.status_code == 422

    resp = await client.patch(
        "/api/v1/tenants/me", json={"brand": {"accent": "#336699"}}, headers=headers
    )
    assert resp.status_code == 200
    assert resp.json()["brand"]["accent"] == "#336699"
    assert resp.json()["logo_url"] is None

    resp = await client.post(
        "/api/v1/tenants/me/logo",
        json={"mime": "image/svg+xml", "size_bytes": 100},
        headers=headers,
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "unsupported_type"

    resp = await client.post(
        "/api/v1/tenants/me/logo",
        json={"mime": "image/png", "size_bytes": 3 * 1024 * 1024},
        headers=headers,
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "too_large"

    # Storage is disabled in unit tests: a valid request 503s rather than
    # minting a URL.
    resp = await client.post(
        "/api/v1/tenants/me/logo", json={"mime": "image/png", "size_bytes": 1000}, headers=headers
    )
    assert resp.status_code == 503
    assert resp.json()["error"]["code"] == "storage_unavailable"

    # Members cannot touch branding.
    member = uuid4()
    accepted = await client.post(
        "/api/v1/invites/accept", json={"token": tenant.invite_token}, headers=auth(member)
    )
    assert accepted.status_code == 200
    resp = await client.post(
        "/api/v1/tenants/me/logo",
        json={"mime": "image/png", "size_bytes": 1000},
        headers=auth(member, tenant.id),
    )
    assert resp.status_code == 403


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


async def test_membership_emails_recorded_and_healed(client):
    tenant = await seed_tenant(client, f"email-{uuid4().hex[:6]}")
    headers = auth(tenant.owner_id, tenant.id)

    # Bootstrap writes the owner's JWT email claim onto the membership.
    members = (await client.get("/api/v1/members", headers=headers)).json()
    assert members[0]["email"] == "user@example.com"

    # Invite acceptance records the acceptor's own claim, not the invite email.
    invitee = uuid4()
    invitee_headers = {
        "Authorization": f"Bearer {make_token(invitee, email='new.member@example.com')}"
    }
    resp = await client.post(
        "/api/v1/invites/accept", json={"token": tenant.invite_token}, headers=invitee_headers
    )
    assert resp.status_code == 200
    members = (await client.get("/api/v1/members", headers=headers)).json()
    by_user = {m["user_id"]: m for m in members}
    assert by_user[str(invitee)]["email"] == "new.member@example.com"

    # Pre-migration rows (email null) self-heal on tenant resolution.
    from app.db import db

    async with db.tenant_tx(tenant.owner_id, tenant.id) as conn:
        await conn.execute(
            "update memberships set email = null where user_id = $1", tenant.owner_id
        )
    assert (await client.get("/api/v1/tenants/me", headers=headers)).status_code == 200
    members = (await client.get("/api/v1/members", headers=headers)).json()
    by_user = {m["user_id"]: m for m in members}
    assert by_user[str(tenant.owner_id)]["email"] == "user@example.com"


async def test_member_role_change_flows(client):
    tenant = await seed_tenant(client, f"role-{uuid4().hex[:6]}")
    owner_headers = auth(tenant.owner_id, tenant.id)
    member = uuid4()
    accepted = await client.post(
        "/api/v1/invites/accept", json={"token": tenant.invite_token}, headers=auth(member)
    )
    assert accepted.status_code == 200
    members = (await client.get("/api/v1/members", headers=owner_headers)).json()
    member_row = next(m for m in members if m["user_id"] == str(member))

    # A member cannot change roles.
    resp = await client.patch(
        f"/api/v1/members/{member_row['id']}",
        json={"role": "admin"},
        headers=auth(member, tenant.id),
    )
    assert resp.status_code == 403

    # Owner promotes member -> admin.
    resp = await client.patch(
        f"/api/v1/members/{member_row['id']}", json={"role": "admin"}, headers=owner_headers
    )
    assert resp.status_code == 200
    assert resp.json()["role"] == "admin"

    # An admin cannot grant owner.
    resp = await client.patch(
        f"/api/v1/members/{member_row['id']}",
        json={"role": "owner"},
        headers=auth(member, tenant.id),
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "insufficient_role"

    # Same-role PATCH is a no-op 200.
    resp = await client.patch(
        f"/api/v1/members/{member_row['id']}", json={"role": "admin"}, headers=owner_headers
    )
    assert resp.status_code == 200

    # The last owner cannot be demoted.
    resp = await client.patch(
        f"/api/v1/members/{tenant.membership_id}", json={"role": "member"}, headers=owner_headers
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "last_owner"

    # With a second owner in place, the original owner can step down.
    resp = await client.patch(
        f"/api/v1/members/{member_row['id']}", json={"role": "owner"}, headers=owner_headers
    )
    assert resp.status_code == 200
    resp = await client.patch(
        f"/api/v1/members/{tenant.membership_id}", json={"role": "member"}, headers=owner_headers
    )
    assert resp.status_code == 200
    assert resp.json()["role"] == "member"

    # Unknown roles are rejected by the schema.
    resp = await client.patch(
        f"/api/v1/members/{member_row['id']}",
        json={"role": "superuser"},
        headers=auth(member, tenant.id),
    )
    assert resp.status_code == 422

    # Audit trail recorded the changes.
    from app.db import db

    async with db.tenant_tx(member, tenant.id) as conn:
        actions = {
            r["action"]
            for r in await conn.fetch(
                "select action from audit_log where tenant_id = $1", tenant.id
            )
        }
    assert "member.role_change" in actions


async def test_mutations_write_audit_log(client, two_tenants):
    a, _ = two_tenants
    from app.db import db

    async with db.tenant_tx(a.owner_id, a.id) as conn:
        actions = {
            r["action"]
            for r in await conn.fetch("select action from audit_log where tenant_id = $1", a.id)
        }
    assert {"tenant.create", "invite.create"} <= actions
