"""Workspace-export jobs: submit, duplicate guard, poll, role guard.

The archive itself is assembled in the worker; what the API owns is the job
lifecycle — with a fake queue and fake storage, like the answer-PDF tests.
"""

from uuid import UUID, uuid4

from app.db import db
from app.queue import ingest_queue
from app.storage import Storage, storage
from tests.conftest import auth, seed_tenant


def _fake_infra(monkeypatch):
    enqueued = []

    async def enqueue(tenant_id, job_id, user_id):
        enqueued.append((tenant_id, job_id, user_id))

    monkeypatch.setattr(ingest_queue, "enqueue_workspace_export", enqueue)
    monkeypatch.setattr(Storage, "enabled", property(lambda self: True))
    return enqueued


async def test_submit_and_poll(client, monkeypatch):
    tenant = await seed_tenant(client, f"wsx-{uuid4().hex[:6]}")
    headers = auth(tenant.owner_id, tenant.id)
    enqueued = _fake_infra(monkeypatch)
    presigned: dict = {}

    def fake_presign(key, *, filename=None):
        presigned["filename"] = filename
        return f"https://signed.example/{key}"

    # Patch the instance, not the class: earlier test files patch the
    # instance, and monkeypatch's teardown materialises the original bound
    # method as an instance attribute — which would shadow a class patch.
    monkeypatch.setattr(storage, "presign_get", fake_presign)

    resp = await client.post("/api/v1/tenants/me/export", headers=headers)
    assert resp.status_code == 202, resp.text
    job = resp.json()
    assert job["status"] == "queued"
    assert job["kind"] == "archive"
    assert job["download_url"] is None
    assert [str(j[1]) for j in enqueued] == [job["id"]]

    # A second click while the first is in flight reuses the job.
    resp = await client.post("/api/v1/tenants/me/export", headers=headers)
    assert resp.status_code == 202
    assert resp.json()["id"] == job["id"]
    assert len(enqueued) == 1

    # The worker lands the zip; the poll then carries the signed URL and a
    # readable filename rather than a uuid.
    file_key = f"{tenant.id}/exports/{job['id']}.zip"
    async with db.tenant_tx(tenant.owner_id, tenant.id) as conn:
        await conn.execute(
            "update workspace_export_jobs set status = 'succeeded', file_key = $2 where id = $1",
            UUID(job["id"]),
            file_key,
        )
    resp = await client.get(f"/api/v1/tenants/me/exports/{job['id']}", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "succeeded"
    assert body["download_url"] == f"https://signed.example/{file_key}"
    assert presigned["filename"].startswith("flowgrid-export-wsx-")
    assert presigned["filename"].endswith(".zip")

    resp = await client.get(f"/api/v1/tenants/me/exports/{uuid4()}", headers=headers)
    assert resp.status_code == 404


async def test_member_cannot_export(client, monkeypatch):
    """The archive holds every member's shared work — requesting it is an
    admin act."""
    tenant = await seed_tenant(client, f"wsxm-{uuid4().hex[:6]}")
    _fake_infra(monkeypatch)
    member = uuid4()
    resp = await client.post(
        "/api/v1/invites/accept", json={"token": tenant.invite_token}, headers=auth(member)
    )
    assert resp.status_code == 200, resp.text

    resp = await client.post("/api/v1/tenants/me/export", headers=auth(member, tenant.id))
    assert resp.status_code == 403


async def test_storage_off_rejects(client, monkeypatch):
    tenant = await seed_tenant(client, f"wsxs-{uuid4().hex[:6]}")
    enqueued = _fake_infra(monkeypatch)
    monkeypatch.setattr(Storage, "enabled", property(lambda self: False))
    resp = await client.post("/api/v1/tenants/me/export", headers=auth(tenant.owner_id, tenant.id))
    assert resp.status_code == 503
    assert enqueued == []
