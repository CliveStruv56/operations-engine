"""Project kinds (0031, docs/project-types-brief.md): the stored kind, the
database keeping it in step with Groundwork, the registry endpoint, the
module-off fallback, and the operator console's view of kinds."""

from uuid import uuid4

import asyncpg
import pytest

from app.db import db
from app.projects.kinds import PROJECT_KINDS
from tests.conftest import auth, make_token, seed_tenant


def admin_auth() -> dict[str, str]:
    return {"Authorization": f"Bearer {make_token(uuid4(), email='operator@example.com')}"}


async def set_flag(tenant, flag: str, on: bool) -> None:
    async with db.tenant_tx(tenant.owner_id, tenant.id) as conn:
        await conn.execute(
            "update tenants set features = features || jsonb_build_object($2::text, $3::bool)"
            " where id = $1",
            tenant.id,
            flag,
            on,
        )


async def test_every_registry_kind_is_storable_and_nothing_else_is(client):
    """The CHECK constraint and the registry must list the same kinds: a kind
    added to one and not the other fails here, not in production."""
    t = await seed_tenant(client, f"kinds-{uuid4().hex[:6]}")
    async with db.tenant_tx(t.owner_id, t.id) as conn:
        for kind in PROJECT_KINDS:
            await conn.execute(
                "insert into projects (tenant_id, name, created_by, kind) values ($1, $2, $3, $4)",
                t.id,
                f"k-{kind.key}",
                t.owner_id,
                kind.key,
            )
    with pytest.raises(asyncpg.CheckViolationError):
        async with db.tenant_tx(t.owner_id, t.id) as conn:
            await conn.execute(
                "insert into projects (tenant_id, name, created_by, kind)"
                " values ($1, 'x', $2, 'bogus')",
                t.id,
                t.owner_id,
            )


async def test_groundwork_row_sets_and_clears_the_kind(client):
    """The trigger writes the kind with the extension row, whatever the code
    path — so kind and proj_projects cannot drift."""
    t = await seed_tenant(client, f"sync-{uuid4().hex[:6]}")
    async with db.tenant_tx(t.owner_id, t.id) as conn:
        assert await conn.fetchval("select kind from projects where id = $1", t.project_id) == (
            "general"
        )
        await conn.execute(
            "insert into proj_projects (id, tenant_id) values ($1, $2)", t.project_id, t.id
        )
        assert await conn.fetchval("select kind from projects where id = $1", t.project_id) == (
            "development"
        )
        await conn.execute("delete from proj_projects where id = $1", t.project_id)
        assert await conn.fetchval("select kind from projects where id = $1", t.project_id) == (
            "general"
        )


async def test_create_accepts_new_and_legacy_shapes(client):
    t = await seed_tenant(client, f"create-{uuid4().hex[:6]}")
    headers = auth(t.owner_id, t.id)

    plain = await client.post("/api/v1/projects", json={"name": "Plain"}, headers=headers)
    assert plain.status_code == 201, plain.text
    assert plain.json()["kind"] == "general" and plain.json()["has_plan"] is False

    planned = await client.post(
        "/api/v1/projects", json={"name": "Planned", "with_plan": True}, headers=headers
    )
    assert planned.json()["kind"] == "general" and planned.json()["has_plan"] is True

    legacy = await client.post(
        "/api/v1/projects", json={"name": "Old client", "kind": "planned"}, headers=headers
    )
    assert legacy.json()["kind"] == "general" and legacy.json()["has_plan"] is True

    # A module kind is made by its own setup endpoint, never inline.
    resp = await client.post(
        "/api/v1/projects", json={"name": "Scheme", "kind": "development"}, headers=headers
    )
    assert resp.status_code == 422


async def test_project_kinds_follow_the_workspace_modules(client):
    t = await seed_tenant(client, f"avail-{uuid4().hex[:6]}")
    headers = auth(t.owner_id, t.id)

    body = (await client.get("/api/v1/project-kinds", headers=headers)).json()
    kinds = {k["key"]: k for k in body["kinds"]}
    assert kinds["general"]["available"] is True and kinds["general"]["home"] == "chat"
    assert kinds["development"]["available"] is False
    assert kinds["development"]["create"] == "setup"
    assert {a["key"] for a in body["addons"]} == {"contacts", "grants"}

    await set_flag(t, "projects", True)
    await set_flag(t, "grants", True)
    body = (await client.get("/api/v1/project-kinds", headers=headers)).json()
    assert {k["key"]: k["available"] for k in body["kinds"]}["development"] is True
    assert {a["key"]: a["available"] for a in body["addons"]} == {
        "contacts": False,
        "grants": True,
    }


async def test_switched_off_module_keeps_its_projects_listed(client):
    """Switching a module off must not lose its projects: they stay in the
    list, marked unavailable, and come back whole when it returns."""
    t = await seed_tenant(client, f"off-{uuid4().hex[:6]}")
    headers = auth(t.owner_id, t.id)
    async with db.tenant_tx(t.owner_id, t.id) as conn:
        await conn.execute(
            "insert into proj_projects (id, tenant_id) values ($1, $2)", t.project_id, t.id
        )

    rows = {p["id"]: p for p in (await client.get("/api/v1/projects", headers=headers)).json()}
    dev = rows[str(t.project_id)]
    assert dev["kind"] == "development" and dev["kind_available"] is False
    assert dev["stage_current"] == "group"

    await set_flag(t, "projects", True)
    rows = {p["id"]: p for p in (await client.get("/api/v1/projects", headers=headers)).json()}
    assert rows[str(t.project_id)]["kind_available"] is True


async def test_list_filters_by_kind_and_rejects_unknown_kinds(client):
    t = await seed_tenant(client, f"filter-{uuid4().hex[:6]}")
    headers = auth(t.owner_id, t.id)
    async with db.tenant_tx(t.owner_id, t.id) as conn:
        await conn.execute(
            "insert into proj_projects (id, tenant_id) values ($1, $2)", t.project_id, t.id
        )
    await client.post("/api/v1/projects", json={"name": "Plain"}, headers=headers)

    dev = (await client.get("/api/v1/projects?kind=development", headers=headers)).json()
    assert [p["id"] for p in dev] == [str(t.project_id)]
    general = (await client.get("/api/v1/projects?kind=general", headers=headers)).json()
    assert str(t.project_id) not in {p["id"] for p in general}
    assert (await client.get("/api/v1/projects?kind=bogus", headers=headers)).status_code == 400


async def test_admin_sees_what_each_module_adds_and_counts_by_kind(client):
    t = await seed_tenant(client, f"admin-{uuid4().hex[:6]}")
    async with db.tenant_tx(t.owner_id, t.id) as conn:
        await conn.execute(
            "insert into proj_projects (id, tenant_id) values ($1, $2)", t.project_id, t.id
        )

    modules = (await client.get("/api/v1/admin/modules", headers=admin_auth())).json()
    by_flag = {m["flag"]: m for m in modules}
    assert by_flag["projects"]["kinds"] == [{"key": "development", "label": "Development project"}]
    assert by_flag["grants"]["addons"] == ["Grant applications"]
    assert by_flag["contacts"]["addons"] == ["Contacts"]

    fleet = (await client.get("/api/v1/admin/tenants", headers=admin_auth())).json()
    row = next(r for r in fleet if r["id"] == str(t.id))
    assert row["project_counts"] == {"development": 1}

    # Not for workspace users.
    resp = await client.get("/api/v1/admin/modules", headers=auth(t.owner_id, t.id))
    assert resp.status_code == 403


async def test_workspace_sees_its_modules_read_only(client):
    """Settings' "Your modules": every module, whether this workspace has it,
    and what it adds — so a missing kind in the picker has a visible reason."""
    t = await seed_tenant(client, f"mods-{uuid4().hex[:6]}")
    await set_flag(t, "grants", True)
    modules = (await client.get("/api/v1/modules", headers=auth(t.owner_id, t.id))).json()
    by_flag = {m["flag"]: m for m in modules}
    assert by_flag["grants"]["enabled"] is True
    assert by_flag["grants"]["addons"] == ["Grant applications"]
    assert by_flag["projects"]["enabled"] is False
    assert by_flag["projects"]["kinds"] == [{"key": "development", "label": "Development project"}]
