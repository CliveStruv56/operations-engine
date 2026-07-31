"""Tasks, risks, conditions, stakeholders, activity feed, contract facts,
and cross-resource deletes."""

import pytest

pytestmark = pytest.mark.usefixtures("ref_data")


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
