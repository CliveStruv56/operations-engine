"""NEXT-002 acceptance: the worker's context-pack gatherer run against this
suite's migrated database. Worker CI has no Postgres, so the worker's only
DB-touching drafts module (deliberately asyncpg + pydantic only) is imported
across the monorepo and exercised here, including cross-tenant leakage."""

import sys
from datetime import date
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from app.db import db
from tests.conftest import auth, seed_tenant
from tests.test_groundwork import (
    enable_module,
    gw_setup,
    ref_data,  # noqa: F401
)

sys.path.append(str(Path(__file__).resolve().parents[2] / "worker"))

from worker.drafts.context import gather  # noqa: E402

pytestmark = pytest.mark.usefixtures("ref_data")

TODAY = date(2026, 7, 31)


async def _seeded_project(client, tenant) -> str:
    headers = auth(tenant.owner_id, tenant.id)
    pid = (await gw_setup(client, tenant))["project_id"]
    base = f"/api/v1/projects/{pid}"
    resp = await client.put(
        f"{base}/budget",
        json=[
            {"category": "land", "label": "Acquisition", "budget": 250000, "forecast": 250000},
            {"category": "fees", "label": "Design team", "budget": 100000, "forecast": 110000},
        ],
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    resp = await client.post(
        f"{base}/funding",
        json={"programme_key": "cwmpas_cch", "name": "Cwmpas grant", "kind": "grant"},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    resp = await client.post(
        f"{base}/conditions",
        json={"number": "3", "description": "Drainage details"},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    resp = await client.post(
        f"{base}/stakeholders",
        json={"name": "Jan Price", "role": "lpa"},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return pid


async def test_gather_counts_and_catalogue_join(client):
    tenant = await seed_tenant(client, f"gather-{uuid4().hex[:6]}")
    await enable_module(tenant)
    pid = await _seeded_project(client, tenant)

    async with db.tenant_tx(tenant.owner_id, tenant.id) as conn:
        pack = await gather(conn, UUID(pid), "monthly_report", {"month": "2026-07"}, TODAY)

    assert pack.project.name == "Dev scheme"
    assert [s.stage_key for s in pack.stages] == ["group", "site", "plan", "build", "live"]
    assert len(pack.tasks) >= 60  # template library, ± applicability
    assert len(pack.risks) == 10
    assert len(pack.budget_lines) == 2
    assert pack.budget_totals.budget == 350000
    assert pack.budget_totals.variance == 10000
    assert len(pack.conditions) == 1 and len(pack.stakeholders) == 1
    assert pack.report_month == "2026-07"
    # The funding stack's programme_key joins its catalogue row, not stale yet.
    assert [p.key for p in pack.programmes] == ["cwmpas_cch"]
    assert pack.programmes[0].stale is False

    # Past next_review (2026-10-28) the same row reads as stale.
    async with db.tenant_tx(tenant.owner_id, tenant.id) as conn:
        later = await gather(conn, UUID(pid), "monthly_report", {}, date(2027, 1, 1))
    assert later.programmes[0].stale is True


async def test_gather_funding_bid_target_resolution(client):
    tenant = await seed_tenant(client, f"gather-{uuid4().hex[:6]}")
    await enable_module(tenant)
    pid = await _seeded_project(client, tenant)

    async with db.tenant_tx(tenant.owner_id, tenant.id) as conn:
        rows = await conn.fetch(
            "select id from proj_funding_sources where project_id = $1", UUID(pid)
        )
        source_id = rows[0]["id"]
        pack = await gather(
            conn, UUID(pid), "funding_bid", {"funding_source_id": str(source_id)}, TODAY
        )
        assert pack.target_funding() is not None
        assert pack.target_programme() is not None
        assert pack.target_programme().key == "cwmpas_cch"

        with pytest.raises(ValueError, match="Funding source not found"):
            await gather(conn, UUID(pid), "funding_bid", {"funding_source_id": str(uuid4())}, TODAY)


async def test_gather_is_tenant_isolated(client):
    a = await seed_tenant(client, f"gathera-{uuid4().hex[:6]}")
    b = await seed_tenant(client, f"gatherb-{uuid4().hex[:6]}")
    await enable_module(a)
    await enable_module(b)
    a_pid = await _seeded_project(client, a)
    b_pid = (await gw_setup(client, b, name="B scheme"))["project_id"]

    # B's project id under A's tenant context: RLS hides the row entirely.
    async with db.tenant_tx(a.owner_id, a.id) as conn:
        with pytest.raises(ValueError, match="Project not found"):
            await gather(conn, UUID(b_pid), "monthly_report", {}, TODAY)

    # And A's own pack never carries another tenant's rows.
    async with db.tenant_tx(a.owner_id, a.id) as conn:
        pack = await gather(conn, UUID(a_pid), "monthly_report", {}, TODAY)
    assert pack.project.id == UUID(a_pid)
