"""CI-blocking cross-tenant isolation suite (spec §9.1).

Two seeded tenants; every read endpoint is attacked cross-tenant, including
direct-object-reference attacks, and RLS is verified at the SQL level per
table with the runtime (non-owner) role.
"""

from uuid import uuid4

import asyncpg
import pytest

from app.db import db
from tests.conftest import APP_URL, auth

TENANT_TABLES = [
    "memberships",
    "projects",
    "documents",
    "doc_chunks",
    "conversations",
    "messages",
    "usage_events",
    "invites",
    "audit_log",
]


async def test_cross_tenant_header_rejected(client, two_tenants):
    """A's token with B's tenant id must be rejected on every endpoint."""
    a, b = two_tenants
    attacks = [
        ("GET", "/api/v1/tenants/me"),
        ("GET", "/api/v1/members"),
        ("PATCH", "/api/v1/tenants/me"),
        ("POST", "/api/v1/invites"),
        ("DELETE", f"/api/v1/members/{b.membership_id}"),
        ("PATCH", f"/api/v1/members/{b.membership_id}"),
        ("GET", "/api/v1/conversations"),
        ("POST", "/api/v1/conversations"),
        ("GET", f"/api/v1/conversations/{b.conversation_id}/messages"),
        ("DELETE", f"/api/v1/conversations/{b.conversation_id}"),
        ("PATCH", f"/api/v1/conversations/{b.conversation_id}"),
        ("POST", f"/api/v1/conversations/{b.conversation_id}/messages"),
        ("GET", "/api/v1/usage/summary"),
        ("GET", "/api/v1/documents"),
        ("POST", "/api/v1/documents"),
        ("GET", f"/api/v1/documents/{b.document_id}"),
        ("POST", f"/api/v1/documents/{b.document_id}/complete"),
        ("POST", f"/api/v1/documents/{b.document_id}/reprocess"),
        ("DELETE", f"/api/v1/documents/{b.document_id}"),
    ]
    for method, path in attacks:
        resp = await client.request(method, path, headers=auth(a.owner_id, b.id), json={})
        assert resp.status_code == 403, f"{method} {path} -> {resp.status_code}"
        assert resp.json()["error"]["code"] == "not_a_member"


async def test_direct_object_reference_attacks(client, two_tenants):
    """B's object ids under A's legitimate tenant context must 404."""
    a, b = two_tenants
    headers = auth(a.owner_id, a.id)

    resp = await client.delete(f"/api/v1/members/{b.membership_id}", headers=headers)
    assert resp.status_code == 404

    resp = await client.patch(
        f"/api/v1/members/{b.membership_id}", json={"role": "member"}, headers=headers
    )
    assert resp.status_code == 404

    members = (await client.get("/api/v1/members", headers=headers)).json()
    listed_ids = {m["id"] for m in members}
    assert str(b.membership_id) not in listed_ids
    assert str(a.membership_id) in listed_ids

    # Chat: B's conversation id under A's context must 404 on every verb.
    resp = await client.get(f"/api/v1/conversations/{b.conversation_id}/messages", headers=headers)
    assert resp.status_code == 404
    resp = await client.post(
        f"/api/v1/conversations/{b.conversation_id}/messages",
        json={"content": "hi"},
        headers=headers,
    )
    assert resp.status_code == 404
    resp = await client.delete(f"/api/v1/conversations/{b.conversation_id}", headers=headers)
    assert resp.status_code == 404

    convs = (await client.get("/api/v1/conversations", headers=headers)).json()
    assert str(b.conversation_id) not in {c["id"] for c in convs}

    # Vault: B's document id under A's context must 404 on every verb.
    for method, path in [
        ("GET", f"/api/v1/documents/{b.document_id}"),
        ("POST", f"/api/v1/documents/{b.document_id}/complete"),
        ("POST", f"/api/v1/documents/{b.document_id}/reprocess"),
        ("DELETE", f"/api/v1/documents/{b.document_id}"),
    ]:
        resp = await client.request(method, path, headers=headers)
        assert resp.status_code == 404, f"{method} {path} -> {resp.status_code}"

    docs = (await client.get("/api/v1/documents", headers=headers)).json()
    assert str(b.document_id) not in {d["id"] for d in docs}


async def test_shared_conversation_does_not_cross_tenants(client, two_tenants):
    """Sharing widens visibility within the tenant only — a chat shared in B
    stays invisible to A (RLS is the outer boundary)."""
    a, b = two_tenants
    async with db.tenant_tx(b.owner_id, b.id) as conn:
        await conn.execute(
            "update conversations set visibility = 'tenant' where id = $1",
            b.conversation_id,
        )
    headers = auth(a.owner_id, a.id)
    convs = (await client.get("/api/v1/conversations", headers=headers)).json()
    assert str(b.conversation_id) not in {c["id"] for c in convs}
    resp = await client.get(f"/api/v1/conversations/{b.conversation_id}/messages", headers=headers)
    assert resp.status_code == 404


async def test_usage_summary_is_tenant_scoped(client, two_tenants):
    """Each seeded tenant has exactly one usage event (10 in / 20 out); a
    tenant's summary must never include the other's tokens."""
    a, b = two_tenants
    for tenant in (a, b):
        resp = await client.get("/api/v1/usage/summary", headers=auth(tenant.owner_id, tenant.id))
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["tokens_in"] == 10
        assert body["tokens_out"] == 20
        assert body["requests"] == 1
        assert [u["key"] for u in body["by_user"]] == [str(tenant.owner_id)]


async def test_cross_tenant_invite_token_is_single_use_and_scoped(client, two_tenants):
    a, b = two_tenants
    outsider = uuid4()
    resp = await client.post(
        "/api/v1/invites/accept", json={"token": b.invite_token}, headers=auth(outsider)
    )
    assert resp.status_code == 200
    assert resp.json()["tenant_id"] == str(b.id)

    # The accepted member of B still cannot touch A.
    resp = await client.get("/api/v1/tenants/me", headers=auth(outsider, a.id))
    assert resp.status_code == 403

    # Token cannot be replayed.
    resp = await client.post(
        "/api/v1/invites/accept", json={"token": b.invite_token}, headers=auth(uuid4())
    )
    assert resp.status_code == 400


async def test_sql_level_rls_per_table(two_tenants):
    """With the runtime role: tenant A context sees only A rows in every
    tenant-scoped table; no context sees zero rows."""
    a, b = two_tenants
    conn = await asyncpg.connect(APP_URL)
    try:
        role_info = await conn.fetchrow(
            "select current_user, rolbypassrls from pg_roles where rolname = current_user"
        )
        assert role_info["current_user"] == "ops_app"
        assert role_info["rolbypassrls"] is False, "runtime role must not bypass RLS"

        for table in TENANT_TABLES + ["tenants"]:
            count = await conn.fetchval(f"select count(*) from {table}")
            assert count == 0, f"{table}: no context must see zero rows, saw {count}"

        async with conn.transaction():
            await conn.execute(
                "select set_config('app.current_user', $1, true),"
                " set_config('app.current_tenant', $2, true)",
                str(a.owner_id),
                str(a.id),
            )
            for table in TENANT_TABLES:
                leaked = await conn.fetchval(
                    f"select count(*) from {table} where tenant_id <> $1", a.id
                )
                assert leaked == 0, f"{table}: tenant A context leaked {leaked} foreign rows"
                mine = await conn.fetchval(
                    f"select count(*) from {table} where tenant_id = $1", a.id
                )
                assert mine > 0, f"{table}: tenant A context sees none of its own rows"
            visible_tenants = await conn.fetch("select id from tenants")
            assert {r["id"] for r in visible_tenants} == {a.id}
    finally:
        await conn.close()


async def test_sql_level_rls_blocks_cross_tenant_writes(two_tenants):
    """Under tenant A context, inserting or updating rows tagged for tenant B
    must be rejected by policy, not app code."""
    a, b = two_tenants
    conn = await asyncpg.connect(APP_URL)
    try:
        async with conn.transaction():
            await conn.execute(
                "select set_config('app.current_user', $1, true),"
                " set_config('app.current_tenant', $2, true)",
                str(a.owner_id),
                str(a.id),
            )
            with pytest.raises(asyncpg.InsufficientPrivilegeError):
                await conn.execute(
                    "insert into documents (tenant_id, title) values ($1, 'smuggled')",
                    b.id,
                )
        async with conn.transaction():
            await conn.execute(
                "select set_config('app.current_user', $1, true),"
                " set_config('app.current_tenant', $2, true)",
                str(a.owner_id),
                str(a.id),
            )
            # Update of B's rows silently matches nothing (filtered by USING).
            result = await conn.execute(
                "update documents set title = 'defaced' where tenant_id = $1", b.id
            )
            assert result == "UPDATE 0"
            deleted = await conn.execute("delete from doc_chunks where tenant_id = $1", b.id)
            assert deleted == "DELETE 0"
    finally:
        await conn.close()


async def test_membership_visibility_requires_user_context(two_tenants):
    a, _ = two_tenants
    conn = await asyncpg.connect(APP_URL)
    try:
        async with conn.transaction():
            # user context only (pre-tenant resolution): own memberships visible
            await conn.execute("select set_config('app.current_user', $1, true)", str(a.owner_id))
            rows = await conn.fetch("select tenant_id from memberships")
            assert {r["tenant_id"] for r in rows} == {a.id}
    finally:
        await conn.close()
