"""Groundwork W2: gate mechanics (manual toggle, doc auto-flip, sign-off with
exceptions, stage advance), tasks, registry uploads, budget, funding +
catalogue, risks/conditions/stakeholders, activity."""

from uuid import UUID, uuid4

import pytest

from app.db import db
from app.storage import storage
from tests.conftest import auth, seed_tenant
from tests.test_groundwork import enable_module, gw_setup

pytestmark = pytest.mark.usefixtures("ref_data")

from tests.test_groundwork import ref_data  # noqa: E402,F401


@pytest.fixture
async def gw(client):
    t = await seed_tenant(client, f"room-{uuid4().hex[:6]}")
    await enable_module(t)
    out = await gw_setup(client, t)
    return {"t": t, "pid": out["project_id"], "h": auth(t.owner_id, t.id)}


async def _stages(client, gw):
    resp = await client.get(f"/api/v1/projects/{gw['pid']}/stages", headers=gw["h"])
    assert resp.status_code == 200, resp.text
    return resp.json()


async def test_gate_manual_toggle_and_computed_rejection(client, gw):
    stages = await _stages(client, gw)
    group = next(s for s in stages if s["stage_key"] == "group")
    site = next(s for s in stages if s["stage_key"] == "site")

    resp = await client.post(
        f"/api/v1/projects/{gw['pid']}/stages/{group['id']}/gate/g1/toggle", headers=gw["h"]
    )
    assert resp.status_code == 200
    item = next(i for i in resp.json()["gate"] if i["id"] == "g1")
    assert item["done"] is True and item["done_by"] is not None

    # Doc-kind items are computed, never hand-toggled.
    resp = await client.post(
        f"/api/v1/projects/{gw['pid']}/stages/{site['id']}/gate/s1/toggle", headers=gw["h"]
    )
    assert resp.status_code == 400


async def test_doc_status_auto_flips_gate(client, gw):
    docs = (await client.get(f"/api/v1/projects/{gw['pid']}/documents", headers=gw["h"])).json()
    needs = next(d for d in docs if d["doc_type_key"] == "housing_needs_survey")

    resp = await client.patch(
        f"/api/v1/projects/{gw['pid']}/documents/{needs['id']}",
        json={"status": "final"},
        headers=gw["h"],
    )
    assert resp.status_code == 200
    site = next(s for s in await _stages(client, gw) if s["stage_key"] == "site")
    assert next(i for i in site["gate"] if i["ref"] == "housing_needs_survey")["done"] is True

    # Back to review → the gate item reopens.
    await client.patch(
        f"/api/v1/projects/{gw['pid']}/documents/{needs['id']}",
        json={"status": "review"},
        headers=gw["h"],
    )
    site = next(s for s in await _stages(client, gw) if s["stage_key"] == "site")
    assert next(i for i in site["gate"] if i["ref"] == "housing_needs_survey")["done"] is False


async def test_signoff_blocked_then_exceptions_then_advance(client, gw):
    stages = await _stages(client, gw)
    group = next(s for s in stages if s["stage_key"] == "group")

    resp = await client.post(
        f"/api/v1/projects/{gw['pid']}/stages/{group['id']}/signoff", json={}, headers=gw["h"]
    )
    assert resp.status_code == 400
    assert "outstanding" in resp.json()["error"]["message"]

    resp = await client.post(
        f"/api/v1/projects/{gw['pid']}/stages/{group['id']}/signoff",
        json={"exceptions": "Insurance renewal pending — accepted by the board"},
        headers=gw["h"],
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "passed"
    assert resp.json()["gate_exceptions"].startswith("Insurance")

    stages = await _stages(client, gw)
    assert next(s for s in stages if s["stage_key"] == "site")["status"] == "active"
    detail = (await client.get(f"/api/v1/projects/{gw['pid']}/groundwork", headers=gw["h"])).json()
    assert detail["stage_current"] == "site"

    resp = await client.post(
        f"/api/v1/projects/{gw['pid']}/stages/{group['id']}/signoff",
        json={"exceptions": "again"},
        headers=gw["h"],
    )
    assert resp.status_code == 409


async def test_signoff_rejects_non_active_stage(client, gw):
    stages = await _stages(client, gw)
    site = next(s for s in stages if s["stage_key"] == "site")
    # Project is still on "group" — signing off "site" would skip a stage.
    resp = await client.post(
        f"/api/v1/projects/{gw['pid']}/stages/{site['id']}/signoff",
        json={"exceptions": "trying to skip ahead"},
        headers=gw["h"],
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "stage_not_active"


async def test_gate_toggle_rejected_after_signoff(client, gw):
    stages = await _stages(client, gw)
    group = next(s for s in stages if s["stage_key"] == "group")
    resp = await client.post(
        f"/api/v1/projects/{gw['pid']}/stages/{group['id']}/signoff",
        json={"exceptions": "accepted by the board"},
        headers=gw["h"],
    )
    assert resp.status_code == 200, resp.text

    resp = await client.post(
        f"/api/v1/projects/{gw['pid']}/stages/{group['id']}/gate/g1/toggle", headers=gw["h"]
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "already_signed_off"


async def test_stage_regression_requires_note(client, gw):
    stages = await _stages(client, gw)
    group = next(s for s in stages if s["stage_key"] == "group")
    resp = await client.patch(
        f"/api/v1/projects/{gw['pid']}/stages/{group['id']}",
        json={"status": "regressed"},
        headers=gw["h"],
    )
    assert resp.status_code == 400
    resp = await client.patch(
        f"/api/v1/projects/{gw['pid']}/stages/{group['id']}",
        json={"status": "regressed", "note": "Entity registration rejected, refiling"},
        headers=gw["h"],
    )
    assert resp.status_code == 200
    assert "refiling" in resp.json()["gate_exceptions"]


async def test_tasks_crud_filters_and_bulk(client, gw):
    base = f"/api/v1/projects/{gw['pid']}/tasks"
    created = await client.post(
        base,
        json={"stage_key": "site", "title": "Extra survey", "due_date": "2026-01-01"},
        headers=gw["h"],
    )
    assert created.status_code == 201
    tid = created.json()["id"]
    assert created.json()["source"] == "manual"

    overdue = (await client.get(f"{base}?overdue=true", headers=gw["h"])).json()
    assert tid in {t["id"] for t in overdue}

    site_tasks = (await client.get(f"{base}?stage_key=site&status=todo", headers=gw["h"])).json()
    assert all(t["stage_key"] == "site" for t in site_tasks)

    patched = await client.patch(f"{base}/{tid}", json={"status": "done"}, headers=gw["h"])
    assert patched.json()["completed_at"] is not None

    two = [t["id"] for t in site_tasks if t["id"] != tid][:2]
    resp = await client.post(f"{base}/bulk-complete", json={"ids": two}, headers=gw["h"])
    assert resp.json()["completed"] == 2

    assert (await client.delete(f"{base}/{tid}", headers=gw["h"])).status_code == 204


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


async def test_budget_put_and_totals(client, gw):
    base = f"/api/v1/projects/{gw['pid']}/budget"
    resp = await client.put(
        base,
        json=[
            {"category": "land", "label": "Acquisition", "budget": 250000, "forecast": 250000},
            {
                "category": "construction",
                "label": "Main works",
                "budget": 1000000,
                "forecast": 1080000,
            },
            {
                "category": "fees",
                "label": "Design team",
                "budget": 120000,
                "forecast": 118000,
                "actual": 40000,
            },
        ],
        headers=gw["h"],
    )
    assert resp.status_code == 200, resp.text
    totals = resp.json()["totals"]
    assert totals == {
        "budget": 1370000.0,
        "forecast": 1448000.0,
        "actual": 40000.0,
        "variance": 78000.0,
    }
    assert len((await client.get(base, headers=gw["h"])).json()["lines"]) == 3


async def test_funding_crud_and_catalogue(client, gw):
    cat = (
        await client.get("/api/v1/projects/funding-programmes?nation=wales", headers=gw["h"])
    ).json()
    keys = {p["key"] for p in cat}
    assert "cwmpas_cch" in keys and "ecology_clh" in keys  # wales + uk-wide
    assert "sahp_cme" not in keys
    assert all(p["stale"] is False for p in cat)
    paused = (
        await client.get("/api/v1/projects/funding-programmes?status=paused", headers=gw["h"])
    ).json()
    assert [p["key"] for p in paused] == ["acre_halls"]

    base = f"/api/v1/projects/{gw['pid']}/funding"
    created = await client.post(
        base,
        json={
            "programme_key": "cwmpas_cch",
            "name": "Cwmpas advice grant",
            "kind": "grant",
            "amount_sought": 2500,
            "drawdown_schedule": [
                {"label": "On award", "due_date": "2026-10-01", "amount": 2500, "status": "planned"}
            ],
        },
        headers=gw["h"],
    )
    assert created.status_code == 201
    fid = created.json()["id"]
    listed = (await client.get(base, headers=gw["h"])).json()
    assert listed[0]["drawdown_schedule"][0]["amount"] == 2500

    assert (
        await client.patch(
            f"{base}/{fid}", json={"status": "secured", "amount_secured": 2500}, headers=gw["h"]
        )
    ).status_code == 200
    assert (await client.delete(f"{base}/{fid}", headers=gw["h"])).status_code == 204


async def test_risks_conditions_stakeholders_and_activity(client, gw):
    pid, h = gw["pid"], gw["h"]
    risk = await client.post(
        f"/api/v1/projects/{pid}/risks",
        json={
            "category": "custom",
            "description": "Archaeology find delays start",
            "likelihood": 2,
            "impact": 4,
        },
        headers=h,
    )
    assert risk.status_code == 201
    assert (
        await client.patch(
            f"/api/v1/projects/{pid}/risks/{risk.json()['id']}",
            json={"status": "monitoring"},
            headers=h,
        )
    ).status_code == 200

    cond = await client.post(
        f"/api/v1/projects/{pid}/conditions",
        json={
            "application_ref": "24/00123/FUL",
            "number": "3",
            "description": "Materials samples to be approved",
            "pre_commencement": True,
        },
        headers=h,
    )
    assert cond.status_code == 201
    assert (
        await client.patch(
            f"/api/v1/projects/{pid}/conditions/{cond.json()['id']}",
            json={"status": "submitted", "submitted_at": "2026-07-01"},
            headers=h,
        )
    ).status_code == 200
    conds = (await client.get(f"/api/v1/projects/{pid}/conditions", headers=h)).json()
    assert conds[0]["pre_commencement"] is True

    sh = await client.post(
        f"/api/v1/projects/{pid}/stakeholders",
        json={"name": "Jan Price", "org": "Borough Council", "role": "lpa"},
        headers=h,
    )
    assert sh.status_code == 201

    activity = (await client.get(f"/api/v1/projects/{pid}/activity", headers=h)).json()
    actions = {a["action"] for a in activity}
    assert {"projects.setup", "projects.risk_create", "projects.condition_update"} <= actions


async def test_project_patch_contract_facts(client, gw):
    resp = await client.patch(
        f"/api/v1/projects/{gw['pid']}/groundwork",
        json={
            "contract_facts": {
                "contractor": "Brick & Beam Ltd",
                "contract_form": "JCT ICD",
                "retention_pct": 3,
            }
        },
        headers=gw["h"],
    )
    assert resp.status_code == 200
    assert resp.json()["contract_facts"]["contract_form"] == "JCT ICD"


async def test_delete_task_funding_condition_stakeholder(client, gw):
    base = f"/api/v1/projects/{gw['pid']}"
    h = gw["h"]

    task = (
        await client.post(
            f"{base}/tasks", json={"stage_key": "group", "title": "Temp task"}, headers=h
        )
    ).json()
    assert (await client.delete(f"{base}/tasks/{task['id']}", headers=h)).status_code == 204
    titles = [t["title"] for t in (await client.get(f"{base}/tasks", headers=h)).json()]
    assert "Temp task" not in titles

    fund = (
        await client.post(
            f"{base}/funding", json={"name": "Temp grant", "kind": "grant"}, headers=h
        )
    ).json()
    assert (await client.delete(f"{base}/funding/{fund['id']}", headers=h)).status_code == 204
    assert (await client.delete(f"{base}/funding/{fund['id']}", headers=h)).status_code == 404

    cond = (
        await client.post(
            f"{base}/conditions", json={"number": "9", "description": "Temp"}, headers=h
        )
    ).json()
    assert (await client.delete(f"{base}/conditions/{cond['id']}", headers=h)).status_code == 204

    stake = (
        await client.post(
            f"{base}/stakeholders", json={"name": "Temp person", "role": "other"}, headers=h
        )
    ).json()
    assert (await client.delete(f"{base}/stakeholders/{stake['id']}", headers=h)).status_code == 204


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
