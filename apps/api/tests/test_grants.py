"""Grantwork: feature gate, spine seeding, gates, registry, award conditions,
the reporting calendar, outcomes, and cross-tenant direct-object references.
"""

import json
from datetime import date, timedelta
from uuid import uuid4

import asyncpg
import pytest

from app.db import db
from app.grants.seeds import (
    FIXTURES,
    SEED_STATUS,
    seed_funder_catalogue,
    seed_reference_data,
)
from tests.conftest import OWNER_URL, auth, seed_tenant

pytestmark = pytest.mark.usefixtures("grant_ref_data")

TEMPLATE_STAGES = 7
TEMPLATE_TASKS = 28
TEMPLATE_DOCS = 11
TEMPLATE_CONDITIONS = 6


@pytest.fixture(scope="session")
async def grant_ref_data(test_database):
    conn = await asyncpg.connect(OWNER_URL)
    try:
        await seed_reference_data(conn)
        # Two catalogue rows so the staleness derivation has both sides. Real
        # funder data is seeded separately — these exist to prove `stale` is
        # computed from next_review, not stored.
        await conn.execute(
            """
            insert into grant_ref_funders (key, name, funder, funder_type, nations, kind,
                                           eligibility, status, last_verified, next_review)
            values ('fresh_fund', 'Fresh Fund', 'Test Trust', 'trust', '{england}', 'revenue',
                    'Registered charities', 'open', current_date, current_date + 90),
                   ('stale_fund', 'Stale Fund', 'Test Trust', 'trust', '{testland}', 'capital',
                    'Registered charities', 'open', current_date - 200, current_date - 10)
            on conflict (key) do nothing
            """
        )
    finally:
        await conn.close()


async def enable_module(tenant) -> None:
    async with db.tenant_tx(tenant.owner_id, tenant.id) as conn:
        await conn.execute(
            """update tenants set features = features || '{"grants": true}' where id = $1""",
            tenant.id,
        )


async def make_tenant(client, prefix: str):
    tenant = await seed_tenant(client, f"{prefix}-{uuid4().hex[:6]}")
    await enable_module(tenant)
    return tenant, auth(tenant.owner_id, tenant.id)


async def create_application(client, headers, **overrides) -> str:
    body = {"title": "Community garden project", **overrides}
    resp = await client.post("/api/v1/grants/applications", json=body, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


# -- feature gate ------------------------------------------------------------


async def test_every_route_404s_without_the_flag(client):
    """A module the tenant has not bought is invisible, not forbidden."""
    tenant = await seed_tenant(client, f"nogrant-{uuid4().hex[:6]}")
    headers = auth(tenant.owner_id, tenant.id)
    for method, path in [
        ("GET", "/api/v1/grants/applications"),
        ("POST", "/api/v1/grants/applications"),
        ("GET", "/api/v1/grants/funders"),
        ("GET", "/api/v1/grants/funder-catalogue"),
        ("GET", "/api/v1/grants/reporting-calendar"),
        ("GET", f"/api/v1/grants/applications/{uuid4()}/stages"),
    ]:
        resp = await client.request(method, path, headers=headers, json={"title": "x"})
        assert resp.status_code == 404, f"{method} {path} -> {resp.status_code}"


# -- spine seeding -----------------------------------------------------------


async def test_create_seeds_the_full_spine(client):
    tenant, headers = await make_tenant(client, "seed")
    resp = await client.post(
        "/api/v1/grants/applications",
        json={"title": "Youth work programme", "amount_requested": "25000"},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["stage_current"] == "case"
    assert body["seeded"] == {
        "stages": TEMPLATE_STAGES,
        "tasks": TEMPLATE_TASKS,
        "doc_types": TEMPLATE_DOCS,
    }

    application_id = body["id"]
    stages = (
        await client.get(f"/api/v1/grants/applications/{application_id}/stages", headers=headers)
    ).json()
    assert [s["stage_key"] for s in stages] == [
        "case",
        "prospect",
        "apply",
        "decision",
        "deliver",
        "monitor",
        "evaluate",
    ]
    assert stages[0]["status"] == "active"
    assert all(s["status"] == "pending" for s in stages[1:])
    assert all(item["done"] is False for item in stages[0]["gate"])

    docs = (
        await client.get(f"/api/v1/grants/applications/{application_id}/documents", headers=headers)
    ).json()
    draftable = {d["doc_type_key"] for d in docs if d["ai_draftable"]}
    assert draftable == {
        "case_for_support",
        "funding_application",
        "monitoring_report",
        "impact_evaluation",
    }
    assert all(d["status"] == "required" for d in docs)


async def test_unknown_application_type_is_a_seeding_error(client):
    tenant, headers = await make_tenant(client, "notype")
    resp = await client.post(
        "/api/v1/grants/applications",
        json={"title": "Mystery", "application_type": "no_such_template"},
        headers=headers,
    )
    assert resp.status_code == 503
    assert resp.json()["error"]["code"] == "not_seeded"


# -- gates -------------------------------------------------------------------


async def test_gate_signoff_requires_completion_or_exceptions(client):
    tenant, headers = await make_tenant(client, "gate")
    application_id = await create_application(client, headers)
    stages = (
        await client.get(f"/api/v1/grants/applications/{application_id}/stages", headers=headers)
    ).json()
    stage = stages[0]

    resp = await client.post(
        f"/api/v1/grants/applications/{application_id}/stages/{stage['id']}/signoff",
        json={},
        headers=headers,
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "gate_incomplete"

    resp = await client.post(
        f"/api/v1/grants/applications/{application_id}/stages/{stage['id']}/signoff",
        json={"exceptions": "Evidence follows next week"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "passed"

    # Advancing moves the pointer and activates the next stage.
    detail = (
        await client.get(f"/api/v1/grants/applications/{application_id}", headers=headers)
    ).json()
    assert detail["stage_current"] == "prospect"

    # A signed-off gate is frozen.
    resp = await client.post(
        f"/api/v1/grants/applications/{application_id}/stages/{stage['id']}/gate/c1/toggle",
        headers=headers,
    )
    assert resp.status_code == 409


async def test_only_the_active_stage_can_be_signed_off(client):
    tenant, headers = await make_tenant(client, "skip")
    application_id = await create_application(client, headers)
    stages = (
        await client.get(f"/api/v1/grants/applications/{application_id}/stages", headers=headers)
    ).json()
    resp = await client.post(
        f"/api/v1/grants/applications/{application_id}/stages/{stages[3]['id']}/signoff",
        json={"exceptions": "trying to skip ahead"},
        headers=headers,
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "stage_not_active"


async def test_doc_gate_items_follow_the_registry(client):
    """A doc-kind gate item cannot be toggled by hand, and flips itself when
    the registry entry it names reaches final."""
    tenant, headers = await make_tenant(client, "docgate")
    application_id = await create_application(client, headers)

    resp = await client.post(
        f"/api/v1/grants/applications/{application_id}/stages/"
        f"{(await _stage(client, headers, application_id, 'case'))['id']}/gate/c3/toggle",
        headers=headers,
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "computed_item"

    docs = (
        await client.get(f"/api/v1/grants/applications/{application_id}/documents", headers=headers)
    ).json()
    case_doc = next(d for d in docs if d["doc_type_key"] == "case_for_support")
    resp = await client.patch(
        f"/api/v1/grants/applications/{application_id}/documents/{case_doc['id']}",
        json={"status": "final"},
        headers=headers,
    )
    assert resp.status_code == 200

    stage = await _stage(client, headers, application_id, "case")
    item = next(i for i in stage["gate"] if i["id"] == "c3")
    assert item["done"] is True

    # And back again when the registry regresses — gates can never disagree.
    await client.patch(
        f"/api/v1/grants/applications/{application_id}/documents/{case_doc['id']}",
        json={"status": "drafting"},
        headers=headers,
    )
    stage = await _stage(client, headers, application_id, "case")
    assert next(i for i in stage["gate"] if i["id"] == "c3")["done"] is False


# -- award and conditions ----------------------------------------------------


async def test_award_seeds_the_standard_conditions_once(client):
    tenant, headers = await make_tenant(client, "award")
    application_id = await create_application(client, headers, amount_requested="30000")

    resp = await client.post(
        f"/api/v1/grants/applications/{application_id}/status",
        json={"status": "awarded"},
        headers=headers,
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "amount_required"

    resp = await client.post(
        f"/api/v1/grants/applications/{application_id}/status",
        json={"status": "awarded", "amount_awarded": "27500", "decision_at": "2026-08-01"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "awarded"
    assert float(resp.json()["amount_awarded"]) == 27500.0

    conditions = (
        await client.get(
            f"/api/v1/grants/applications/{application_id}/conditions", headers=headers
        )
    ).json()
    assert len(conditions) == TEMPLATE_CONDITIONS
    assert conditions[0]["pre_drawdown"] is True  # pre-drawdown conditions sort first

    # Re-recording the award must not duplicate the register.
    await client.post(
        f"/api/v1/grants/applications/{application_id}/status",
        json={"status": "awarded", "amount_awarded": "27500"},
        headers=headers,
    )
    again = (
        await client.get(
            f"/api/v1/grants/applications/{application_id}/conditions", headers=headers
        )
    ).json()
    assert len(again) == TEMPLATE_CONDITIONS


async def test_pipeline_applications_have_no_conditions(client):
    """Conditions come from an offer. An application still being written has
    no offer, so seeding them at creation would be inventing obligations."""
    tenant, headers = await make_tenant(client, "nocond")
    application_id = await create_application(client, headers)
    conditions = (
        await client.get(
            f"/api/v1/grants/applications/{application_id}/conditions", headers=headers
        )
    ).json()
    assert conditions == []


async def test_submitting_queues_a_claims_harvest(client, monkeypatch):
    jobs: list[str] = []

    class _HarvestQueue:
        async def enqueue_harvest(self, tenant_id, application_id, user_id):
            jobs.append(str(application_id))

    monkeypatch.setattr("app.routers.grants.applications.ingest_queue", _HarvestQueue())
    tenant, headers = await make_tenant(client, "harvestok")
    application_id = await create_application(client, headers)
    resp = await client.post(
        f"/api/v1/grants/applications/{application_id}/status",
        json={"status": "submitted"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "submitted"
    assert resp.json()["harvest_queued"] is True
    assert jobs == [application_id]


async def test_submit_still_succeeds_when_harvest_cannot_queue(client):
    """Redis is disabled in this suite, so enqueue raises. Recording the
    submission must not."""
    tenant, headers = await make_tenant(client, "harvestfail")
    application_id = await create_application(client, headers)
    resp = await client.post(
        f"/api/v1/grants/applications/{application_id}/status",
        json={"status": "submitted"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "submitted"
    assert resp.json()["harvest_queued"] is False


# -- portfolio ---------------------------------------------------------------


async def test_portfolio_reports_derived_figures(client):
    tenant, headers = await make_tenant(client, "folio")
    live = await create_application(client, headers, amount_requested="40000")
    won = await create_application(client, headers, amount_requested="10000")
    await client.post(
        f"/api/v1/grants/applications/{won}/status",
        json={"status": "awarded", "amount_awarded": "9000"},
        headers=headers,
    )
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    await client.post(
        f"/api/v1/grants/applications/{won}/reporting-periods",
        json={
            "label": "Year 1",
            "period_start": "2026-04-01",
            "period_end": "2027-03-31",
            "due_date": yesterday,
        },
        headers=headers,
    )

    rows = (await client.get("/api/v1/grants/applications", headers=headers)).json()
    by_id = {r["id"]: r for r in rows}
    # Undecided: the ask discounted by its stage weight (case = 0.05).
    assert by_id[live]["weighted_value"] == pytest.approx(2000.0)
    # Awarded: what was actually offered, not the ask.
    assert by_id[won]["weighted_value"] == pytest.approx(9000.0)
    assert by_id[won]["open_conditions"] == TEMPLATE_CONDITIONS
    assert by_id[won]["overdue_returns"] == 1
    assert by_id[won]["next_return_due"] == yesterday

    filtered = (
        await client.get("/api/v1/grants/applications?status=awarded", headers=headers)
    ).json()
    assert [r["id"] for r in filtered] == [won]


# -- reporting calendar and outcomes -----------------------------------------


async def test_reporting_calendar_spans_applications_and_rags_by_due_date(client):
    tenant, headers = await make_tenant(client, "cal")
    application_id = await create_application(client, headers)
    for label, due in [
        ("Overdue return", date.today() - timedelta(days=5)),
        ("Due soon", date.today() + timedelta(days=10)),
        ("Far off", date.today() + timedelta(days=200)),
    ]:
        resp = await client.post(
            f"/api/v1/grants/applications/{application_id}/reporting-periods",
            json={
                "label": label,
                "period_start": "2026-04-01",
                "period_end": "2027-03-31",
                "due_date": due.isoformat(),
            },
            headers=headers,
        )
        assert resp.status_code == 201, resp.text

    calendar = (await client.get("/api/v1/grants/reporting-calendar", headers=headers)).json()
    rags = {row["label"]: row["rag"] for row in calendar}
    # The calendar spans every application in the tenant, so the fixture's own
    # seeded period is legitimately here too — assert on ours specifically.
    assert {k: v for k, v in rags.items() if k in ("Overdue return", "Due soon", "Far off")} == {
        "Overdue return": "red",
        "Due soon": "amber",
        "Far off": "green",
    }
    assert calendar[0]["label"] == "Overdue return"  # soonest first
    assert calendar[0]["overdue"] is True
    assert calendar[0]["application_title"] == "Community garden project"

    # An accepted return leaves the calendar entirely.
    period_id = calendar[0]["id"]
    await client.patch(
        f"/api/v1/grants/applications/{application_id}/reporting-periods/{period_id}",
        json={"status": "accepted", "accepted_at": date.today().isoformat()},
        headers=headers,
    )
    calendar = (await client.get("/api/v1/grants/reporting-calendar", headers=headers)).json()
    assert "Overdue return" not in {row["label"] for row in calendar}


async def test_duplicate_period_label_is_rejected(client):
    tenant, headers = await make_tenant(client, "duppd")
    application_id = await create_application(client, headers)
    body = {"label": "Year 1", "period_start": "2026-04-01", "period_end": "2027-03-31"}
    assert (
        await client.post(
            f"/api/v1/grants/applications/{application_id}/reporting-periods",
            json=body,
            headers=headers,
        )
    ).status_code == 201
    resp = await client.post(
        f"/api/v1/grants/applications/{application_id}/reporting-periods",
        json=body,
        headers=headers,
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "duplicate_period"


async def test_period_must_not_end_before_it_starts(client):
    tenant, headers = await make_tenant(client, "badpd")
    application_id = await create_application(client, headers)
    resp = await client.post(
        f"/api/v1/grants/applications/{application_id}/reporting-periods",
        json={"label": "Backwards", "period_start": "2027-03-31", "period_end": "2026-04-01"},
        headers=headers,
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "bad_period"


async def test_recording_an_outcome_upserts(client):
    """One value per measure per period: re-recording corrects, never
    duplicates — the figures a monitoring return renders come from here."""
    tenant, headers = await make_tenant(client, "outcome")
    application_id = await create_application(client, headers)
    measure = (
        await client.post(
            f"/api/v1/grants/applications/{application_id}/measures",
            json={"name": "Beneficiaries reached", "unit": "people", "target": "250"},
            headers=headers,
        )
    ).json()
    period = (
        await client.post(
            f"/api/v1/grants/applications/{application_id}/reporting-periods",
            json={"label": "Year 1", "period_start": "2026-04-01", "period_end": "2027-03-31"},
            headers=headers,
        )
    ).json()
    url = (
        f"/api/v1/grants/applications/{application_id}"
        f"/reporting-periods/{period['id']}/outcomes/{measure['id']}"
    )

    resp = await client.put(url, json={"value": "180", "narrative": "First year"}, headers=headers)
    assert resp.status_code == 200
    assert float(resp.json()["value"]) == 180.0
    assert resp.json()["measure_name"] == "Beneficiaries reached"
    assert float(resp.json()["target"]) == 250.0

    resp = await client.put(url, json={"value": "195", "narrative": "Corrected"}, headers=headers)
    assert resp.status_code == 200
    assert float(resp.json()["value"]) == 195.0

    outcomes = (
        await client.get(
            f"/api/v1/grants/applications/{application_id}"
            f"/reporting-periods/{period['id']}/outcomes",
            headers=headers,
        )
    ).json()
    assert len(outcomes) == 1
    assert outcomes[0]["narrative"] == "Corrected"


async def test_duplicate_measure_name_is_rejected(client):
    tenant, headers = await make_tenant(client, "dupms")
    application_id = await create_application(client, headers)
    body = {"name": "Meals served", "unit": "meals"}
    assert (
        await client.post(
            f"/api/v1/grants/applications/{application_id}/measures", json=body, headers=headers
        )
    ).status_code == 201
    resp = await client.post(
        f"/api/v1/grants/applications/{application_id}/measures", json=body, headers=headers
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "duplicate_measure"


# -- funders and catalogue ---------------------------------------------------


async def test_funder_crud_and_application_count(client):
    tenant, headers = await make_tenant(client, "funder")
    funder = (
        await client.post(
            "/api/v1/grants/funders",
            json={"name": "Borough Community Foundation", "kind": "community_foundation"},
            headers=headers,
        )
    ).json()
    assert funder["application_count"] == 0

    application_id = await create_application(client, headers, funder_id=funder["id"])
    refreshed = (await client.get(f"/api/v1/grants/funders/{funder['id']}", headers=headers)).json()
    assert refreshed["application_count"] == 1

    resp = await client.patch(
        f"/api/v1/grants/funders/{funder['id']}",
        json={"relationship": "funder", "contact_email": "grants@example.org"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["relationship"] == "funder"

    # Deleting a funder detaches its bids rather than deleting them.
    assert (
        await client.delete(f"/api/v1/grants/funders/{funder['id']}", headers=headers)
    ).status_code == 204
    detail = (
        await client.get(f"/api/v1/grants/applications/{application_id}", headers=headers)
    ).json()
    assert detail["funder_id"] is None


async def test_catalogue_staleness_is_derived_from_the_review_date(client):
    tenant, headers = await make_tenant(client, "cat")
    rows = (await client.get("/api/v1/grants/funder-catalogue", headers=headers)).json()
    by_key = {r["key"]: r for r in rows}
    assert by_key["fresh_fund"]["stale"] is False
    assert by_key["stale_fund"]["stale"] is True

    # `testland` is a fixture-only nation, so this asserts the filter rather
    # than the seeded catalogue's coverage.
    filtered = (
        await client.get("/api/v1/grants/funder-catalogue?nation=testland", headers=headers)
    ).json()
    assert [r["key"] for r in filtered] == ["stale_fund"]


# -- cross-module link and cross-tenant references ---------------------------


async def test_application_links_to_a_core_project(client):
    """The soft link that ties a Groundwork development project to the bid
    that funds it (ASSUMPTIONS #23)."""
    tenant, headers = await make_tenant(client, "link")
    application_id = await create_application(client, headers, project_id=str(tenant.project_id))
    detail = (
        await client.get(f"/api/v1/grants/applications/{application_id}", headers=headers)
    ).json()
    assert detail["project_id"] == str(tenant.project_id)
    assert detail["project_name"] is not None


async def test_cross_tenant_object_references_404(client):
    a, headers = await make_tenant(client, "grca")
    b, _ = await make_tenant(client, "grcb")

    for method, path in [
        ("GET", f"/api/v1/grants/applications/{b.application_id}"),
        ("PATCH", f"/api/v1/grants/applications/{b.application_id}"),
        ("DELETE", f"/api/v1/grants/applications/{b.application_id}"),
        ("POST", f"/api/v1/grants/applications/{b.application_id}/status"),
        ("GET", f"/api/v1/grants/applications/{b.application_id}/stages"),
        ("GET", f"/api/v1/grants/applications/{b.application_id}/tasks"),
        ("GET", f"/api/v1/grants/applications/{b.application_id}/documents"),
        ("GET", f"/api/v1/grants/applications/{b.application_id}/conditions"),
        ("GET", f"/api/v1/grants/applications/{b.application_id}/reporting-periods"),
        ("GET", f"/api/v1/grants/applications/{b.application_id}/measures"),
        ("GET", f"/api/v1/grants/funders/{b.funder_id}"),
        ("PATCH", f"/api/v1/grants/funders/{b.funder_id}"),
        ("DELETE", f"/api/v1/grants/funders/{b.funder_id}"),
    ]:
        resp = await client.request(
            method,
            path,
            headers=headers,
            json={"title": "x", "status": "withdrawn", "name": "x"},
        )
        assert resp.status_code == 404, f"{method} {path} -> {resp.status_code}"

    # FK checks bypass RLS, so these are the app-level guards that stop A
    # attaching B's funder or B's project to A's own application.
    resp = await client.post(
        "/api/v1/grants/applications",
        json={"title": "Smuggle", "funder_id": str(b.funder_id)},
        headers=headers,
    )
    assert resp.status_code == 404
    resp = await client.post(
        "/api/v1/grants/applications",
        json={"title": "Smuggle", "project_id": str(b.project_id)},
        headers=headers,
    )
    assert resp.status_code == 404

    own = await create_application(client, headers)
    resp = await client.patch(
        f"/api/v1/grants/applications/{own}",
        json={"funder_id": str(b.funder_id)},
        headers=headers,
    )
    assert resp.status_code == 404

    # B's own rows are untouched by any of it.
    b_headers = auth(b.owner_id, b.id)
    rows = (await client.get("/api/v1/grants/applications", headers=b_headers)).json()
    assert str(b.application_id) in {r["id"] for r in rows}


async def test_a_period_from_another_application_is_not_writable(client):
    """Both ids are checked together: same tenant, wrong parent must 404."""
    tenant, headers = await make_tenant(client, "wrongparent")
    first = await create_application(client, headers)
    second = await create_application(client, headers, title="Second bid")
    period = (
        await client.post(
            f"/api/v1/grants/applications/{first}/reporting-periods",
            json={"label": "Year 1", "period_start": "2026-04-01", "period_end": "2027-03-31"},
            headers=headers,
        )
    ).json()
    measure = (
        await client.post(
            f"/api/v1/grants/applications/{second}/measures",
            json={"name": "Sessions run"},
            headers=headers,
        )
    ).json()
    resp = await client.put(
        f"/api/v1/grants/applications/{second}/reporting-periods/{period['id']}"
        f"/outcomes/{measure['id']}",
        json={"value": "10"},
        headers=headers,
    )
    assert resp.status_code == 404


async def _stage(client, headers, application_id: str, stage_key: str) -> dict:
    stages = (
        await client.get(f"/api/v1/grants/applications/{application_id}/stages", headers=headers)
    ).json()
    return next(s for s in stages if s["stage_key"] == stage_key)


# -- the seeded funder catalogue ---------------------------------------------


async def test_seeded_catalogue_rows_ship_unverified_and_stale(client):
    """The catalogue is compiled from model knowledge, not checked by anyone.

    So every seeded row must arrive in the state that makes both existing
    safety mechanisms fire: `status='unverified'` puts the first-page warning
    block on any draft built from it, and a `next_review` on or before today
    badges it in the UI. A row that shipped `open` and fresh would present
    unchecked funder facts to a charity with nothing attached saying so.
    """
    tenant, headers = await make_tenant(client, "seedcat")
    rows = (await client.get("/api/v1/grants/funder-catalogue", headers=headers)).json()
    seeded = {r["key"]: r for r in rows}
    fixture_keys = {row["key"] for row in _fixture()["funders"]}
    assert fixture_keys, "the catalogue fixture is empty"

    for key in fixture_keys:
        row = seeded[key]
        assert row["status"] == SEED_STATUS, f"{key}: seeded rows must not claim to be open"
        assert row["stale"] is True, f"{key}: seeded rows must arrive due for review"
        assert row["notes"], f"{key}: a seeded row must say where it came from"
        assert row["route_url"], f"{key}: verification needs somewhere to go"


def test_the_fixture_itself_cannot_ship_as_verified():
    """Guards the data file rather than the database.

    `last_verified` is only meaningful if it records something a person did.
    Raising it — or setting `status='open'` — in the fixture would be typing
    a verification instead of performing one, which is exactly the failure
    this catalogue's staleness machinery exists to prevent.
    """
    for row in _fixture()["funders"]:
        assert row["status"] == SEED_STATUS, f"{row['key']}: fixture must ship unverified"
        assert row["next_review"] == row["last_verified"], (
            f"{row['key']}: a seeded row is due for review immediately"
        )
        assert "UNVERIFIED SEED" in row["notes"] or "PLACEHOLDER" in row["notes"], (
            f"{row['key']}: the row must declare its own provenance"
        )


async def test_reseeding_never_demotes_a_verified_row(client):
    """Re-running the seed refreshes descriptive text but must not reset the
    verification an operator performed — otherwise every content correction
    silently un-verifies the whole catalogue."""
    key = "local_community_foundation"
    conn = await asyncpg.connect(OWNER_URL)
    try:
        await conn.execute(
            """
            update grant_ref_funders
            set status = 'open', next_review = current_date + 90, name = 'Operator edited'
            where key = $1
            """,
            key,
        )
        await seed_funder_catalogue(conn)
        row = await conn.fetchrow("select * from grant_ref_funders where key = $1", key)
        assert row["status"] == "open", "re-seeding demoted a verified row"
        assert row["next_review"] > date.today(), "re-seeding reset the review date"
        # Descriptive columns *do* refresh — that is the point of re-seeding.
        assert row["name"] != "Operator edited"
    finally:
        await conn.execute(
            """
            update grant_ref_funders set status = $2, next_review = last_verified
            where key = $1
            """,
            key,
            SEED_STATUS,
        )
        await conn.close()


def _fixture() -> dict:
    return json.loads((FIXTURES / "funders.json").read_text())


# -- draft jobs --------------------------------------------------------------


class _FakeQueue:
    """Records enqueues instead of reaching Redis (which conftest disables)."""

    def __init__(self):
        self.jobs = []

    async def enqueue_grant_draft(self, tenant_id, application_id, job_id, user_id):
        self.jobs.append(("draft", str(application_id), str(job_id)))

    async def enqueue_impact_card(self, tenant_id, application_id, job_id, user_id):
        self.jobs.append(("impact_card", str(application_id), str(job_id)))


@pytest.fixture
def queue(monkeypatch):
    fake = _FakeQueue()
    monkeypatch.setattr("app.routers.grants.drafts.ingest_queue", fake)
    return fake


async def test_submitting_a_draft_queues_it_and_polls(client, queue):
    tenant, headers = await make_tenant(client, "draft")
    application_id = await create_application(client, headers)

    resp = await client.post(
        f"/api/v1/grants/applications/{application_id}/drafts",
        json={"kind": "case_for_support", "instructions": "Emphasise the youth work."},
        headers=headers,
    )
    assert resp.status_code == 202, resp.text
    job = resp.json()
    assert job["status"] == "queued"
    assert job["kind"] == "case_for_support"
    assert queue.jobs == [("draft", application_id, job["id"])]

    polled = (await client.get(f"/api/v1/grants/drafts/{job['id']}", headers=headers)).json()
    assert polled["id"] == job["id"]
    assert polled["download_url"] is None  # nothing rendered yet

    active = (
        await client.get(f"/api/v1/grants/applications/{application_id}/drafts", headers=headers)
    ).json()
    assert [j["id"] for j in active] == [job["id"]]


async def test_one_draft_per_kind_in_flight(client, queue):
    """A second click mid-draft doubles the model spend for an identical
    result, since the register would only version it."""
    tenant, headers = await make_tenant(client, "inflight")
    application_id = await create_application(client, headers)
    url = f"/api/v1/grants/applications/{application_id}/drafts"

    assert (
        await client.post(url, json={"kind": "case_for_support"}, headers=headers)
    ).status_code == 202
    resp = await client.post(url, json={"kind": "case_for_support"}, headers=headers)
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "draft_in_flight"

    # A different kind is unaffected.
    assert (
        await client.post(url, json={"kind": "impact_evaluation"}, headers=headers)
    ).status_code == 202


async def test_monitoring_report_requires_a_period_of_this_application(client, queue):
    tenant, headers = await make_tenant(client, "mrperiod")
    application_id = await create_application(client, headers)
    other = await create_application(client, headers, title="Other bid")
    url = f"/api/v1/grants/applications/{application_id}/drafts"

    resp = await client.post(url, json={"kind": "monitoring_report"}, headers=headers)
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "period_required"

    foreign = (
        await client.post(
            f"/api/v1/grants/applications/{other}/reporting-periods",
            json={"label": "Year 1", "period_start": "2026-04-01", "period_end": "2027-03-31"},
            headers=headers,
        )
    ).json()
    resp = await client.post(
        url,
        json={"kind": "monitoring_report", "reporting_period_id": foreign["id"]},
        headers=headers,
    )
    assert resp.status_code == 404

    own = (
        await client.post(
            f"/api/v1/grants/applications/{application_id}/reporting-periods",
            json={"label": "Year 1", "period_start": "2026-04-01", "period_end": "2027-03-31"},
            headers=headers,
        )
    ).json()
    resp = await client.post(
        url, json={"kind": "monitoring_report", "reporting_period_id": own["id"]}, headers=headers
    )
    assert resp.status_code == 202


async def test_impact_card_is_its_own_job_kind(client, queue):
    tenant, headers = await make_tenant(client, "card")
    application_id = await create_application(client, headers)
    resp = await client.post(
        f"/api/v1/grants/applications/{application_id}/impact-card", headers=headers
    )
    assert resp.status_code == 202
    assert resp.json()["kind"] == "impact_card"
    assert queue.jobs == [("impact_card", application_id, resp.json()["id"])]


async def test_the_card_is_not_a_draft_kind_clients_can_ask_for(client, queue):
    """`impact_card` is a valid job row but not a valid DraftIn kind — it goes
    through its own route, because it is an export rather than a draft."""
    tenant, headers = await make_tenant(client, "cardkind")
    application_id = await create_application(client, headers)
    resp = await client.post(
        f"/api/v1/grants/applications/{application_id}/drafts",
        json={"kind": "impact_card"},
        headers=headers,
    )
    assert resp.status_code == 422


async def test_draft_jobs_are_tenant_scoped(client, queue):
    a, a_headers = await make_tenant(client, "dja")
    b, b_headers = await make_tenant(client, "djb")
    b_application = await create_application(client, b_headers)
    b_job = (
        await client.post(
            f"/api/v1/grants/applications/{b_application}/drafts",
            json={"kind": "case_for_support"},
            headers=b_headers,
        )
    ).json()

    resp = await client.get(f"/api/v1/grants/drafts/{b_job['id']}", headers=a_headers)
    assert resp.status_code == 404
    resp = await client.post(
        f"/api/v1/grants/applications/{b_application}/drafts",
        json={"kind": "case_for_support"},
        headers=a_headers,
    )
    assert resp.status_code == 404
