"""Community module: feature flag, profile upsert, asset CRUD and filters,
statistics feeding the claims register, and cross-tenant direct-object-
reference attacks with the flag enabled (the isolation suite's community
routes are gated, so its DOR checks would pass trivially there).

SQL-level RLS for the community_* tables is covered by test_isolation.py
(TENANT_TABLES); this file exercises the API surface.
"""

from uuid import uuid4

from app.db import db
from tests.conftest import Tenant, auth, seed_tenant


async def enable_community(tenant: Tenant) -> None:
    async with db.tenant_tx(tenant.owner_id, tenant.id) as conn:
        await conn.execute(
            """update tenants set features = features || '{"community": true}' where id = $1""",
            tenant.id,
        )


# -- feature flag ------------------------------------------------------------


async def test_flag_off_hides_module(client):
    t = await seed_tenant(client, f"commoff-{uuid4().hex[:6]}")
    headers = auth(t.owner_id, t.id)
    assert (await client.get("/api/v1/community/profile", headers=headers)).status_code == 404
    assert (await client.get("/api/v1/community/assets", headers=headers)).status_code == 404
    resp = await client.post(
        "/api/v1/community/statistics",
        json={"label": "Usual residents", "value": 494},
        headers=headers,
    )
    assert resp.status_code == 404


# -- profile -----------------------------------------------------------------


async def test_profile_upsert(client):
    t = await seed_tenant(client, f"comm-{uuid4().hex[:6]}")
    await enable_community(t)
    headers = auth(t.owner_id, t.id)

    # The fixture seeds a profile row, so the first PUT is already an update.
    resp = await client.get("/api/v1/community/profile", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["place_name"].endswith("island")

    body = {
        "place_name": "Sanday",
        "council_area": "Orkney Islands Council",
        "settlements": ["Lady Village", "Kettletoft"],
        "description": "The largest of Orkney's north isles.",
    }
    resp = await client.put("/api/v1/community/profile", json=body, headers=headers)
    assert resp.status_code == 200, resp.text
    first_id = resp.json()["id"]

    # A second PUT updates the same row rather than growing a second profile.
    body["description"] = "The largest of the north isles, famous for its beaches."
    resp = await client.put("/api/v1/community/profile", json=body, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == first_id
    assert resp.json()["description"] == body["description"]
    assert resp.json()["settlements"] == ["Lady Village", "Kettletoft"]


# -- assets ------------------------------------------------------------------


async def test_asset_crud_and_filters(client):
    t = await seed_tenant(client, f"comm-{uuid4().hex[:6]}")
    await enable_community(t)
    headers = auth(t.owner_id, t.id)

    resp = await client.post(
        "/api/v1/community/assets",
        json={
            "category": "education",
            "subcategory": "primary_secondary",
            "name": "Sanday Community School",
            "attributes": {"pupils": 68, "ages": "3-18", "nursery": True},
            "settlement": "Lady Village",
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    school = resp.json()
    assert school["attributes"] == {"pupils": 68, "ages": "3-18", "nursery": True}

    resp = await client.post(
        "/api/v1/community/assets",
        json={"category": "transport", "name": "Loganair island flights", "status": "seasonal"},
        headers=headers,
    )
    assert resp.status_code == 201

    listed = (
        await client.get("/api/v1/community/assets?category=education", headers=headers)
    ).json()
    assert {a["name"] for a in listed} >= {"Sanday Community School"}
    assert all(a["category"] == "education" for a in listed)

    listed = (await client.get("/api/v1/community/assets?q=loganair", headers=headers)).json()
    assert [a["name"] for a in listed] == ["Loganair island flights"]

    resp = await client.patch(
        f"/api/v1/community/assets/{school['id']}",
        json={"attributes": {"pupils": 71, "ages": "3-18", "nursery": True}},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["attributes"]["pupils"] == 71

    resp = await client.delete(f"/api/v1/community/assets/{school['id']}", headers=headers)
    assert resp.status_code == 204
    resp = await client.get(f"/api/v1/community/assets/{school['id']}", headers=headers)
    assert resp.status_code == 404


# -- statistics and the claims feed ------------------------------------------


async def test_stat_with_claim_kind_feeds_register(client):
    t = await seed_tenant(client, f"comm-{uuid4().hex[:6]}")
    await enable_community(t)
    headers = auth(t.owner_id, t.id)

    resp = await client.post(
        "/api/v1/community/statistics",
        json={
            "label": "Households",
            "value": 240,
            "unit": "households",
            "period": "2022",
            "claim_kind": "community_households",
            "source": "Scotland's Census 2022",
            "source_url": "https://www.scotlandscensus.gov.uk/",
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    stat = resp.json()
    assert stat["claim_id"] is not None

    claim = (await client.get(f"/api/v1/claims/{stat['claim_id']}", headers=headers)).json()
    assert claim["status"] == "confirmed"
    assert claim["source"] == "module"
    assert claim["source_ref"] == "https://www.scotlandscensus.gov.uk/"
    assert claim["period"] == "2022"
    assert claim["statement"] == "The community has 240 households."
    assert claim["category"] == "community"


async def test_stat_update_supersedes_claim(client):
    t = await seed_tenant(client, f"comm-{uuid4().hex[:6]}")
    await enable_community(t)
    headers = auth(t.owner_id, t.id)

    resp = await client.post(
        "/api/v1/community/statistics",
        json={"label": "Population", "value": 494, "claim_kind": "community_population"},
        headers=headers,
    )
    assert resp.status_code == 201
    stat = resp.json()
    old_claim_id = stat["claim_id"]

    resp = await client.patch(
        f"/api/v1/community/statistics/{stat['id']}", json={"value": 510}, headers=headers
    )
    assert resp.status_code == 200
    new_claim_id = resp.json()["claim_id"]
    assert new_claim_id is not None and new_claim_id != old_claim_id

    old = (await client.get(f"/api/v1/claims/{old_claim_id}", headers=headers)).json()
    assert old["status"] == "superseded"
    new = (await client.get(f"/api/v1/claims/{new_claim_id}", headers=headers)).json()
    assert new["status"] == "confirmed"
    assert new["statement"] == "The community has a usual resident population of 510."


async def test_stat_unknown_claim_kind_rejected(client):
    t = await seed_tenant(client, f"comm-{uuid4().hex[:6]}")
    await enable_community(t)
    resp = await client.post(
        "/api/v1/community/statistics",
        json={"label": "Sheep", "value": 9000, "claim_kind": "community_sheep"},
        headers=auth(t.owner_id, t.id),
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "unknown_claim_kind"


async def test_stat_duplicate_claim_identity_rejected(client):
    t = await seed_tenant(client, f"comm-{uuid4().hex[:6]}")
    await enable_community(t)
    headers = auth(t.owner_id, t.id)
    body = {
        "label": "Population",
        "value": 494,
        "period": "2022",
        "claim_kind": "community_population",
    }
    assert (
        await client.post("/api/v1/community/statistics", json=body, headers=headers)
    ).status_code == 201
    resp = await client.post("/api/v1/community/statistics", json=body, headers=headers)
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "duplicate_statistic"


# -- cross-tenant DOR with the flag enabled ----------------------------------


async def test_direct_object_reference_attacks(client, two_tenants):
    """B's community ids under A's context must 404 even with the module on
    for both — the gated isolation-suite checks pass trivially with it off."""
    a, b = two_tenants
    await enable_community(a)
    await enable_community(b)
    headers = auth(a.owner_id, a.id)

    # Each PATCH body names a real field of its schema — an unknown field is
    # dropped by Pydantic and the empty patch 400s before the 404 can fire.
    for method, path, body in [
        ("GET", f"/api/v1/community/assets/{b.community_asset_id}", None),
        ("PATCH", f"/api/v1/community/assets/{b.community_asset_id}", {"name": "mine now"}),
        ("DELETE", f"/api/v1/community/assets/{b.community_asset_id}", None),
        ("PATCH", f"/api/v1/community/statistics/{b.community_stat_id}", {"value": 1}),
        ("DELETE", f"/api/v1/community/statistics/{b.community_stat_id}", None),
    ]:
        resp = await client.request(method, path, headers=headers, json=body)
        assert resp.status_code == 404, f"{method} {path} -> {resp.status_code}"

    assets = (await client.get("/api/v1/community/assets", headers=headers)).json()
    assert str(b.community_asset_id) not in {x["id"] for x in assets}
    assert str(a.community_asset_id) in {x["id"] for x in assets}

    stats = (await client.get("/api/v1/community/statistics", headers=headers)).json()
    assert str(b.community_stat_id) not in {x["id"] for x in stats}
    assert str(a.community_stat_id) in {x["id"] for x in stats}

    # A's profile GET must return A's place, never B's.
    profile = (await client.get("/api/v1/community/profile", headers=headers)).json()
    assert profile["place_name"].startswith("alpha")
