"""MOD-1: destructive module actions need admin, like core DELETE /projects.

A member keeps everyday editing; deleting a record with no soft delete behind
it, or bulk-overwriting the contact book, takes an admin. A tenant without the
module still sees 404 — the role check never reveals a route the flag hides.
"""

from uuid import uuid4

from app.db import db
from tests.conftest import Tenant, auth, seed_tenant


async def _enable(tenant: Tenant, *flags: str) -> None:
    async with db.tenant_tx(tenant.owner_id, tenant.id) as conn:
        for flag in flags:
            await conn.execute(
                "update tenants set features = features || jsonb_build_object($2::text, true)"
                " where id = $1",
                tenant.id,
                flag,
            )


async def _member(client, tenant: Tenant) -> dict[str, str]:
    member = uuid4()
    r = await client.post(
        "/api/v1/invites/accept", json={"token": tenant.invite_token}, headers=auth(member)
    )
    assert r.status_code == 200, r.text
    return auth(member, tenant.id)


def _destructive(t: Tenant) -> list[tuple[str, str, dict | None]]:
    return [
        ("DELETE", f"/api/v1/grants/applications/{t.application_id}", None),
        ("DELETE", f"/api/v1/grants/funders/{t.funder_id}", None),
        ("DELETE", f"/api/v1/contacts/{t.contact_id}", None),
        ("DELETE", f"/api/v1/companies/{t.company_id}", None),
        ("DELETE", f"/api/v1/community/assets/{t.community_asset_id}", None),
        ("POST", "/api/v1/contacts/import", {"csv": "name,email\nA,a@example.org\n"}),
    ]


async def test_members_cannot_run_destructive_module_actions(client):
    t = await seed_tenant(client, f"modrole-{uuid4().hex[:6]}")
    await _enable(t, "grants", "contacts", "community")
    member = await _member(client, t)

    for method, path, body in _destructive(t):
        r = await client.request(method, path, json=body, headers=member)
        assert r.status_code == 403, f"{method} {path} -> {r.status_code}"
        assert r.json()["error"]["code"] == "insufficient_role"

    # Everyday editing stays open to members.
    r = await client.patch(
        f"/api/v1/contacts/{t.contact_id}", json={"job_title": "Treasurer"}, headers=member
    )
    assert r.status_code == 200, r.text

    # The owner can do every one of them.
    owner = auth(t.owner_id, t.id)
    for method, path, body in _destructive(t):
        r = await client.request(method, path, json=body, headers=owner)
        assert r.status_code in (200, 204), f"{method} {path} -> {r.status_code} {r.text}"


async def test_flag_off_still_404s_before_the_role_check(client):
    t = await seed_tenant(client, f"modoff-{uuid4().hex[:6]}")
    member = await _member(client, t)
    for method, path, body in _destructive(t):
        r = await client.request(method, path, json=body, headers=member)
        assert r.status_code == 404, f"{method} {path} -> {r.status_code}"
