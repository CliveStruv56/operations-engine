"""Tenant activity feed: allowlist enforcement, attribution, tenant scoping."""

from uuid import uuid4

from app.audit import write_audit
from app.db import db
from tests.conftest import auth, seed_tenant


async def test_feed_shows_allowlisted_actions_with_attribution(client):
    tenant = await seed_tenant(client, f"feed-{uuid4().hex[:6]}")
    headers = auth(tenant.owner_id, tenant.id)

    resp = await client.post("/api/v1/projects", json={"name": "Feed project"}, headers=headers)
    assert resp.status_code == 201, resp.text

    resp = await client.get("/api/v1/activity", headers=headers)
    assert resp.status_code == 200, resp.text
    feed = resp.json()
    created = next(i for i in feed if i["action"] == "project.create")
    assert created["actor_email"] == "user@example.com"
    assert created["target_title"] == "Feed project"

    # Private-chat and pre-upload events never surface. The seed flow wrote
    # conversation.create, message rows and a bare document row, and tenant
    # bootstrap wrote tenant.create/invite.create — none belong in the feed.
    actions = {i["action"] for i in feed}
    assert not actions & {
        "conversation.create",
        "conversation.delete",
        "message.create",
        "document.create",
        "tenant.create",
        "invite.create",
    }


async def test_share_event_surfaces_with_title(client):
    tenant = await seed_tenant(client, f"feedshare-{uuid4().hex[:6]}")
    headers = auth(tenant.owner_id, tenant.id)
    resp = await client.patch(
        f"/api/v1/conversations/{tenant.conversation_id}",
        json={"visibility": "tenant"},
        headers=headers,
    )
    assert resp.status_code == 200

    feed = (await client.get("/api/v1/activity", headers=headers)).json()
    shared = next(i for i in feed if i["action"] == "conversation.share")
    assert shared["meta"]["title"].endswith("chat")
    assert shared["actor_email"] == "user@example.com"


async def test_feed_limit_and_order(client):
    tenant = await seed_tenant(client, f"feedlimit-{uuid4().hex[:6]}")
    # One transaction per row: now() is transaction-start time, so a single
    # tx would give every row the same created_at and make ordering arbitrary.
    for n in range(20):
        async with db.tenant_tx(tenant.owner_id, tenant.id) as conn:
            await write_audit(
                conn,
                tenant.id,
                tenant.owner_id,
                "tenant.update",
                "tenant",
                str(tenant.id),
                meta={"n": n},
            )
    feed = (await client.get("/api/v1/activity", headers=auth(tenant.owner_id, tenant.id))).json()
    assert len(feed) == 15
    times = [i["created_at"] for i in feed]
    assert times == sorted(times, reverse=True)
    assert feed[0]["meta"]["n"] == 19


async def test_feed_is_tenant_scoped(client, two_tenants):
    a, b = two_tenants
    resp = await client.post(
        "/api/v1/projects", json={"name": "B secret project"}, headers=auth(b.owner_id, b.id)
    )
    assert resp.status_code == 201

    feed = (await client.get("/api/v1/activity", headers=auth(a.owner_id, a.id))).json()
    assert all(i["target_title"] != "B secret project" for i in feed)
    assert all(i["action"] != "project.create" for i in feed)
