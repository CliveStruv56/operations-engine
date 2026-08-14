"""Operator console: platform-admin gate, on-behalf tenant creation with
owner handover, fleet listing, and the invite-only signup switch."""

from uuid import uuid4

from app.config import get_settings
from app.db import db
from app.litellm import litellm_client
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
        ("PATCH", f"/api/v1/admin/tenants/{a.id}/features", {"features": {"contacts": True}}),
        ("PATCH", f"/api/v1/admin/tenants/{a.id}", {"name": "X"}),
        ("POST", f"/api/v1/admin/tenants/{a.id}/suspend", {"reason": "x"}),
        ("POST", f"/api/v1/admin/tenants/{a.id}/resume", None),
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


# -- module entitlements -----------------------------------------------------


async def test_admin_enables_a_module_on_a_live_workspace(client, two_tenants):
    """Selling a module to an existing client: the flag flips and its routes
    come alive, without touching the database by hand."""
    a, _ = two_tenants
    headers = auth(a.owner_id, a.id)

    # Contacts is off for the seeded tenant, so the CRM router is invisible.
    assert (await client.get("/api/v1/contacts", headers=headers)).status_code == 404

    resp = await client.patch(
        f"/api/v1/admin/tenants/{a.id}/features",
        json={"features": {"contacts": True}},
        headers=admin_auth(uuid4()),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["features"]["contacts"] is True

    assert (await client.get("/api/v1/contacts", headers=headers)).status_code == 200
    me = (await client.get("/api/v1/tenants/me", headers=headers)).json()
    assert me["features"]["contacts"] is True


async def test_features_patch_merges_and_can_withdraw_a_module(client, two_tenants):
    """Naming one module must not disturb another, and false withdraws
    access without deleting anything."""
    a, _ = two_tenants
    operator = admin_auth(uuid4())

    await client.patch(
        f"/api/v1/admin/tenants/{a.id}/features",
        json={"features": {"contacts": True, "projects": True}},
        headers=operator,
    )
    resp = await client.patch(
        f"/api/v1/admin/tenants/{a.id}/features",
        json={"features": {"web_search": True}},
        headers=operator,
    )
    assert resp.json()["features"] == {"contacts": True, "projects": True, "web_search": True}

    resp = await client.patch(
        f"/api/v1/admin/tenants/{a.id}/features",
        json={"features": {"contacts": False}},
        headers=operator,
    )
    assert resp.json()["features"]["contacts"] is False
    assert resp.json()["features"]["projects"] is True  # untouched
    headers = auth(a.owner_id, a.id)
    assert (await client.get("/api/v1/contacts", headers=headers)).status_code == 404


async def test_features_patch_rejects_unknown_flags_and_missing_workspaces(client, two_tenants):
    a, _ = two_tenants
    operator = admin_auth(uuid4())

    resp = await client.patch(
        f"/api/v1/admin/tenants/{a.id}/features",
        json={"features": {"contatcs": True}},  # typo would otherwise persist silently
        headers=operator,
    )
    assert resp.status_code == 422

    resp = await client.patch(
        f"/api/v1/admin/tenants/{a.id}/features", json={"features": {}}, headers=operator
    )
    assert resp.status_code == 422

    resp = await client.patch(
        f"/api/v1/admin/tenants/{uuid4()}/features",
        json={"features": {"contacts": True}},
        headers=operator,
    )
    assert resp.status_code == 404


async def test_features_change_is_audited_and_surfaces_to_the_team(client, two_tenants):
    a, _ = two_tenants
    await client.patch(
        f"/api/v1/admin/tenants/{a.id}/features",
        json={"features": {"contacts": True}},
        headers=admin_auth(uuid4()),
    )
    feed = (await client.get("/api/v1/activity", headers=auth(a.owner_id, a.id))).json()
    entry = next(i for i in feed if i["action"] == "tenant.features_change")
    assert entry["meta"]["changed"] == {"contacts": True}


# -- editing a live workspace ------------------------------------------------


async def test_admin_edits_workspace_fields(client, two_tenants):
    """Name, seats, trial end, plan and accent were all create-only; each of
    them had to be reachable without touching SQL."""
    a, _ = two_tenants
    operator = admin_auth(uuid4())

    resp = await client.patch(
        f"/api/v1/admin/tenants/{a.id}",
        json={
            "name": "Willow Housing Ltd",
            "seats": 12,
            "plan": "pro",
            "trial_ends_at": "2026-12-31T00:00:00Z",
            "brand_accent": "#1f6d53",
        },
        headers=operator,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["name"] == "Willow Housing Ltd"
    assert body["seats"] == 12
    assert body["plan"] == "pro"
    assert body["trial_ends_at"].startswith("2026-12-31")
    assert body["brand"]["accent"] == "#1f6d53"

    # Seats drive the gateway's fair-use ceiling, so the budget moves with them.
    async with db.tenant_tx(a.owner_id, a.id) as conn:
        budget = await conn.fetchval("select soft_budget_usd from tenants where id = $1", a.id)
    assert float(budget) == 12 * get_settings().default_soft_budget_per_seat_usd


async def test_seat_change_resyncs_the_gateway_key_budget(client, two_tenants, monkeypatch):
    """soft_budget_usd used to move with seats while the virtual key kept
    enforcing its creation-time max_budget."""
    a, _ = two_tenants
    # Empty LITELLM_KEY_ENCRYPTION_KEY in tests means pass-through storage.
    async with db.tenant_tx(a.owner_id, a.id) as conn:
        await conn.execute(
            "update tenants set litellm_key_encrypted = 'sk-tenant-test' where id = $1", a.id
        )

    calls: list[tuple[str, float]] = []

    async def record(key: str, soft_budget_usd: float) -> None:
        calls.append((key, soft_budget_usd))

    monkeypatch.setattr(litellm_client, "update_key_budget", record)
    resp = await client.patch(
        f"/api/v1/admin/tenants/{a.id}", json={"seats": 7}, headers=admin_auth(uuid4())
    )
    assert resp.status_code == 200, resp.text
    assert calls == [("sk-tenant-test", 7 * get_settings().default_soft_budget_per_seat_usd)]

    # A name-only edit touches no budget and must not call the gateway.
    calls.clear()
    resp = await client.patch(
        f"/api/v1/admin/tenants/{a.id}", json={"name": "Same seats"}, headers=admin_auth(uuid4())
    )
    assert resp.status_code == 200, resp.text
    assert calls == []


async def test_workspace_patch_is_partial_and_validated(client, two_tenants):
    """Sending one field must not reset the others."""
    a, _ = two_tenants
    operator = admin_auth(uuid4())

    await client.patch(
        f"/api/v1/admin/tenants/{a.id}",
        json={"name": "Original", "seats": 9, "brand_accent": "#112233"},
        headers=operator,
    )
    resp = await client.patch(
        f"/api/v1/admin/tenants/{a.id}", json={"name": "Renamed"}, headers=operator
    )
    body = resp.json()
    assert body["name"] == "Renamed"
    assert body["seats"] == 9  # untouched
    assert body["brand"]["accent"] == "#112233"  # untouched

    for payload, code in [
        ({}, 400),  # nothing to do
        ({"plan": "enterprise"}, 422),  # not a known plan
        ({"seats": 0}, 422),
        ({"brand_accent": "red"}, 422),
    ]:
        r = await client.patch(f"/api/v1/admin/tenants/{a.id}", json=payload, headers=operator)
        assert r.status_code == code, f"{payload} -> {r.status_code}"

    r = await client.patch(
        f"/api/v1/admin/tenants/{uuid4()}", json={"name": "ghost"}, headers=operator
    )
    assert r.status_code == 404


# -- suspend / resume --------------------------------------------------------


async def test_suspend_takes_the_workspace_dark_and_resume_restores_it(client, two_tenants):
    """Suspension is enforced at tenant resolution, so it covers every
    tenant-scoped route — including chat, which is where spend happens."""
    a, b = two_tenants
    operator = admin_auth(uuid4())
    member = auth(a.owner_id, a.id)

    assert (await client.get("/api/v1/tenants/me", headers=member)).status_code == 200

    resp = await client.post(
        f"/api/v1/admin/tenants/{a.id}/suspend",
        json={"reason": "Trial lapsed, awaiting payment"},
        headers=operator,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["suspended_at"] is not None
    assert resp.json()["suspended_reason"] == "Trial lapsed, awaiting payment"

    for method, path in [
        ("GET", "/api/v1/tenants/me"),
        ("GET", "/api/v1/conversations"),
        ("GET", "/api/v1/documents"),
        ("POST", "/api/v1/conversations"),
    ]:
        r = await client.request(method, path, headers=member, json={})
        assert r.status_code == 403, f"{method} {path} -> {r.status_code}"
        assert r.json()["error"]["code"] == "tenant_suspended"

    # The other tenant is unaffected.
    assert (
        await client.get("/api/v1/tenants/me", headers=auth(b.owner_id, b.id))
    ).status_code == 200

    resp = await client.post(f"/api/v1/admin/tenants/{a.id}/resume", headers=operator)
    assert resp.status_code == 200
    assert resp.json()["suspended_at"] is None
    assert (await client.get("/api/v1/tenants/me", headers=member)).status_code == 200


async def test_suspension_needs_a_reason_and_resume_is_idempotent(client, two_tenants):
    a, _ = two_tenants
    operator = admin_auth(uuid4())

    r = await client.post(f"/api/v1/admin/tenants/{a.id}/suspend", json={}, headers=operator)
    assert r.status_code == 422
    r = await client.post(
        f"/api/v1/admin/tenants/{a.id}/suspend", json={"reason": "  "}, headers=operator
    )
    assert r.status_code in (200, 422)  # whitespace-only is accepted or rejected, never a 500

    # Resuming a workspace that was never suspended is a no-op, not an error.
    r = await client.post(f"/api/v1/admin/tenants/{a.id}/resume", headers=operator)
    assert r.status_code == 200
    r = await client.post(f"/api/v1/admin/tenants/{a.id}/resume", headers=operator)
    assert r.status_code == 200
    assert r.json()["suspended_at"] is None

    r = await client.post(
        f"/api/v1/admin/tenants/{uuid4()}/suspend", json={"reason": "x"}, headers=operator
    )
    assert r.status_code == 404


async def test_suspended_workspace_is_still_visible_and_editable_to_the_operator(
    client, two_tenants
):
    """The console must not lose control of a workspace it just suspended."""
    a, _ = two_tenants
    operator = admin_auth(uuid4())
    await client.post(
        f"/api/v1/admin/tenants/{a.id}/suspend", json={"reason": "nonpayment"}, headers=operator
    )

    listing = (await client.get("/api/v1/admin/tenants", headers=operator)).json()
    rows = {r["id"]: r for r in listing}
    assert rows[str(a.id)]["suspended_reason"] == "nonpayment"

    r = await client.patch(f"/api/v1/admin/tenants/{a.id}", json={"seats": 4}, headers=operator)
    assert r.status_code == 200, "operator must still be able to edit a suspended workspace"


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
