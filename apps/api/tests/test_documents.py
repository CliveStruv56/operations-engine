"""Vault document lifecycle with fake storage + queue: presign/create,
server-side complete validation, list/get, delete cascade + object removal,
reprocess transitions, and role rules."""

from uuid import uuid4

import pytest

from app.db import db
from app.queue import ingest_queue
from app.storage import storage
from tests.conftest import auth, seed_tenant

PDF = "application/pdf"


@pytest.fixture
def fake_storage(monkeypatch):
    """In-memory object store: presigns record keys, sizes are settable."""
    state = {"objects": {}, "deleted": [], "presigned": []}

    def presign_put(key, mime):
        state["presigned"].append(key)
        return f"http://fake-storage/{key}?sig=put"

    async def object_size(key):
        return state["objects"].get(key)

    async def delete_object(key):
        state["deleted"].append(key)
        state["objects"].pop(key, None)

    monkeypatch.setattr(storage, "presign_put", presign_put)
    monkeypatch.setattr(storage, "object_size", object_size)
    monkeypatch.setattr(storage, "delete_object", delete_object)
    return state


@pytest.fixture
def fake_queue(monkeypatch):
    jobs = []

    async def enqueue(tenant_id, document_id, user_id):
        jobs.append((tenant_id, document_id, user_id))

    monkeypatch.setattr(ingest_queue, "enqueue_ingest", enqueue)
    return jobs


async def create_doc(client, headers, fake_storage, title="handbook.pdf", size=1000) -> str:
    resp = await client.post(
        "/api/v1/documents",
        json={"title": title, "mime": PDF, "size_bytes": size},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["upload_url"].startswith("http://fake-storage/")
    # Simulate the browser's PUT by materialising the object.
    fake_storage["objects"][fake_storage["presigned"][-1]] = size
    return body["id"]


async def test_upload_complete_flow(client, fake_storage, fake_queue):
    tenant = await seed_tenant(client, f"vault-{uuid4().hex[:6]}")
    headers = auth(tenant.owner_id, tenant.id)

    doc_id = await create_doc(client, headers, fake_storage)
    resp = await client.get(f"/api/v1/documents/{doc_id}", headers=headers)
    assert resp.json()["status"] == "uploaded"

    resp = await client.post(f"/api/v1/documents/{doc_id}/complete", headers=headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "parsing"
    assert [str(j[1]) for j in fake_queue] == [str(doc_id)]

    # Double-complete is rejected.
    resp = await client.post(f"/api/v1/documents/{doc_id}/complete", headers=headers)
    assert resp.status_code == 409


async def test_complete_requires_uploaded_object(client, fake_storage, fake_queue):
    tenant = await seed_tenant(client, f"vault-{uuid4().hex[:6]}")
    headers = auth(tenant.owner_id, tenant.id)
    resp = await client.post(
        "/api/v1/documents",
        json={"title": "ghost.pdf", "mime": PDF, "size_bytes": 100},
        headers=headers,
    )
    doc_id = resp.json()["id"]  # no PUT happened

    resp = await client.post(f"/api/v1/documents/{doc_id}/complete", headers=headers)
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "not_uploaded"
    assert fake_queue == []


async def test_complete_rejects_oversized_object(client, fake_storage, fake_queue):
    """A client can lie in size_bytes; the head check at complete is the
    enforcement point."""
    tenant = await seed_tenant(client, f"vault-{uuid4().hex[:6]}")
    headers = auth(tenant.owner_id, tenant.id)
    doc_id = await create_doc(client, headers, fake_storage, size=1000)
    key = fake_storage["presigned"][-1]
    fake_storage["objects"][key] = 51 * 1024 * 1024  # actual object is 51 MB

    resp = await client.post(f"/api/v1/documents/{doc_id}/complete", headers=headers)
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "too_large"
    assert key in fake_storage["deleted"]
    resp = await client.get(f"/api/v1/documents/{doc_id}", headers=headers)
    assert resp.json()["status"] == "failed"
    assert fake_queue == []


async def test_create_validates_mime_and_size(client, fake_storage):
    tenant = await seed_tenant(client, f"vault-{uuid4().hex[:6]}")
    headers = auth(tenant.owner_id, tenant.id)

    resp = await client.post(
        "/api/v1/documents",
        json={"title": "x.exe", "mime": "application/x-msdownload", "size_bytes": 10},
        headers=headers,
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "unsupported_type"

    resp = await client.post(
        "/api/v1/documents",
        json={"title": "big.pdf", "mime": PDF, "size_bytes": 51 * 1024 * 1024},
        headers=headers,
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "too_large"


async def test_storage_disabled_returns_503(client):
    tenant = await seed_tenant(client, f"vault-{uuid4().hex[:6]}")
    resp = await client.post(
        "/api/v1/documents",
        json={"title": "a.pdf", "mime": PDF, "size_bytes": 10},
        headers=auth(tenant.owner_id, tenant.id),
    )
    assert resp.status_code == 503
    assert resp.json()["error"]["code"] == "storage_unavailable"


async def test_list_filters_by_status(client, fake_storage, fake_queue):
    tenant = await seed_tenant(client, f"vault-{uuid4().hex[:6]}")
    headers = auth(tenant.owner_id, tenant.id)
    doc_id = await create_doc(client, headers, fake_storage)

    listed = (await client.get("/api/v1/documents?status=uploaded", headers=headers)).json()
    assert [d["id"] for d in listed] == [doc_id]
    # The seeded 'ready' fixture doc doesn't leak into the filter.
    ready = (await client.get("/api/v1/documents?status=ready", headers=headers)).json()
    assert [d["id"] for d in ready] == [str(tenant.document_id)]


async def test_delete_removes_row_chunks_and_object(client, fake_storage, fake_queue):
    tenant = await seed_tenant(client, f"vault-{uuid4().hex[:6]}")
    headers = auth(tenant.owner_id, tenant.id)
    doc_id = await create_doc(client, headers, fake_storage)
    key = fake_storage["presigned"][-1]
    async with db.tenant_tx(tenant.owner_id, tenant.id) as conn:
        await conn.execute(
            "insert into doc_chunks (tenant_id, document_id, content) values ($1, $2, 'c')",
            tenant.id,
            doc_id,
        )

    resp = await client.delete(f"/api/v1/documents/{doc_id}", headers=headers)
    assert resp.status_code == 204
    assert key in fake_storage["deleted"]
    async with db.tenant_tx(tenant.owner_id, tenant.id) as conn:
        chunks = await conn.fetchval(
            "select count(*) from doc_chunks where document_id = $1", doc_id
        )
    assert chunks == 0
    resp = await client.get(f"/api/v1/documents/{doc_id}", headers=headers)
    assert resp.status_code == 404


async def test_member_cannot_delete_others_documents(client, fake_storage):
    tenant = await seed_tenant(client, f"vault-{uuid4().hex[:6]}")
    member_id = uuid4()
    resp = await client.post(
        "/api/v1/invites/accept",
        json={"token": tenant.invite_token},
        headers=auth(member_id),
    )
    assert resp.status_code == 200

    # Owner's seeded document: member may read but not delete.
    resp = await client.delete(
        f"/api/v1/documents/{tenant.document_id}", headers=auth(member_id, tenant.id)
    )
    assert resp.status_code == 403
    # Owner (admin role) can.
    resp = await client.delete(
        f"/api/v1/documents/{tenant.document_id}", headers=auth(tenant.owner_id, tenant.id)
    )
    assert resp.status_code == 204


async def test_reprocess_transitions(client, fake_storage, fake_queue):
    tenant = await seed_tenant(client, f"vault-{uuid4().hex[:6]}")
    headers = auth(tenant.owner_id, tenant.id)

    # The conftest doc has no stored file; reprocess requires one (a seeded
    # note has nothing to re-read), so this test stands in an uploaded one.
    async with db.tenant_tx(tenant.owner_id, tenant.id) as conn:
        await conn.execute(
            "update documents set storage_key = $2 where id = $1",
            tenant.document_id,
            f"{tenant.id}/{tenant.document_id}.pdf",
        )

    # Seeded doc is 'ready' → reprocess allowed.
    resp = await client.post(f"/api/v1/documents/{tenant.document_id}/reprocess", headers=headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "parsing"
    assert [str(j[1]) for j in fake_queue] == [str(tenant.document_id)]

    # Now mid-pipeline → a second reprocess is rejected.
    resp = await client.post(f"/api/v1/documents/{tenant.document_id}/reprocess", headers=headers)
    assert resp.status_code == 409
