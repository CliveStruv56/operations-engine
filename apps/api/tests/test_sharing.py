"""Conversation visibility: private-by-default (no admin override) and
share-with-team read access."""

import json
from uuid import uuid4

from app.db import db
from tests.conftest import auth, seed_tenant


async def _join(client, tenant, role="member"):
    """Invite + accept a new user into the tenant; returns their user id."""
    resp = await client.post(
        "/api/v1/invites",
        json={"email": f"peer-{uuid4().hex[:6]}@example.com", "role": role},
        headers=auth(tenant.owner_id, tenant.id),
    )
    assert resp.status_code == 201, resp.text
    user_id = uuid4()
    resp = await client.post(
        "/api/v1/invites/accept",
        json={"token": resp.json()["token"]},
        headers=auth(user_id),
    )
    assert resp.status_code == 200, resp.text
    return user_id


async def test_private_chat_hidden_from_admin_and_owner(client):
    """Private means private: elevated roles get 404 like anyone else."""
    tenant = await seed_tenant(client, f"priv-{uuid4().hex[:6]}")
    # Reuse the seeded invite for the member — tenants have 3 seats and the
    # seed already reserves one.
    member_id = uuid4()
    resp = await client.post(
        "/api/v1/invites/accept",
        json={"token": tenant.invite_token},
        headers=auth(member_id),
    )
    assert resp.status_code == 200, resp.text
    admin_id = await _join(client, tenant, role="admin")

    resp = await client.post(
        "/api/v1/conversations",
        json={"title": "member private chat"},
        headers=auth(member_id, tenant.id),
    )
    assert resp.status_code == 201, resp.text
    conv_id = resp.json()["id"]
    assert resp.json()["visibility"] == "private"

    for elevated in (admin_id, tenant.owner_id):
        headers = auth(elevated, tenant.id)
        resp = await client.get(f"/api/v1/conversations/{conv_id}/messages", headers=headers)
        assert resp.status_code == 404
        resp = await client.delete(f"/api/v1/conversations/{conv_id}", headers=headers)
        assert resp.status_code == 404
        convs = (await client.get("/api/v1/conversations", headers=headers)).json()
        assert conv_id not in {c["id"] for c in convs}


async def test_shared_chat_readable_but_not_writable_by_peer(client):
    tenant = await seed_tenant(client, f"share-{uuid4().hex[:6]}")
    peer_id = await _join(client, tenant)
    conv_id = str(tenant.conversation_id)
    owner_headers = auth(tenant.owner_id, tenant.id)
    peer_headers = auth(peer_id, tenant.id)

    resp = await client.patch(
        f"/api/v1/conversations/{conv_id}",
        json={"visibility": "tenant"},
        headers=owner_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["visibility"] == "tenant"

    convs = (await client.get("/api/v1/conversations", headers=peer_headers)).json()
    shared = next(c for c in convs if c["id"] == conv_id)
    assert shared["is_mine"] is False
    assert shared["visibility"] == "tenant"
    assert shared["owner_email"] == "user@example.com"

    # The owner sees it as their own.
    convs = (await client.get("/api/v1/conversations", headers=owner_headers)).json()
    assert next(c for c in convs if c["id"] == conv_id)["is_mine"] is True

    # Peer can read the messages...
    resp = await client.get(f"/api/v1/conversations/{conv_id}/messages", headers=peer_headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 1

    # ...but cannot post, delete, or change visibility.
    resp = await client.post(
        f"/api/v1/conversations/{conv_id}/messages",
        json={"content": "hi"},
        headers=peer_headers,
    )
    assert resp.status_code == 404
    resp = await client.delete(f"/api/v1/conversations/{conv_id}", headers=peer_headers)
    assert resp.status_code == 404
    resp = await client.patch(
        f"/api/v1/conversations/{conv_id}",
        json={"visibility": "private"},
        headers=peer_headers,
    )
    assert resp.status_code == 404


async def test_unshare_revokes_peer_access(client):
    tenant = await seed_tenant(client, f"unshare-{uuid4().hex[:6]}")
    peer_id = await _join(client, tenant)
    conv_id = str(tenant.conversation_id)
    owner_headers = auth(tenant.owner_id, tenant.id)
    peer_headers = auth(peer_id, tenant.id)

    for visibility in ("tenant", "private"):
        resp = await client.patch(
            f"/api/v1/conversations/{conv_id}",
            json={"visibility": visibility},
            headers=owner_headers,
        )
        assert resp.status_code == 200, resp.text

    convs = (await client.get("/api/v1/conversations", headers=peer_headers)).json()
    assert conv_id not in {c["id"] for c in convs}
    resp = await client.get(f"/api/v1/conversations/{conv_id}/messages", headers=peer_headers)
    assert resp.status_code == 404


async def test_share_writes_title_but_unshare_does_not(client):
    tenant = await seed_tenant(client, f"audit-{uuid4().hex[:6]}")
    owner_headers = auth(tenant.owner_id, tenant.id)
    for visibility in ("tenant", "private"):
        resp = await client.patch(
            f"/api/v1/conversations/{tenant.conversation_id}",
            json={"visibility": visibility},
            headers=owner_headers,
        )
        assert resp.status_code == 200

    # A no-op PATCH (already private) must not add an audit row.
    resp = await client.patch(
        f"/api/v1/conversations/{tenant.conversation_id}",
        json={"visibility": "private"},
        headers=owner_headers,
    )
    assert resp.status_code == 200

    async with db.tenant_tx(tenant.owner_id, tenant.id) as conn:
        rows = await conn.fetch(
            "select action, meta from audit_log where target_id = $1"
            " and action in ('conversation.share', 'conversation.unshare')"
            " order by created_at",
            str(tenant.conversation_id),
        )
    assert [r["action"] for r in rows] == ["conversation.share", "conversation.unshare"]
    metas = [r["meta"] if isinstance(r["meta"], dict) else json.loads(r["meta"]) for r in rows]
    assert metas[0]["title"].endswith("chat")
    # Making a chat private again must not carry its title into the audit log:
    # /activity returns meta verbatim to every member of the tenant.
    assert "title" not in metas[1]


async def test_patch_visibility_validates_value(client):
    tenant = await seed_tenant(client, f"val-{uuid4().hex[:6]}")
    resp = await client.patch(
        f"/api/v1/conversations/{tenant.conversation_id}",
        json={"visibility": "public"},
        headers=auth(tenant.owner_id, tenant.id),
    )
    assert resp.status_code == 422
