"""Registry uploads (presign → verified complete → versions → download) and
vault-document linking rules."""

from uuid import UUID, uuid4

import pytest

from app.db import db
from app.storage import storage
from tests.test_groundwork import gw_setup

pytestmark = pytest.mark.usefixtures("ref_data")


@pytest.fixture
def fake_storage(monkeypatch):
    objects = {}
    monkeypatch.setattr(storage, "presign_put", lambda key, mime: f"http://fake-storage/{key}?put")
    monkeypatch.setattr(storage, "presign_get", lambda key: f"http://fake-storage/{key}?get")

    async def object_size(key):
        return objects.get(key)

    monkeypatch.setattr(storage, "object_size", object_size)
    return objects


async def test_registry_upload_versions_and_download(client, gw, fake_storage):
    docs = (await client.get(f"/api/v1/projects/{gw['pid']}/documents", headers=gw["h"])).json()
    doc = next(d for d in docs if d["doc_type_key"] == "development_appraisal")
    base = f"/api/v1/projects/{gw['pid']}/documents/{doc['id']}"

    up = await client.post(
        f"{base}/upload",
        json={
            "filename": "appraisal v1.xlsx",
            "mime": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "size_bytes": 1000,
        },
        headers=gw["h"],
    )
    assert up.status_code == 200, up.text
    key = up.json()["file_key"]
    assert "/v1-appraisal" in key

    # Complete before the browser PUT lands → rejected.
    resp = await client.post(f"{base}/upload/complete", json={"file_key": key}, headers=gw["h"])
    assert resp.status_code == 400

    fake_storage[key] = 1000
    resp = await client.post(
        f"{base}/upload/complete", json={"file_key": key, "note": "First cut"}, headers=gw["h"]
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["current_file_key"] == key
    assert len(body["versions"]) == 1 and body["versions"][0]["note"] == "First cut"

    # A foreign key path is rejected outright.
    resp = await client.post(
        f"{base}/upload/complete",
        json={"file_key": f"{gw['t'].id}/projects/{uuid4()}/docs/x/v9-evil.pdf"},
        headers=gw["h"],
    )
    assert resp.status_code == 400

    dl = await client.get(f"{base}/download", headers=gw["h"])
    assert dl.json()["download_url"].endswith("?get")


async def test_vault_link_rejects_cross_project_documents(client, gw):
    other_pid = (await gw_setup(client, gw["t"], name="Other scheme"))["project_id"]

    async def make_vault_doc(project_id):
        doc_id = uuid4()
        async with db.tenant_tx(gw["t"].owner_id, gw["t"].id) as conn:
            await conn.execute(
                """
                insert into documents (id, tenant_id, title, storage_key, mime,
                                       project_id, created_by)
                values ($1, $2, 'Survey', 'k.pdf', 'application/pdf', $3, $4)
                """,
                doc_id,
                gw["t"].id,
                project_id,
                gw["t"].owner_id,
            )
        return doc_id

    docs = (await client.get(f"/api/v1/projects/{gw['pid']}/documents", headers=gw["h"])).json()
    target = docs[0]

    # A vault document owned by another project can never back this registry.
    other_doc = await make_vault_doc(UUID(other_pid))
    resp = await client.patch(
        f"/api/v1/projects/{gw['pid']}/documents/{target['id']}",
        json={"vault_document_id": str(other_doc)},
        headers=gw["h"],
    )
    assert resp.status_code == 404

    # Unassigned vault documents are linkable.
    unassigned = await make_vault_doc(None)
    resp = await client.patch(
        f"/api/v1/projects/{gw['pid']}/documents/{target['id']}",
        json={"vault_document_id": str(unassigned)},
        headers=gw["h"],
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["vault_document_id"] == str(unassigned)
