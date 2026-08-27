"""Answer-PDF export jobs: submit, duplicate guard, poll, and role guards.

The rendering itself lives in the worker (WeasyPrint); what the API owns is
the job lifecycle, so that is what is tested here — with a fake queue and
fake storage, like the vault upload flow.
"""

from uuid import UUID, uuid4

from app.db import db
from app.queue import ingest_queue
from app.storage import Storage, storage
from tests.conftest import auth, seed_tenant


async def _seed_message(tenant, role: str = "assistant", content: str = "## An answer\nText."):
    async with db.tenant_tx(tenant.owner_id, tenant.id) as conn:
        return str(
            await conn.fetchval(
                "insert into messages (tenant_id, conversation_id, role, content)"
                " values ($1, $2, $3, $4) returning id",
                tenant.id,
                tenant.conversation_id,
                role,
                content,
            )
        )


def _fake_infra(monkeypatch):
    enqueued = []

    async def enqueue(tenant_id, job_id, user_id):
        enqueued.append((tenant_id, job_id, user_id))

    monkeypatch.setattr(ingest_queue, "enqueue_answer_pdf", enqueue)
    monkeypatch.setattr(Storage, "enabled", property(lambda self: True))
    monkeypatch.setattr(storage, "presign_get", lambda key: f"https://signed.example/{key}")
    return enqueued


async def test_submit_and_poll(client, monkeypatch):
    tenant = await seed_tenant(client, f"pdf-{uuid4().hex[:6]}")
    headers = auth(tenant.owner_id, tenant.id)
    message_id = await _seed_message(tenant)
    enqueued = _fake_infra(monkeypatch)

    resp = await client.post(
        f"/api/v1/conversations/{tenant.conversation_id}/messages/{message_id}/pdf",
        headers=headers,
    )
    assert resp.status_code == 202, resp.text
    job = resp.json()
    assert job["status"] == "queued"
    assert job["download_url"] is None
    assert [str(j[1]) for j in enqueued] == [job["id"]]

    # A second click while the first is in flight reuses the job.
    resp = await client.post(
        f"/api/v1/conversations/{tenant.conversation_id}/messages/{message_id}/pdf",
        headers=headers,
    )
    assert resp.status_code == 202
    assert resp.json()["id"] == job["id"]
    assert len(enqueued) == 1

    # The worker lands the file; the poll then carries the signed URL.
    file_key = f"{tenant.id}/conversations/{tenant.conversation_id}/answers/{message_id}.pdf"
    async with db.tenant_tx(tenant.owner_id, tenant.id) as conn:
        await conn.execute(
            "update conversation_export_jobs set status = 'succeeded', file_key = $2 where id = $1",
            UUID(job["id"]),
            file_key,
        )
    resp = await client.get(f"/api/v1/conversations/exports/{job['id']}", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "succeeded"
    assert body["download_url"] == f"https://signed.example/{file_key}"


async def test_only_assistant_messages_export(client, monkeypatch):
    tenant = await seed_tenant(client, f"pdfg-{uuid4().hex[:6]}")
    headers = auth(tenant.owner_id, tenant.id)
    user_msg = await _seed_message(tenant, role="user", content="my question")
    _fake_infra(monkeypatch)

    resp = await client.post(
        f"/api/v1/conversations/{tenant.conversation_id}/messages/{user_msg}/pdf",
        headers=headers,
    )
    assert resp.status_code == 404

    resp = await client.get(f"/api/v1/conversations/exports/{uuid4()}", headers=headers)
    assert resp.status_code == 404
