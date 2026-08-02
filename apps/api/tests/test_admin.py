"""Operator console: platform-admin gate, on-behalf tenant creation with
owner handover, fleet listing, and the invite-only signup switch."""

from uuid import uuid4

from app.config import get_settings
from tests.conftest import auth, make_token


def admin_auth(user_id) -> dict[str, str]:
    return {"Authorization": f"Bearer {make_token(user_id, email='operator@example.com')}"}


# -- gate --------------------------------------------------------------------


async def test_admin_endpoints_reject_non_admins(client, two_tenants):
    """A tenant owner is not a platform admin: every /admin endpoint 403s."""
    a, _ = two_tenants
    headers = auth(a.owner_id)  # default email is not on the admin list
    for method, path, body in [
        ("GET", "/api/v1/admin/tenants", None),
        ("POST", "/api/v1/admin/tenants", {"name": "X", "owner_email": "x@example.com"}),
        ("POST", f"/api/v1/admin/tenants/{a.id}/owner-invite", {"email": "x@example.com"}),
    ]:
        resp = await client.request(method, path, json=body, headers=headers)
        assert resp.status_code == 403, f"{method} {path} -> {resp.status_code}"
        assert resp.json()["error"]["code"] == "platform_admin_required"


# -- onboarding --------------------------------------------------------------


async def test_admin_creates_tenant_and_hands_over_ownership(client, two_tenants):
    operator = uuid4()
    resp = await client.post(
        "/api/v1/admin/tenants",
        json={
            "name": "Willow Housing",
            "owner_email": "willow@example.com",
            "seats": 5,
            "trial_days": 30,
            "features": {"projects": True, "contacts": True},
            "brand_accent": "#1f6d53",
        },
        headers=admin_auth(operator),
    )
    assert resp.status_code == 201, resp.text
    created = resp.json()
    assert created["seats"] == 5
    assert created["features"] == {"projects": True, "contacts": True}
    assert created["brand"] == {"accent": "#1f6d53"}
    assert created["invite"]["role"] == "owner"
    assert created["invite"]["email"] == "willow@example.com"

    # The client accepts the invite and owns the workspace.
    client_user = uuid4()
    resp = await client.post(
        "/api/v1/invites/accept",
        json={"token": created["invite"]["token"]},
        headers=auth(client_user),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"tenant_id": created["id"], "role": "owner"}

    me = (await client.get("/api/v1/tenants/me", headers=auth(client_user, created["id"]))).json()
    assert me["role"] == "owner"
    assert me["features"] == {"projects": True, "contacts": True}

    # The operator holds no membership in the workspace they created.
    resp = await client.get("/api/v1/tenants/me", headers=auth(operator, created["id"]))
    assert resp.status_code == 403

    members = (await client.get("/api/v1/members", headers=auth(client_user, created["id"]))).json()
    assert [m["role"] for m in members] == ["owner"]


async def test_admin_reissues_owner_invite(client, two_tenants):
    a, _ = two_tenants
    operator = uuid4()
    resp = await client.post(
        f"/api/v1/admin/tenants/{a.id}/owner-invite",
        json={"email": "handover@example.com"},
        headers=admin_auth(operator),
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["role"] == "owner"

    resp = await client.post(
        f"/api/v1/admin/tenants/{uuid4()}/owner-invite",
        json={"email": "x@example.com"},
        headers=admin_auth(operator),
    )
    assert resp.status_code == 404


async def test_tenant_admins_still_cannot_invite_owners(client, two_tenants):
    """The owner role is only issuable from the operator console — the
    tenant-facing invite schema keeps its admin|member cap."""
    a, _ = two_tenants
    resp = await client.post(
        "/api/v1/invites",
        json={"email": "x@example.com", "role": "owner"},
        headers=auth(a.owner_id, a.id),
    )
    assert resp.status_code == 422


# -- fleet listing -----------------------------------------------------------


async def test_admin_lists_all_tenants_with_usage(client, two_tenants):
    a, b = two_tenants
    resp = await client.get("/api/v1/admin/tenants", headers=admin_auth(uuid4()))
    assert resp.status_code == 200, resp.text
    rows = {r["id"]: r for r in resp.json()}
    assert {str(a.id), str(b.id)} <= set(rows)
    for tenant in (a, b):
        row = rows[str(tenant.id)]
        assert row["member_count"] == 1
        assert row["pending_invites"] == 1
        assert row["month_requests"] == 1  # the seeded chat usage event


# -- invite-only signup ------------------------------------------------------


async def test_closed_signup_blocks_self_serve(client, monkeypatch):
    monkeypatch.setenv("OPEN_SIGNUP", "false")
    get_settings.cache_clear()
    try:
        resp = await client.post("/api/v1/tenants", json={"name": "walk-in"}, headers=auth(uuid4()))
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "signup_closed"

        # The platform admin can still create workspaces directly.
        resp = await client.post(
            "/api/v1/tenants", json={"name": "operator-made"}, headers=admin_auth(uuid4())
        )
        assert resp.status_code == 201, resp.text
    finally:
        monkeypatch.setenv("OPEN_SIGNUP", "true")
        get_settings.cache_clear()
