"""Community module: feature flag, profile upsert, asset CRUD and filters,
statistics feeding the claims register, and cross-tenant direct-object-
reference attacks with the flag enabled (the isolation suite's community
routes are gated, so its DOR checks would pass trivially there).

SQL-level RLS for the community_* tables is covered by test_isolation.py
(TENANT_TABLES); this file exercises the API surface.
"""

from uuid import UUID, uuid4

import pytest

from app.db import db
from app.litellm import StreamResult, litellm_client
from app.queue import ingest_queue
from app.storage import Storage, storage
from tests.conftest import Tenant, auth, seed_tenant
from tests.test_chat import parse_sse


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


# -- chat lookup -------------------------------------------------------------


@pytest.fixture
def capture_llm(monkeypatch):
    """Stub stream_chat, recording the system prompt of each call."""
    prompts: list[str] = []

    async def _fake(virtual_key, alias, messages, result: StreamResult):
        prompts.append(messages[0]["content"])
        result.text_parts.append("ok")
        yield "ok"
        result.tokens_in = 10
        result.tokens_out = 5

    monkeypatch.setattr(litellm_client, "stream_chat", _fake)

    async def _fake_embed(virtual_key, text):
        return [0.0] * 2048, 7

    monkeypatch.setattr(litellm_client, "embed_query", _fake_embed)
    return prompts


async def _chat_ready_tenant(client, name: str, community: bool = True) -> Tenant:
    t = await seed_tenant(client, name)
    if community:
        await enable_community(t)
    async with db.tenant_tx(t.owner_id, t.id) as conn:
        await conn.execute(
            "update tenants set litellm_key_encrypted = 'sk-test-virtual' where id = $1", t.id
        )
    return t


async def _say(client, tenant: Tenant, content: str) -> None:
    headers = auth(tenant.owner_id, tenant.id)
    conv = (await client.post("/api/v1/conversations", json={"title": "t"}, headers=headers)).json()
    resp = await client.post(
        f"/api/v1/conversations/{conv['id']}/messages",
        json={"content": content, "use_vault": False},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text


async def test_chat_injects_matching_figure(client, capture_llm):
    t = await _chat_ready_tenant(client, f"commchat-{uuid4().hex[:6]}")
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
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text

    await _say(client, t, "How many households are there on the island?")
    system = capture_llm[-1]
    assert "<community-profile>" in system
    assert "Households: 240 households (2022 — Scotland's Census 2022)" in system

    # An unrelated question must not carry the place along.
    await _say(client, t, "Summarise our leave policy")
    assert "<community-profile>" not in capture_llm[-1]


async def test_chat_matches_a_category_question(client, capture_llm):
    """ "Is there a shop?" asks about a kind of thing, not a named one."""
    t = await _chat_ready_tenant(client, f"commchatcat-{uuid4().hex[:6]}")
    headers = auth(t.owner_id, t.id)
    resp = await client.post(
        "/api/v1/community/assets",
        json={
            "category": "retail_services",
            "subcategory": "general store",
            "name": "Sinclair General Stores",
            "attributes": {"post_office": True, "fuel": True},
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text

    await _say(client, t, "Is there a shop where I can buy groceries?")
    system = capture_llm[-1]
    assert "Sinclair General Stores" in system
    assert "post office: yes" in system


async def test_chat_matches_the_profile_description(client, capture_llm):
    """Prose in the profile answers before anything is typed in as a facility.

    A trust writes "we have a school, two shops and a pub" into the
    description on day one; a question about the pub must surface that
    sentence rather than silence, even though no facility row matches."""
    t = await _chat_ready_tenant(client, f"commchatdesc-{uuid4().hex[:6]}")
    headers = auth(t.owner_id, t.id)
    resp = await client.put(
        "/api/v1/community/profile",
        json={
            "place_name": "Sanday",
            "description": "We have a school, two shops, a pub and a Heritage Centre.",
        },
        headers=headers,
    )
    assert resp.status_code == 200, resp.text

    await _say(client, t, "Is there a pub on the island?")
    system = capture_llm[-1]
    assert "<community-profile>" in system
    assert "a pub and a Heritage Centre" in system


async def test_chat_lookup_respects_feature_flag(client, capture_llm):
    t = await _chat_ready_tenant(client, f"commchatoff-{uuid4().hex[:6]}", community=False)
    # The seeded stat ("Usual residents") would match, but the flag is off.
    await _say(client, t, "How many usual residents are there?")
    assert "<community-profile>" not in capture_llm[-1]


async def test_records_answer_does_not_offer_vault_recovery(client, capture_llm):
    """A vault-on question answered from the community profile must not tell
    the user their vault "could not back" the answer — the backing lives in a
    register, and "add a document" recovery over a correct figure misleads."""
    t = await _chat_ready_tenant(client, f"commchatcov-{uuid4().hex[:6]}")
    headers = auth(t.owner_id, t.id)

    conv = (await client.post("/api/v1/conversations", json={"title": "t"}, headers=headers)).json()
    # The seeded stat "Usual residents" matches; the empty vault cites nothing.
    resp = await client.post(
        f"/api/v1/conversations/{conv['id']}/messages",
        json={"content": "How many usual residents are there?"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    done = dict(parse_sse(resp.text))["done"]
    assert done["coverage"] == "records"
    assert done["scope_used"] is None

    # No records matched either: the ordinary vault-recovery signal stands.
    resp = await client.post(
        f"/api/v1/conversations/{conv['id']}/messages",
        json={"content": "Summarise our leave policy"},
        headers=headers,
    )
    done = dict(parse_sse(resp.text))["done"]
    assert done["coverage"] == "none"


# -- profile PDF export -------------------------------------------------------


def _fake_pdf_infra(monkeypatch):
    enqueued = []

    async def enqueue(tenant_id, job_id, user_id):
        enqueued.append((tenant_id, job_id, user_id))

    monkeypatch.setattr(ingest_queue, "enqueue_community_pdf", enqueue)
    monkeypatch.setattr(Storage, "enabled", property(lambda self: True))
    monkeypatch.setattr(storage, "presign_get", lambda key: f"https://signed.example/{key}")
    return enqueued


async def test_profile_pdf_submit_and_poll(client, monkeypatch):
    t = await seed_tenant(client, f"commpdf-{uuid4().hex[:6]}")
    await enable_community(t)
    headers = auth(t.owner_id, t.id)
    enqueued = _fake_pdf_infra(monkeypatch)

    resp = await client.post("/api/v1/community/profile/pdf", headers=headers)
    assert resp.status_code == 202, resp.text
    job = resp.json()
    assert job["status"] == "queued"
    assert job["kind"] == "profile_pdf"
    assert job["download_url"] is None
    assert [str(j[1]) for j in enqueued] == [job["id"]]

    # A second click while the first is in flight reuses the job.
    resp = await client.post("/api/v1/community/profile/pdf", headers=headers)
    assert resp.status_code == 202
    assert resp.json()["id"] == job["id"]
    assert len(enqueued) == 1

    # The worker lands the file; the poll then carries the signed URL.
    file_key = f"{t.id}/community/exports/{job['id']}.pdf"
    async with db.tenant_tx(t.owner_id, t.id) as conn:
        await conn.execute(
            "update community_export_jobs set status = 'succeeded', file_key = $2 where id = $1",
            UUID(job["id"]),
            file_key,
        )
    resp = await client.get(f"/api/v1/community/exports/{job['id']}", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "succeeded"
    assert body["download_url"] == f"https://signed.example/{file_key}"

    resp = await client.get(f"/api/v1/community/exports/{uuid4()}", headers=headers)
    assert resp.status_code == 404


async def test_profile_pdf_requires_a_profile(client, monkeypatch):
    t = await seed_tenant(client, f"commpdfnp-{uuid4().hex[:6]}")
    await enable_community(t)
    _fake_pdf_infra(monkeypatch)
    async with db.tenant_tx(t.owner_id, t.id) as conn:
        await conn.execute("delete from community_profile")
    resp = await client.post("/api/v1/community/profile/pdf", headers=auth(t.owner_id, t.id))
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "no_profile"


async def test_profile_pdf_respects_feature_flag(client, monkeypatch):
    t = await seed_tenant(client, f"commpdfoff-{uuid4().hex[:6]}")
    _fake_pdf_infra(monkeypatch)
    resp = await client.post("/api/v1/community/profile/pdf", headers=auth(t.owner_id, t.id))
    assert resp.status_code == 404
