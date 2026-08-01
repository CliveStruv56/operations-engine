"""Workspace search (⌘K): title matching, tenant + per-user scoping."""

from tests.conftest import auth


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
    """Conversations match GET /conversations semantics: only the caller's own."""
    a, b = two_tenants
    resp = await client.get("/api/v1/search", params={"q": "chat"}, headers=auth(b.owner_id, b.id))
    assert resp.status_code == 200
    ids = {c["id"] for c in resp.json()["conversations"]}
    assert ids == {str(b.conversation_id)}


async def test_search_escapes_like_wildcards(client, two_tenants):
    a, _ = two_tenants
    resp = await client.get("/api/v1/search", params={"q": "%"}, headers=auth(a.owner_id, a.id))
    assert resp.status_code == 200
    assert resp.json() == {"conversations": [], "documents": []}


async def test_search_requires_query(client, two_tenants):
    a, _ = two_tenants
    resp = await client.get("/api/v1/search", headers=auth(a.owner_id, a.id))
    assert resp.status_code == 422
    resp = await client.get("/api/v1/search", params={"q": ""}, headers=auth(a.owner_id, a.id))
    assert resp.status_code == 422
