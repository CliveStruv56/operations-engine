"""Groundwork W1: feature flag, spine seeding (exact counts + applicability),
portfolio RAG, dormancy rules, ref-seed idempotency, and module isolation."""

from uuid import uuid4

import asyncpg
import pytest

from app.db import db
from app.groundwork.rag import compute_rag
from app.groundwork.seeds import seed_reference_data
from tests.conftest import OWNER_URL, auth, seed_tenant

pytestmark = pytest.mark.usefixtures("ref_data")


@pytest.fixture(scope="session")
async def ref_data(test_database):
    conn = await asyncpg.connect(OWNER_URL)
    try:
        await seed_reference_data(conn)
    finally:
        await conn.close()


async def enable_module(tenant) -> None:
    async with db.tenant_tx(tenant.owner_id, tenant.id) as conn:
        await conn.execute(
            """update tenants set features = features || '{"projects": true}' where id = $1""",
            tenant.id,
        )


async def gw_setup(client, tenant, applicability=None, name="Dev scheme") -> dict:
    headers = auth(tenant.owner_id, tenant.id)
    core = await client.post("/api/v1/projects", json={"name": name}, headers=headers)
    assert core.status_code == 201, core.text
    resp = await client.post(
        f"/api/v1/projects/{core.json()['id']}/setup",
        json={"client_org": "Test CLT", "applicability": applicability or {}},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


# -- RAG pure function -------------------------------------------------------


def test_rag_programme_thresholds():
    assert compute_rag(0, 0, 0, 0).programme == "green"
    assert compute_rag(1, 0, 0, 0).programme == "amber"
    assert compute_rag(30, 0, 0, 0).programme == "amber"
    assert compute_rag(31, 0, 0, 0).programme == "red"


def test_rag_cost_thresholds():
    assert compute_rag(0, 100, 100, 0).cost == "green"
    assert compute_rag(0, 100, 100.01, 0).cost == "amber"
    assert compute_rag(0, 100, 110.01, 0).cost == "red"
    assert compute_rag(0, 0, 50, 0).cost == "green"  # no budget yet: not judged


def test_rag_risk_thresholds():
    assert compute_rag(0, 0, 0, 8).risk == "green"
    assert compute_rag(0, 0, 0, 9).risk == "amber"
    assert compute_rag(0, 0, 0, 15).risk == "amber"
    assert compute_rag(0, 0, 0, 16).risk == "red"


# -- feature flag ------------------------------------------------------------


async def test_flag_off_hides_module(client):
    t = await seed_tenant(client, f"gwoff-{uuid4().hex[:6]}")
    headers = auth(t.owner_id, t.id)
    assert (await client.get("/api/v1/projects/portfolio", headers=headers)).status_code == 404
    resp = await client.post(f"/api/v1/projects/{t.project_id}/setup", json={}, headers=headers)
    assert resp.status_code == 404
    # Core project endpoints are unaffected by the module flag.
    assert (await client.get("/api/v1/projects", headers=headers)).status_code == 200


# -- spine seeding -----------------------------------------------------------


async def test_setup_seeds_exact_counts(client):
    t = await seed_tenant(client, f"gw-{uuid4().hex[:6]}")
    await enable_module(t)
    out = await gw_setup(client, t)
    assert out["seeded"] == {"stages": 5, "tasks": 64, "doc_types": 32, "risks": 10}
    assert out["stage_current"] == "group"

    async with db.tenant_tx(t.owner_id, t.id) as conn:
        counts = await conn.fetchrow(
            """
            select (select count(*) from proj_stages where project_id = $1) as stages,
                   (select count(*) from proj_tasks where project_id = $1) as tasks,
                   (select count(*) from proj_documents where project_id = $1) as docs,
                   (select count(*) from proj_risks where project_id = $1) as risks
            """,
            out["project_id"],
        )
        assert dict(counts) == {"stages": 5, "tasks": 64, "docs": 32, "risks": 10}
        first = await conn.fetchrow(
            "select status, gate from proj_stages where project_id = $1 and position = 1",
            out["project_id"],
        )
        assert first["status"] == "active"
        import json as _json

        gate = _json.loads(first["gate"])
        assert all(item["done"] is False for item in gate)
        draftable = await conn.fetchval(
            "select count(*) from proj_documents where project_id = $1 and ai_draftable",
            out["project_id"],
        )
        assert draftable == 3

    # Second setup on the same project is rejected.
    resp = await client.post(
        f"/api/v1/projects/{out['project_id']}/setup",
        json={},
        headers=auth(t.owner_id, t.id),
    )
    assert resp.status_code == 409


async def test_applicability_effects(client):
    t = await seed_tenant(client, f"gwapp-{uuid4().hex[:6]}")
    await enable_module(t)
    everything = await gw_setup(
        client,
        t,
        applicability={"wales": True, "hrb": True, "conservation_area": True},
        name="All toggles",
    )
    assert everything["seeded"]["tasks"] == 67  # 64 + SAB + BSR + heritage

    exempt = await gw_setup(client, t, applicability={"bng_exempt": True}, name="BNG exempt")
    assert exempt["seeded"]["tasks"] == 63  # BNG task skipped

    async with db.tenant_tx(t.owner_id, t.id) as conn:
        sab = await conn.fetchval(
            "select count(*) from proj_tasks where project_id = $1 and title like 'SAB%'",
            everything["project_id"],
        )
        assert sab == 1
        bng = await conn.fetchval(
            "select count(*) from proj_tasks where project_id = $1 and title like 'BNG%'",
            exempt["project_id"],
        )
        assert bng == 0


async def test_ref_seed_idempotent():
    conn = await asyncpg.connect(OWNER_URL)
    try:
        await seed_reference_data(conn)
        await seed_reference_data(conn)
        assert await conn.fetchval("select count(*) from proj_ref_programmes") == 10
        assert await conn.fetchval("select count(*) from proj_ref_templates") == 1
    finally:
        await conn.close()


# -- portfolio ---------------------------------------------------------------


async def test_portfolio_rag_and_counts(client):
    t = await seed_tenant(client, f"gwport-{uuid4().hex[:6]}")
    await enable_module(t)
    out = await gw_setup(client, t)
    pid = out["project_id"]
    headers = auth(t.owner_id, t.id)

    rows = (await client.get("/api/v1/projects/portfolio", headers=headers)).json()
    row = next(r for r in rows if r["id"] == pid)
    # Fresh seed: no dates → programme green; no budget → cost green;
    # the seeded risk library's top score is 20 → risk red by design.
    assert row["rag"] == {"programme": "green", "cost": "green", "risk": "red"}
    assert row["open_risks"] == 10
    assert row["next_milestone"] is None

    async with db.tenant_tx(t.owner_id, t.id) as conn:
        await conn.execute(
            """
            update proj_tasks set due_date = current_date - 40
            where project_id = $1 and is_milestone
              and title = 'Landowner approach & negotiation'
            """,
            pid,
        )
        await conn.execute(
            """
            insert into proj_budget_lines (tenant_id, project_id, category, label,
                                           budget, forecast)
            values ($1, $2, 'construction', 'Main works', 100000, 115000)
            """,
            t.id,
            pid,
        )
        await conn.execute("update proj_risks set status = 'closed' where project_id = $1", pid)

    row = next(
        r
        for r in (await client.get("/api/v1/projects/portfolio", headers=headers)).json()
        if r["id"] == pid
    )
    assert row["rag"] == {"programme": "red", "cost": "red", "risk": "green"}
    assert row["overdue_tasks"] == 1
    assert row["open_risks"] == 0
    assert row["next_milestone"]["title"] == "Landowner approach & negotiation"


# -- status ------------------------------------------------------------------


async def test_dormant_requires_reason(client):
    t = await seed_tenant(client, f"gwdorm-{uuid4().hex[:6]}")
    await enable_module(t)
    pid = (await gw_setup(client, t))["project_id"]
    headers = auth(t.owner_id, t.id)

    resp = await client.post(
        f"/api/v1/projects/{pid}/status", json={"status": "dormant"}, headers=headers
    )
    assert resp.status_code == 400

    resp = await client.post(
        f"/api/v1/projects/{pid}/status",
        json={"status": "dormant", "dormancy_reason": "funding_gap"},
        headers=headers,
    )
    assert resp.status_code == 200
    resp = await client.post(
        f"/api/v1/projects/{pid}/status", json={"status": "active"}, headers=headers
    )
    async with db.tenant_tx(t.owner_id, t.id) as conn:
        row = await conn.fetchrow("select status, dormancy_reason from proj_projects")
        assert row["status"] == "active" and row["dormancy_reason"] is None


# -- isolation ---------------------------------------------------------------

# All nine tenant-scoped module tables (PRD §2) — setup seeds the first five;
# _seed_room_rows fills the user-created remainder.
MODULE_TABLES = [
    "proj_projects",
    "proj_stages",
    "proj_tasks",
    "proj_documents",
    "proj_risks",
    "proj_budget_lines",
    "proj_funding_sources",
    "proj_conditions",
    "proj_stakeholders",
]


async def _seed_room_rows(client, tenant, pid: str) -> None:
    headers = auth(tenant.owner_id, tenant.id)
    base = f"/api/v1/projects/{pid}"
    resp = await client.put(
        f"{base}/budget",
        json=[{"category": "land", "label": "Acquisition", "budget": 1000}],
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    resp = await client.post(
        f"{base}/funding", json={"name": "CLT grant", "kind": "grant"}, headers=headers
    )
    assert resp.status_code == 201, resp.text
    resp = await client.post(
        f"{base}/conditions",
        json={"number": "3", "description": "Drainage details"},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    resp = await client.post(
        f"{base}/stakeholders", json={"name": "Cllr Jones", "role": "lpa"}, headers=headers
    )
    assert resp.status_code == 201, resp.text


async def test_module_isolation(client):
    a = await seed_tenant(client, f"gwa-{uuid4().hex[:6]}")
    b = await seed_tenant(client, f"gwb-{uuid4().hex[:6]}")
    await enable_module(a)
    await enable_module(b)
    a_pid = (await gw_setup(client, a, name="A scheme"))["project_id"]
    b_pid = (await gw_setup(client, b, name="B scheme"))["project_id"]
    await _seed_room_rows(client, a, a_pid)
    await _seed_room_rows(client, b, b_pid)

    # SQL level: tenant A context sees only A rows in every seeded module table.
    async with db.tenant_tx(a.owner_id, a.id) as conn:
        for table in MODULE_TABLES:
            leaked = await conn.fetchval(
                f"select count(*) from {table} where tenant_id <> $1", a.id
            )
            assert leaked == 0, f"{table} leaked cross-tenant rows"
            mine = await conn.fetchval(f"select count(*) from {table} where tenant_id = $1", a.id)
            assert mine > 0, f"{table} has no rows for tenant A"
        # Reference tables are readable from any tenant context.
        assert await conn.fetchval("select count(*) from proj_ref_programmes") == 10

    # Endpoint level: B's project id under A's token → 404, and A's portfolio
    # never lists B's project.
    headers_a = auth(a.owner_id, a.id)
    resp = await client.post(
        f"/api/v1/projects/{b_pid}/status", json={"status": "complete"}, headers=headers_a
    )
    assert resp.status_code == 404
    rows = (await client.get("/api/v1/projects/portfolio", headers=headers_a)).json()
    assert b_pid not in {r["id"] for r in rows}
