"""Grantwork's context gatherer run against this suite's migrated database.

Worker CI has no Postgres, so the worker's DB-touching Grantwork modules
(deliberately asyncpg + pydantic only) are imported across the monorepo and
exercised here — including cross-tenant leakage, which is the reason the rule
in ASSUMPTIONS #13 exists.
"""

import sys
from datetime import date
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from app.db import db
from tests.conftest import auth, seed_tenant
from tests.test_grants import (  # noqa: F401
    create_application,
    grant_ref_data,
    make_tenant,
)

sys.path.append(str(Path(__file__).resolve().parents[2] / "worker"))

from worker.grants.context import gather  # noqa: E402
from worker.grants.retrieval import scope_weights  # noqa: E402

pytestmark = pytest.mark.usefixtures("grant_ref_data")

TODAY = date(2026, 8, 3)


async def _populated(client, headers, **overrides) -> tuple[str, str, str]:
    """An awarded application with a period, a measure and a recorded outcome."""
    application_id = await create_application(
        client, headers, amount_requested="30000", **overrides
    )
    await client.post(
        f"/api/v1/grants/applications/{application_id}/status",
        json={"status": "awarded", "amount_awarded": "27500"},
        headers=headers,
    )
    period = (
        await client.post(
            f"/api/v1/grants/applications/{application_id}/reporting-periods",
            json={
                "label": "Year 1",
                "period_start": "2026-04-01",
                "period_end": "2027-03-31",
                "due_date": "2027-04-30",
            },
            headers=headers,
        )
    ).json()
    measure = (
        await client.post(
            f"/api/v1/grants/applications/{application_id}/measures",
            json={"name": "Beneficiaries reached", "unit": "people", "target": "250"},
            headers=headers,
        )
    ).json()
    await client.put(
        f"/api/v1/grants/applications/{application_id}"
        f"/reporting-periods/{period['id']}/outcomes/{measure['id']}",
        json={"value": "180", "narrative": "Reached 180 people."},
        headers=headers,
    )
    return application_id, period["id"], measure["id"]


async def test_gather_collects_the_whole_spine(client):
    tenant, headers = await make_tenant(client, "gather")
    application_id, period_id, measure_id = await _populated(client, headers)

    async with db.tenant_tx(tenant.owner_id, tenant.id) as conn:
        pack = await gather(
            conn,
            UUID(application_id),
            "monitoring_report",
            {"reporting_period_id": period_id},
            TODAY,
        )

    assert pack.application.status == "awarded"
    assert pack.application.amount_awarded == 27500.0  # Decimal -> float at the edge
    assert len(pack.stages) == 7
    assert len(pack.tasks) == 28
    assert len(pack.conditions) == 6  # seeded on award
    assert [p.label for p in pack.periods] == ["Year 1"]
    assert [m.name for m in pack.measures] == ["Beneficiaries reached"]
    assert pack.target_period_id == UUID(period_id)

    progress = pack.measure_progress(UUID(period_id))
    assert progress[0]["value"] == 180.0
    assert progress[0]["share"] == 180 / 250


async def test_gather_rejects_a_period_from_another_application(client):
    """The engine must not draft a return for an obligation that belongs to a
    different bid — the figures would be right and the document wrong."""
    tenant, headers = await make_tenant(client, "wrongperiod")
    first, period_id, _ = await _populated(client, headers)
    second = await create_application(client, headers, title="Other bid")

    async with db.tenant_tx(tenant.owner_id, tenant.id) as conn:
        with pytest.raises(ValueError, match="Reporting period not found"):
            await gather(
                conn,
                UUID(second),
                "monitoring_report",
                {"reporting_period_id": period_id},
                TODAY,
            )


async def test_gather_attaches_the_catalogue_row_and_marks_it_stale(client):
    """The seeded catalogue ships unverified and stale (ASSUMPTIONS #24), so a
    bid built on one carries the page-one warning."""
    tenant, headers = await make_tenant(client, "cat")
    application_id = await create_application(
        client, headers, programme_key="tnlcf_awards_for_all_england"
    )

    async with db.tenant_tx(tenant.owner_id, tenant.id) as conn:
        pack = await gather(conn, UUID(application_id), "funding_application", {}, TODAY)

    assert pack.catalogue is not None
    assert pack.catalogue.status == "unverified"
    assert pack.catalogue.stale is True
    warning = pack.warning_block()
    assert warning is not None and "confirm the current criteria" in warning


async def test_gather_is_tenant_isolated(client):
    """B's application id under A's tenant transaction must not resolve — RLS
    is the boundary, not an app-level check."""
    a, a_headers = await make_tenant(client, "gwa")
    b, b_headers = await make_tenant(client, "gwb")
    b_application, _, _ = await _populated(client, b_headers)

    async with db.tenant_tx(a.owner_id, a.id) as conn:
        with pytest.raises(ValueError, match="Application not found"):
            await gather(conn, UUID(b_application), "case_for_support", {}, TODAY)


async def test_gather_rejects_an_unknown_kind(client):
    tenant, headers = await make_tenant(client, "badkind")
    application_id = await create_application(client, headers)
    async with db.tenant_tx(tenant.owner_id, tenant.id) as conn:
        with pytest.raises(ValueError, match="Unknown draft kind"):
            await gather(conn, UUID(application_id), "not_a_kind", {}, TODAY)


async def test_scope_weights_follow_the_linked_project(client):
    """The cross-module soft link earning its keep: a bid tied to a project
    boosts that project's vault documents (ASSUMPTIONS #23)."""
    tenant, headers = await make_tenant(client, "scope")
    linked = await create_application(client, headers, project_id=str(tenant.project_id))
    standalone = await create_application(client, headers, title="No project")

    async with db.tenant_tx(tenant.owner_id, tenant.id) as conn:
        await conn.execute(
            "update documents set project_id = $1 where id = $2",
            tenant.project_id,
            tenant.document_id,
        )
        linked_weights = await scope_weights(conn, UUID(linked))
        standalone_weights = await scope_weights(conn, UUID(standalone))

    assert linked_weights.get(tenant.document_id) == 1.5
    # No project: retrieve across the whole vault unweighted, which is right —
    # a charity's need evidence is rarely filed under one project.
    assert standalone_weights == {}


async def test_gather_survives_an_application_with_nothing_recorded(client):
    """A brand-new application must still produce a pack — the draft says
    [TO CONFIRM] rather than the job crashing."""
    tenant = await seed_tenant(client, f"bare-{uuid4().hex[:6]}")
    async with db.tenant_tx(tenant.owner_id, tenant.id) as conn:
        await conn.execute(
            """update tenants set features = features || '{"grants": true}' where id = $1""",
            tenant.id,
        )
    headers = auth(tenant.owner_id, tenant.id)
    application_id = await create_application(client, headers)

    async with db.tenant_tx(tenant.owner_id, tenant.id) as conn:
        pack = await gather(conn, UUID(application_id), "case_for_support", {}, TODAY)

    assert pack.measures == [] and pack.outcomes == []
    assert pack.catalogue is None
    assert pack.warning_block() is None
    assert pack.record_counts()["impact measures"] == 0
