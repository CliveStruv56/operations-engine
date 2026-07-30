"""Slice 4.5: project CRUD + isolation, document partitioning, project-scoped
chat (boosted retrieval + scope_used), and content survival on delete."""

from uuid import uuid4

import pytest

from app.db import db
from app.litellm import litellm_client
from tests.conftest import auth, seed_tenant
from tests.test_chat import enable_llm_key, parse_sse
from tests.test_retrieval import _seed_chunk, _vec


async def test_project_crud_and_document_counts(client):
    t = await seed_tenant(client, f"proj-{uuid4().hex[:6]}")
    headers = auth(t.owner_id, t.id)

    resp = await client.post(
        "/api/v1/projects",
        json={"name": "Acme refurb", "description": "Site works"},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    project = resp.json()
    assert project["document_count"] == 0

    resp = await client.patch(
        f"/api/v1/documents/{t.document_id}",
        json={"project_id": project["id"], "is_primary": True},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["project_id"] == project["id"]
    assert resp.json()["is_primary"] is True

    listed = (await client.get("/api/v1/projects", headers=headers)).json()
    by_id = {p["id"]: p for p in listed}
    assert by_id[project["id"]]["document_count"] == 1

    resp = await client.patch(
        f"/api/v1/projects/{project['id']}",
        json={"archived": True},
        headers=headers,
    )
    assert resp.json()["archived"] is True


async def test_project_delete_orphans_content_not_deletes(client):
    t = await seed_tenant(client, f"orph-{uuid4().hex[:6]}")
    headers = auth(t.owner_id, t.id)
    project = (
        await client.post("/api/v1/projects", json={"name": "Doomed"}, headers=headers)
    ).json()
    await client.patch(
        f"/api/v1/documents/{t.document_id}",
        json={"project_id": project["id"]},
        headers=headers,
    )

    resp = await client.delete(f"/api/v1/projects/{project['id']}", headers=headers)
    assert resp.status_code == 204
    doc = (await client.get(f"/api/v1/documents/{t.document_id}", headers=headers)).json()
    assert doc["project_id"] is None  # documents survive, unassigned


async def test_cross_tenant_project_assignment_rejected(client):
    a = await seed_tenant(client, f"pa-{uuid4().hex[:6]}")
    b = await seed_tenant(client, f"pb-{uuid4().hex[:6]}")
    # A's document cannot be assigned to B's project: RLS hides it → 404.
    resp = await client.patch(
        f"/api/v1/documents/{a.document_id}",
        json={"project_id": str(b.project_id)},
        headers=auth(a.owner_id, a.id),
    )
    assert resp.status_code == 404
    # And B's project list never shows A's projects.
    listed = (await client.get("/api/v1/projects", headers=auth(b.owner_id, b.id))).json()
    assert str(a.project_id) not in {p["id"] for p in listed}


@pytest.fixture
def scoped_llm(monkeypatch):
    """Cites every excerpt id in the system prompt, in order."""

    async def _fake(virtual_key, alias, messages, result):
        import re

        ids = re.findall(r"\[c:([0-9a-f-]{36})\]", messages[0]["content"])
        text = " ".join(f"[c:{i}]" for i in ids) or "No coverage."
        result.text_parts.append(text)
        yield text
        result.model, result.tokens_in, result.tokens_out = "m", 10, 5

    async def _fake_embed(virtual_key, text):
        return _vec(0), 7

    monkeypatch.setattr(litellm_client, "stream_chat", _fake)
    monkeypatch.setattr(litellm_client, "embed_query", _fake_embed)


async def test_project_chat_boosts_project_docs_and_reports_scope(client, scoped_llm):
    t = await seed_tenant(client, f"scope-{uuid4().hex[:6]}")
    await enable_llm_key(t)
    headers = auth(t.owner_id, t.id)

    # Two equally-similar docs; only one belongs to the project.
    proj_doc, proj_chunk = await _seed_chunk(t, "Zebra policy for the project.", hot=0)
    _, other_chunk = await _seed_chunk(t, "Zebra policy for everyone else.", hot=0)
    project = (
        await client.post("/api/v1/projects", json={"name": "Scoped"}, headers=headers)
    ).json()
    await client.patch(
        f"/api/v1/documents/{proj_doc}",
        json={"project_id": project["id"], "is_primary": True},
        headers=headers,
    )

    conv = (
        await client.post(
            "/api/v1/conversations",
            json={"title": "in project", "project_id": project["id"]},
            headers=headers,
        )
    ).json()
    assert conv["project_id"] == project["id"]

    resp = await client.post(
        f"/api/v1/conversations/{conv['id']}/messages",
        json={"content": "zebra policy?"},
        headers=headers,
    )
    done = dict(parse_sse(resp.text))["done"]
    assert done["scope_used"] == "project"
    # The project's primary doc outranks the equally-similar outsider.
    assert done["citations"][0]["chunk_id"] == str(proj_chunk)
    assert {c["chunk_id"] for c in done["citations"]} >= {str(proj_chunk), str(other_chunk)}


async def test_projectless_chat_reports_vault_scope(client, scoped_llm):
    t = await seed_tenant(client, f"vscope-{uuid4().hex[:6]}")
    await enable_llm_key(t)
    await _seed_chunk(t, "Zebra rules.", hot=0)
    resp = await client.post(
        f"/api/v1/conversations/{t.conversation_id}/messages",
        json={"content": "zebra?"},
        headers=auth(t.owner_id, t.id),
    )
    done = dict(parse_sse(resp.text))["done"]
    assert done["scope_used"] == "vault"

    resp = await client.post(
        f"/api/v1/conversations/{t.conversation_id}/messages",
        json={"content": "zebra?", "use_vault": False},
        headers=auth(t.owner_id, t.id),
    )
    assert dict(parse_sse(resp.text))["done"]["scope_used"] is None


async def test_summary_chunks_are_retrievable(client, scoped_llm):
    """A summary chunk participates in retrieval like any other chunk."""
    t = await seed_tenant(client, f"sum-{uuid4().hex[:6]}")
    doc_id, _ = await _seed_chunk(t, "Detailed body text.", hot=1)
    async with db.tenant_tx(t.owner_id, t.id) as conn:
        summary_chunk = await conn.fetchval(
            """
            insert into doc_chunks (tenant_id, document_id, content, is_summary, embedding)
            values ($1, $2, $3, true, $4::vector) returning id
            """,
            t.id,
            doc_id,
            "Document summary: key messages of the handbook.",
            "[" + ",".join(str(x) for x in _vec(0)) + "]",
        )
        await conn.execute("update documents set summary = 'Key messages…' where id = $1", doc_id)

    from app.retrieval import retrieve

    async with db.tenant_tx(t.owner_id, t.id) as conn:
        hits = await retrieve(conn, _vec(0), "key messages of the document")
    assert summary_chunk in [c.chunk_id for c in hits]
