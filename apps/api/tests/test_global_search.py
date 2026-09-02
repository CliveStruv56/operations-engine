"""Workspace search (⌘K): title matching, tenant + per-user scoping."""

from uuid import uuid4

from app.db import db
from tests.conftest import auth, seed_tenant


async def test_search_matches_conversation_and_document_titles(client, two_tenants):
    a, _ = two_tenants
    resp = await client.get(
        "/api/v1/search", params={"q": "handbook"}, headers=auth(a.owner_id, a.id)
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert [d["id"] for d in body["documents"]] == [str(a.document_id)]
    assert body["conversations"] == []

    resp = await client.get("/api/v1/search", params={"q": "CHAT"}, headers=auth(a.owner_id, a.id))
    assert resp.status_code == 200
    body = resp.json()
    assert [c["id"] for c in body["conversations"]] == [str(a.conversation_id)]


async def test_search_is_tenant_scoped(client, two_tenants):
    """Both tenants seed a '<name> handbook' document; each caller sees only
    their own tenant's."""
    a, b = two_tenants
    for tenant, other in ((a, b), (b, a)):
        resp = await client.get(
            "/api/v1/search",
            params={"q": "handbook"},
            headers=auth(tenant.owner_id, tenant.id),
        )
        assert resp.status_code == 200
        ids = {d["id"] for d in resp.json()["documents"]}
        assert str(tenant.document_id) in ids
        assert str(other.document_id) not in ids


async def test_search_conversations_are_personal(client, two_tenants):
    """Conversations match GET /conversations semantics: own + shared within
    the tenant — never another tenant's."""
    a, b = two_tenants
    resp = await client.get("/api/v1/search", params={"q": "chat"}, headers=auth(b.owner_id, b.id))
    assert resp.status_code == 200
    ids = {c["id"] for c in resp.json()["conversations"]}
    assert ids == {str(b.conversation_id)}


async def test_search_finds_shared_but_not_private_peer_chats(client):
    """A member finds a teammate's shared chat by title, never a private one."""
    tenant = await seed_tenant(client, f"searchshare-{uuid4().hex[:6]}")
    owner_headers = auth(tenant.owner_id, tenant.id)
    invite = (
        await client.post(
            "/api/v1/invites",
            json={"email": "peer@example.com", "role": "member"},
            headers=owner_headers,
        )
    ).json()
    peer_id = uuid4()
    resp = await client.post(
        "/api/v1/invites/accept",
        json={"token": invite["token"]},
        headers=auth(peer_id, email="peer@example.com"),
    )
    assert resp.status_code == 200
    peer_headers = auth(peer_id, tenant.id)

    # Private: invisible to the peer's search.
    resp = await client.get("/api/v1/search", params={"q": "chat"}, headers=peer_headers)
    assert resp.status_code == 200
    assert resp.json()["conversations"] == []

    resp = await client.patch(
        f"/api/v1/conversations/{tenant.conversation_id}",
        json={"visibility": "tenant"},
        headers=owner_headers,
    )
    assert resp.status_code == 200

    resp = await client.get("/api/v1/search", params={"q": "chat"}, headers=peer_headers)
    assert resp.status_code == 200
    rows = resp.json()["conversations"]
    assert [c["id"] for c in rows] == [str(tenant.conversation_id)]
    assert rows[0]["is_mine"] is False
    assert rows[0]["owner_email"] == "user@example.com"


async def test_search_escapes_like_wildcards(client, two_tenants):
    a, _ = two_tenants
    resp = await client.get("/api/v1/search", params={"q": "%"}, headers=auth(a.owner_id, a.id))
    assert resp.status_code == 200
    assert resp.json() == {"conversations": [], "documents": [], "contacts": []}


async def test_search_contacts_only_when_flag_on(client, two_tenants):
    """The seeded contact surfaces in ⌘K only once the CRM flag is enabled,
    and never crosses tenants."""
    a, b = two_tenants

    # Flag off (seed default): the seeded contact exists but stays out.
    resp = await client.get(
        "/api/v1/search", params={"q": "contact"}, headers=auth(a.owner_id, a.id)
    )
    assert resp.status_code == 200
    assert resp.json()["contacts"] == []

    async with db.tenant_tx(a.owner_id, a.id) as conn:
        await conn.execute(
            """update tenants set features = features || '{"contacts": true}' where id = $1""",
            a.id,
        )
    resp = await client.get(
        "/api/v1/search", params={"q": "contact"}, headers=auth(a.owner_id, a.id)
    )
    assert resp.status_code == 200
    hits = resp.json()["contacts"]
    assert [h["id"] for h in hits] == [str(a.contact_id)]
    assert hits[0]["company_name"] is not None
    assert str(b.contact_id) not in {h["id"] for h in hits}

    # Company-name matches surface the company's people too.
    resp = await client.get("/api/v1/search", params={"q": "ltd"}, headers=auth(a.owner_id, a.id))
    assert [h["id"] for h in resp.json()["contacts"]] == [str(a.contact_id)]


async def test_search_requires_query(client, two_tenants):
    a, _ = two_tenants
    resp = await client.get("/api/v1/search", headers=auth(a.owner_id, a.id))
    assert resp.status_code == 422
    resp = await client.get("/api/v1/search", params={"q": ""}, headers=auth(a.owner_id, a.id))
    assert resp.status_code == 422
