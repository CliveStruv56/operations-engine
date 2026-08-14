"""Core project plans: blank vs planned create, tasks, isolation of assignees."""

from uuid import uuid4

from tests.conftest import auth, seed_tenant


async def test_blank_create_has_no_plan(client):
    t = await seed_tenant(client, f"blank-{uuid4().hex[:6]}")
    headers = auth(t.owner_id, t.id)
    resp = await client.post("/api/v1/projects", json={"name": "Folder"}, headers=headers)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["has_plan"] is False
    assert body["document_count"] == 0
    assert body["open_task_count"] == 0

    tasks = await client.get(f"/api/v1/projects/{body['id']}/plan-tasks", headers=headers)
    assert tasks.status_code == 200
    assert tasks.json() == []

    add = await client.post(
        f"/api/v1/projects/{body['id']}/plan-tasks",
        json={"title": "Nope"},
        headers=headers,
    )
    assert add.status_code == 400
    assert add.json()["error"]["code"] == "no_plan"


async def test_blank_rejects_seed_tasks(client):
    t = await seed_tenant(client, f"rej-{uuid4().hex[:6]}")
    resp = await client.post(
        "/api/v1/projects",
        json={"name": "Folder", "kind": "blank", "tasks": [{"title": "x"}]},
        headers=auth(t.owner_id, t.id),
    )
    assert resp.status_code == 400


async def test_planned_create_seeds_brief_and_tasks(client):
    t = await seed_tenant(client, f"plan-{uuid4().hex[:6]}")
    headers = auth(t.owner_id, t.id)
    resp = await client.post(
        "/api/v1/projects",
        json={
            "name": "Hall roof",
            "kind": "planned",
            "tasks": [
                {
                    "title": "Get quotes",
                    "due_date": "2026-09-01",
                    "assignee_membership_id": str(t.membership_id),
                }
            ],
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["has_plan"] is True
    assert body["document_count"] == 1
    assert body["open_task_count"] == 1
    assert body["is_development"] is False

    docs = (await client.get("/api/v1/documents", headers=headers)).json()
    brief = next(d for d in docs if d["project_id"] == body["id"])
    assert brief["title"] == "Project brief"
    assert brief["is_primary"] is True
    assert brief["status"] == "ready"

    tasks = (await client.get(f"/api/v1/projects/{body['id']}/plan-tasks", headers=headers)).json()
    assert len(tasks) == 1
    assert tasks[0]["title"] == "Get quotes"
    assert tasks[0]["due_date"] == "2026-09-01"
    assert tasks[0]["assignee_membership_id"] == str(t.membership_id)


async def test_plan_task_crud_and_complete(client):
    t = await seed_tenant(client, f"crud-{uuid4().hex[:6]}")
    headers = auth(t.owner_id, t.id)
    project = (
        await client.post(
            "/api/v1/projects", json={"name": "Work", "kind": "planned"}, headers=headers
        )
    ).json()
    created = (
        await client.post(
            f"/api/v1/projects/{project['id']}/plan-tasks",
            json={"title": "Call the surveyor"},
            headers=headers,
        )
    ).json()
    assert created["status"] == "todo"

    patched = (
        await client.patch(
            f"/api/v1/projects/{project['id']}/plan-tasks/{created['id']}",
            json={"status": "done"},
            headers=headers,
        )
    ).json()
    assert patched["status"] == "done"
    assert patched["completed_at"] is not None

    listed = (await client.get("/api/v1/projects", headers=headers)).json()
    assert next(p for p in listed if p["id"] == project["id"])["open_task_count"] == 0

    resp = await client.delete(
        f"/api/v1/projects/{project['id']}/plan-tasks/{created['id']}", headers=headers
    )
    assert resp.status_code == 204


async def test_blank_project_can_gain_a_plan(client):
    t = await seed_tenant(client, f"gain-{uuid4().hex[:6]}")
    headers = auth(t.owner_id, t.id)
    project = (
        await client.post("/api/v1/projects", json={"name": "Folder"}, headers=headers)
    ).json()
    resp = await client.patch(
        f"/api/v1/projects/{project['id']}", json={"has_plan": True}, headers=headers
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["has_plan"] is True
    assert resp.json()["document_count"] == 1
    add = await client.post(
        f"/api/v1/projects/{project['id']}/plan-tasks",
        json={"title": "Now allowed", "details": "Call before Friday"},
        headers=headers,
    )
    assert add.status_code == 201, add.text
    assert add.json()["details"] == "Call before Friday"


async def test_plan_task_details_and_reopen(client):
    t = await seed_tenant(client, f"note-{uuid4().hex[:6]}")
    headers = auth(t.owner_id, t.id)
    project = (
        await client.post(
            "/api/v1/projects", json={"name": "Work", "kind": "planned"}, headers=headers
        )
    ).json()
    created = (
        await client.post(
            f"/api/v1/projects/{project['id']}/plan-tasks",
            json={"title": "Survey", "details": "Ask about drainage"},
            headers=headers,
        )
    ).json()
    done = (
        await client.patch(
            f"/api/v1/projects/{project['id']}/plan-tasks/{created['id']}",
            json={"status": "done"},
            headers=headers,
        )
    ).json()
    assert done["completed_at"] is not None
    reopened = (
        await client.patch(
            f"/api/v1/projects/{project['id']}/plan-tasks/{created['id']}",
            json={"status": "todo", "details": "Ask about drainage and access"},
            headers=headers,
        )
    ).json()
    assert reopened["status"] == "todo"
    assert reopened["completed_at"] is None
    assert reopened["details"] == "Ask about drainage and access"


async def test_cannot_assign_another_tenants_member(client):
    a = await seed_tenant(client, f"aa-{uuid4().hex[:6]}")
    b = await seed_tenant(client, f"bb-{uuid4().hex[:6]}")
    headers = auth(a.owner_id, a.id)
    project = (
        await client.post(
            "/api/v1/projects", json={"name": "Ours", "kind": "planned"}, headers=headers
        )
    ).json()
    resp = await client.post(
        f"/api/v1/projects/{project['id']}/plan-tasks",
        json={"title": "Spy", "assignee_membership_id": str(b.membership_id)},
        headers=headers,
    )
    assert resp.status_code == 404
