"""W3 draft endpoints: submit validation per kind, queue handoff in-tx,
polling with presigned download, flag gating, and tenant isolation."""

from uuid import UUID, uuid4

import pytest

from app.db import db
from app.errors import ApiError
from app.queue import ingest_queue
from app.storage import storage
from tests.conftest import auth, seed_tenant
from tests.test_groundwork import gw_setup

pytestmark = pytest.mark.usefixtures("ref_data")


@pytest.fixture
def fake_draft_queue(monkeypatch):
    jobs = []

    async def enqueue(tenant_id, project_id, job_id, user_id):
        jobs.append((tenant_id, project_id, job_id, user_id))

    monkeypatch.setattr(ingest_queue, "enqueue_draft", enqueue)
    return jobs


async def test_submit_monthly_report_and_poll(client, gw, fake_draft_queue, monkeypatch):
    resp = await client.post(
        f"/api/v1/projects/{gw['pid']}/drafts",
        json={"kind": "monthly_report", "month": "2026-07"},
        headers=gw["h"],
    )
    assert resp.status_code == 202, resp.text
    job = resp.json()
    assert job["status"] == "queued" and job["kind"] == "monthly_report"
    assert fake_draft_queue == [(gw["t"].id, UUID(gw["pid"]), UUID(job["id"]), gw["t"].owner_id)]

    polled = await client.get(f"/api/v1/projects/drafts/{job['id']}", headers=gw["h"])
    assert polled.status_code == 200
    assert polled.json()["status"] == "queued" and polled.json()["download_url"] is None

    # Worker finishes: succeeded rows carry a presigned download URL.
    async with db.tenant_tx(gw["t"].owner_id, gw["t"].id) as conn:
        await conn.execute(
            """
            update proj_draft_jobs
            set status = 'succeeded', file_key = 'k/drafts/x.docx', to_confirm_count = 3
            where id = $1
            """,
            UUID(job["id"]),
        )
    monkeypatch.setattr(storage, "presign_get", lambda key: f"http://fake-storage/{key}?get")
    done = (await client.get(f"/api/v1/projects/drafts/{job['id']}", headers=gw["h"])).json()
    assert done["download_url"] == "http://fake-storage/k/drafts/x.docx?get"
    assert done["to_confirm_count"] == 3


async def test_submit_validation_per_kind(client, gw, fake_draft_queue):
    base = f"/api/v1/projects/{gw['pid']}/drafts"
    resp = await client.post(base, json={"kind": "monthly_report"}, headers=gw["h"])
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "month_required"

    resp = await client.post(base, json={"kind": "funding_bid"}, headers=gw["h"])
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "funding_source_required"

    resp = await client.post(
        base, json={"kind": "funding_bid", "funding_source_id": str(uuid4())}, headers=gw["h"]
    )
    assert resp.status_code == 404

    created = await client.post(
        f"/api/v1/projects/{gw['pid']}/funding",
        json={"name": "CLT grant", "kind": "grant"},
        headers=gw["h"],
    )
    resp = await client.post(
        base,
        json={"kind": "funding_bid", "funding_source_id": created.json()["id"]},
        headers=gw["h"],
    )
    assert resp.status_code == 202, resp.text

    resp = await client.post(
        base,
        json={"kind": "feasibility_study", "instructions": "Focus on the barn conversion."},
        headers=gw["h"],
    )
    assert resp.status_code == 202
    assert resp.json()["kind"] == "feasibility_study"

    resp = await client.post(base, json={"kind": "shopping_list"}, headers=gw["h"])
    assert resp.status_code == 422  # pydantic pattern


async def test_failed_enqueue_rolls_back_job_row(client, gw, monkeypatch):
    async def broken(*args):
        raise ApiError(503, "queue_unavailable", "Ingestion queue is not configured")

    monkeypatch.setattr(ingest_queue, "enqueue_draft", broken)
    resp = await client.post(
        f"/api/v1/projects/{gw['pid']}/drafts",
        json={"kind": "monthly_report", "month": "2026-07"},
        headers=gw["h"],
    )
    assert resp.status_code == 503
    async with db.tenant_tx(gw["t"].owner_id, gw["t"].id) as conn:
        count = await conn.fetchval(
            "select count(*) from proj_draft_jobs where project_id = $1", UUID(gw["pid"])
        )
    assert count == 0  # no stuck "queued" job survives the failed enqueue


async def test_draft_jobs_are_tenant_isolated(client, gw, fake_draft_queue):
    resp = await client.post(
        f"/api/v1/projects/{gw['pid']}/drafts",
        json={"kind": "monthly_report", "month": "2026-07"},
        headers=gw["h"],
    )
    job_id = resp.json()["id"]

    intruder = await seed_tenant(client, f"draftb-{uuid4().hex[:6]}")
    async with db.tenant_tx(intruder.owner_id, intruder.id) as conn:
        await conn.execute(
            """update tenants set features = features || '{"projects": true}' where id = $1""",
            intruder.id,
        )
    other_headers = auth(intruder.owner_id, intruder.id)
    resp = await client.get(f"/api/v1/projects/drafts/{job_id}", headers=other_headers)
    assert resp.status_code == 404

    # And B cannot submit against A's project id.
    resp = await client.post(
        f"/api/v1/projects/{gw['pid']}/drafts",
        json={"kind": "monthly_report", "month": "2026-07"},
        headers=other_headers,
    )
    assert resp.status_code == 404


async def test_drafts_gated_on_module_flag(client, fake_draft_queue):
    tenant = await seed_tenant(client, f"noflag-{uuid4().hex[:6]}")
    headers = auth(tenant.owner_id, tenant.id)
    resp = await client.get(f"/api/v1/projects/drafts/{uuid4()}", headers=headers)
    assert resp.status_code == 404
    resp = await client.post(
        f"/api/v1/projects/{uuid4()}/drafts",
        json={"kind": "monthly_report", "month": "2026-07"},
        headers=headers,
    )
    assert resp.status_code == 404


async def test_second_project_draft_reuses_module_setup(client, gw, fake_draft_queue):
    """A second core project without groundwork setup 404s on submit."""
    core = await client.post("/api/v1/projects", json={"name": "Plain container"}, headers=gw["h"])
    resp = await client.post(
        f"/api/v1/projects/{core.json()['id']}/drafts",
        json={"kind": "monthly_report", "month": "2026-07"},
        headers=gw["h"],
    )
    assert resp.status_code == 404

    other_pid = (await gw_setup(client, gw["t"], name="Second scheme"))["project_id"]
    resp = await client.post(
        f"/api/v1/projects/{other_pid}/drafts",
        json={"kind": "monthly_report", "month": "2026-07"},
        headers=gw["h"],
    )
    assert resp.status_code == 202


@pytest.fixture
def fake_health_card_queue(monkeypatch):
    jobs = []

    async def enqueue(tenant_id, project_id, job_id, user_id):
        jobs.append((tenant_id, project_id, job_id, user_id))

    monkeypatch.setattr(ingest_queue, "enqueue_health_card", enqueue)
    return jobs


async def test_health_card_submit_and_poll(client, gw, fake_health_card_queue, monkeypatch):
    resp = await client.post(f"/api/v1/projects/{gw['pid']}/health-card", headers=gw["h"])
    assert resp.status_code == 202, resp.text
    job = resp.json()
    assert job["kind"] == "health_card" and job["status"] == "queued"
    assert len(fake_health_card_queue) == 1

    # Same poll endpoint serves health cards.
    polled = await client.get(f"/api/v1/projects/drafts/{job['id']}", headers=gw["h"])
    assert polled.status_code == 200 and polled.json()["kind"] == "health_card"

    async with db.tenant_tx(gw["t"].owner_id, gw["t"].id) as conn:
        await conn.execute(
            "update proj_draft_jobs set status = 'succeeded', file_key = 'k/x.pdf' where id = $1",
            UUID(job["id"]),
        )
    monkeypatch.setattr(storage, "presign_get", lambda key: f"http://fake-storage/{key}?get")
    done = (await client.get(f"/api/v1/projects/drafts/{job['id']}", headers=gw["h"])).json()
    assert done["download_url"] == "http://fake-storage/k/x.pdf?get"


async def test_health_card_isolated_and_gated(client, gw, fake_health_card_queue):
    intruder = await seed_tenant(client, f"hc-{uuid4().hex[:6]}")
    headers = auth(intruder.owner_id, intruder.id)
    # Module flag off → 404; A's project id under B's context → 404 either way.
    resp = await client.post(f"/api/v1/projects/{gw['pid']}/health-card", headers=headers)
    assert resp.status_code == 404
