"""The claims register, and the three public registers that seed it.

Register clients are exercised against recorded payloads through
`httpx.MockTransport` — never live. The keys are blanked in conftest for the
same reason: a developer's .env must not turn this file into an integration
test against Companies House.
"""

import json
import sys
from datetime import date, timedelta
from pathlib import Path
from uuid import uuid4

import httpx
import pytest

from app.claims import registers
from app.claims.service import load_kinds, render_statement
from app.config import get_settings
from app.db import db
from tests.conftest import auth

# Worker CI has no Postgres, so the worker's DB-touching claims modules
# (asyncpg + pydantic only) are imported across the monorepo and exercised
# here — the same rule as the context gatherers, ASSUMPTIONS #13.
sys.path.append(str(Path(__file__).resolve().parents[2] / "worker"))

from worker.claims.extract import ExtractedFact  # noqa: E402
from worker.claims.facts import load_claims, save_proposals  # noqa: E402


@pytest.fixture
def register_keys(monkeypatch):
    """Configure all three registers.

    `get_settings` is lru_cached, so the cached instance is patched directly —
    clearing the cache would re-read the environment and lose everything else
    conftest set up.
    """
    settings = get_settings()
    monkeypatch.setattr(settings, "companies_house_api_key", "test-ch-key", raising=False)
    monkeypatch.setattr(settings, "charity_commission_api_key", "test-cc-key", raising=False)
    monkeypatch.setattr(settings, "oscr_api_key", "test-oscr-key", raising=False)
    return settings


COMPANY_PROFILE = {
    "company_name": "Riverside Community Trust",
    "company_number": "07123456",
    "type": "private-limited-guarant-nsc",
    "company_status": "active",
    "date_of_creation": "2011-03-04",
    "registered_office_address": {
        "address_line_1": "12 Meadow Lane",
        "locality": "Sheffield",
        "postal_code": "S1 2AB",
        "country": "England",
    },
    "accounts": {"next_made_up_to": "2026-03-31", "next_due": "2026-12-31"},
    "confirmation_statement": {"next_due": "2026-09-15"},
}

COMPANY_OFFICERS = {
    "items": [
        {
            "name": "FRY, Sarah",
            "officer_role": "director",
            "appointed_on": "2011-03-04",
            # Deliberately present in the recorded payload: the client must
            # read past these rather than store them.
            "date_of_birth": {"month": 4, "year": 1975},
            "nationality": "British",
            "occupation": "Accountant",
        },
        {"name": "OLD, Terry", "officer_role": "director", "resigned_on": "2020-01-01"},
        {"name": "SEC, Sam", "officer_role": "secretary", "appointed_on": "2012-01-01"},
    ]
}

CHARITY_DETAIL = {
    "charity_name": "Riverside Community Trust",
    "reg_charity_number": "1234567",
    "charity_company_registration_number": "07123456",
    "charity_type": "Charitable company",
    "charity_registration_status": "Registered",
    "date_of_registration": "2011-04-01",
    "charity_contact_address": {
        "address_line_1": "12 Meadow Lane",
        "locality": "Sheffield",
        "postal_code": "S1 2AB",
    },
    "charity_objects": "To advance community wellbeing in Sheffield.",
    "charity_activities": "Community meals, advice sessions and a repair cafe.",
    "latest_income": 847000,
    "latest_expenditure": 792000,
    "latest_acc_fin_period_end_date": "2026-03-31",
    "area_of_operation": "Sheffield, South Yorkshire",
    "who_what_where": [{"classification_description": "Older people"}],
}

CHARITY_TRUSTEES = [{"trustee_name": "Sarah Fry"}, {"trustee_name": "Ade Okafor"}]

OSCR_CHARITY = [
    {
        "charity_name": "Clyde Community Trust",
        "charity_number": "SC012345",
        "charity_id": "9911",
        "constitutional_form": "SCIO",
        "charity_status": "Registered",
        "registered_date": "2014-06-02",
        "principal_office": {"address_line_1": "4 Harbour Street", "postal_code": "G1 4AA"},
        "objectives": "To advance community development in Clydebank.",
        "year_end": "2026-03-31",
        "geographical_spread": "Glasgow, West Dunbartonshire",
        "trustees": [{"trustee_name": "Morag Dunn"}],
    }
]

OSCR_RETURNS = [
    {"year_end": "2026-03-31", "income": 210000, "expenditure": 198000, "staff": 6},
    {"year_end": "2025-03-31", "income": 185000, "expenditure": 180000},
]


def _transport(routes: dict[str, object]) -> httpx.MockTransport:
    """Route by path suffix, so a client's query string does not matter."""

    def handler(request: httpx.Request) -> httpx.Response:
        for suffix, payload in routes.items():
            if request.url.path.endswith(suffix):
                return httpx.Response(200, json=payload)
        return httpx.Response(404, json={})

    return httpx.MockTransport(handler)


async def _import(client, tenant, monkeypatch, route: str, fetcher_name: str, routes, number):
    """Drive one import route with its register client's HTTP mocked out."""
    real = getattr(registers, fetcher_name)
    transport = _transport(routes)

    async def patched(num: str, *, client=None):
        async with httpx.AsyncClient(transport=transport) as mock:
            return await real(num, client=mock)

    monkeypatch.setattr(f"app.routers.claims.{fetcher_name}", patched)
    return await client.post(
        f"/api/v1/claims/import/{route}",
        json={"number": number},
        headers=auth(tenant.owner_id, tenant.id),
    )


async def test_kinds_catalogue_is_seeded(client, two_tenants):
    a, _ = two_tenants
    resp = await client.get("/api/v1/claims/kinds", headers=auth(a.owner_id, a.id))
    assert resp.status_code == 200
    keys = {k["key"] for k in resp.json()}
    # The identity facts the whole activation story rests on.
    assert {"registered_name", "company_number", "charity_number", "trustee"} <= keys


async def test_companies_house_import_proposes_facts(
    client, two_tenants, register_keys, monkeypatch
):
    a, _ = two_tenants
    resp = await _import(
        client,
        a,
        monkeypatch,
        "companies-house",
        "fetch_companies_house",
        {"/officers": COMPANY_OFFICERS, "/company/07123456": COMPANY_PROFILE},
        "07123456",
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["register_key"] == "companies_house"
    assert body["inactive"] is False
    assert "07123456" in body["source_url"]

    by_kind = {c["kind"]: c for c in body["proposed"]}
    assert by_kind["company_number"]["statement"].endswith("company number 07123456.")
    # The register returns a type code; a claim has to read as English.
    assert by_kind["legal_form"]["value"] == (
        "a private company limited by guarantee without share capital"
    )
    assert by_kind["registered_office"]["value"] == "12 Meadow Lane, Sheffield, S1 2AB, England"

    # Every proposal waits for a person. That is the register's founding rule.
    assert {c["status"] for c in body["proposed"]} == {"proposed"}
    assert {c["source"] for c in body["proposed"]} == {"register"}

    # Identity facts age with the confirmation statement, finance with accounts.
    assert by_kind["company_number"]["next_review"] == "2026-09-15"
    assert by_kind["accounts_year_end"]["next_review"] == "2026-12-31"


async def test_companies_house_import_keeps_only_serving_directors(
    client, two_tenants, register_keys, monkeypatch
):
    """Resigned officers and secretaries are not the governing body.

    And the payload's date of birth, nationality and occupation must not
    survive the boundary — the cheapest place to not hold personal data is
    before it arrives.
    """
    a, _ = two_tenants
    resp = await _import(
        client,
        a,
        monkeypatch,
        "companies-house",
        "fetch_companies_house",
        {"/officers": COMPANY_OFFICERS, "/company/07123456": COMPANY_PROFILE},
        "07123456",
    )
    directors = [c for c in resp.json()["proposed"] if c["kind"] == "director"]
    assert [d["subject"] for d in directors] == ["FRY, Sarah"]

    stored = json.dumps(directors[0])
    for leaked in ("1975", "British", "Accountant", "date_of_birth"):
        assert leaked not in stored, f"{leaked} crossed the register boundary"


async def test_charity_commission_import_covers_finance_and_trustees(
    client, two_tenants, register_keys, monkeypatch
):
    a, _ = two_tenants
    resp = await _import(
        client,
        a,
        monkeypatch,
        "charity-commission",
        "fetch_charity_commission",
        {
            "/charitytrustees/1234567/0": CHARITY_TRUSTEES,
            "/allcharitydetailsV2/1234567/0": CHARITY_DETAIL,
        },
        "1234567",
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    by_kind = {c["kind"]: c for c in body["proposed"]}

    assert by_kind["annual_income"]["statement"] == (
        "The organisation's annual income was £847,000."
    )
    # Ten months after the 31 March year end is the E&W filing deadline.
    assert by_kind["annual_income"]["next_review"] == "2027-01-31"
    assert by_kind["charitable_objects"]["value"] == (
        "To advance community wellbeing in Sheffield."
    )

    trustees = sorted(c["subject"] for c in body["proposed"] if c["kind"] == "trustee")
    assert trustees == ["Ade Okafor", "Sarah Fry"]


async def test_oscr_import_gives_scotland_a_finance_series_and_headcount(
    client, two_tenants, register_keys, monkeypatch
):
    """The Scottish register is the richest of the three on finance.

    Its annual return carries a series of years — which is what `period`
    exists for — and staff numbers, which no other UK register publishes.
    """
    a, _ = two_tenants
    resp = await _import(
        client,
        a,
        monkeypatch,
        "oscr",
        "fetch_oscr",
        {"/annualreturns": OSCR_RETURNS, "/all_charities": OSCR_CHARITY},
        "SC012345",
    )
    assert resp.status_code == 200, resp.text
    proposed = resp.json()["proposed"]

    incomes = {c["period"]: c["value"] for c in proposed if c["kind"] == "annual_income"}
    assert incomes == {"2025/26": 210000.0, "2024/25": 185000.0}

    headcount = next(c for c in proposed if c["kind"] == "employees_headcount")
    assert headcount["value"] == 6
    assert headcount["statement"] == "The organisation employs 6 people."

    # Nine months after year end in Scotland, not ten.
    assert (
        incomes
        and next(c["next_review"] for c in proposed if c["kind"] == "annual_income") == "2026-12-31"
    )

    trustees = [c["subject"] for c in proposed if c["kind"] == "trustee"]
    assert trustees == ["Morag Dunn"]


async def test_oscr_import_survives_a_charity_with_no_annual_return(
    client, two_tenants, register_keys, monkeypatch
):
    """A charity too new to have filed still has a perfectly good entry.

    Losing the whole import over the richer half being absent would be absurd,
    so the returns call is best-effort.
    """
    a, _ = two_tenants
    resp = await _import(
        client,
        a,
        monkeypatch,
        "oscr",
        "fetch_oscr",
        {"/all_charities": OSCR_CHARITY},  # no /annualreturns route -> 404
        "SC012345",
    )
    assert resp.status_code == 200, resp.text
    kinds = {c["kind"] for c in resp.json()["proposed"]}
    assert "registered_name" in kinds
    assert "employees_headcount" not in kinds


async def test_dissolved_record_is_refused_until_asked_for(
    client, two_tenants, register_keys, monkeypatch
):
    """A dissolved company returns complete, plausible data.

    A bid asserting current registration from a dead record is the worst thing
    this feature could produce, so it takes a deliberate second ask.
    """
    a, _ = two_tenants
    dissolved = {**COMPANY_PROFILE, "company_status": "dissolved"}
    routes = {"/officers": COMPANY_OFFICERS, "/company/07123456": dissolved}

    resp = await _import(
        client, a, monkeypatch, "companies-house", "fetch_companies_house", routes, "07123456"
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "register_record_inactive"

    real = registers.fetch_companies_house
    transport = _transport(routes)

    async def patched(num: str, *, client=None):
        async with httpx.AsyncClient(transport=transport) as mock:
            return await real(num, client=mock)

    monkeypatch.setattr("app.routers.claims.fetch_companies_house", patched)
    resp = await client.post(
        "/api/v1/claims/import/companies-house",
        json={"number": "07123456", "allow_inactive": True},
        headers=auth(a.owner_id, a.id),
    )
    assert resp.status_code == 200
    assert resp.json()["inactive"] is True


async def test_reimport_reports_unchanged_rather_than_duplicating(
    client, two_tenants, register_keys, monkeypatch
):
    a, _ = two_tenants
    routes = {"/officers": COMPANY_OFFICERS, "/company/07123456": COMPANY_PROFILE}
    args = (client, a, monkeypatch, "companies-house", "fetch_companies_house", routes, "07123456")

    first = (await _import(*args)).json()
    assert first["unchanged"] == 0
    assert first["proposed"]

    second = (await _import(*args)).json()
    # Nothing moved at the register, so the second run has nothing to ask
    # about: it reports what it agreed with rather than putting the same
    # eleven questions in front of somebody again.
    assert second["proposed"] == []
    assert second["unchanged"] == len(first["proposed"])

    listed = (await client.get("/api/v1/claims", headers=auth(a.owner_id, a.id))).json()
    assert len([c for c in listed if c["kind"] == "company_number"]) == 1


async def test_reimport_surfaces_a_changed_figure(client, two_tenants, register_keys, monkeypatch):
    """The other half: when the register HAS moved, say so.

    A confirmed claim is not overwritten — a new proposal appears beside it, so
    somebody decides whether the register or the workspace is right.
    """
    a, _ = two_tenants
    headers = auth(a.owner_id, a.id)
    detail = {"/charitytrustees/1234567/0": [], "/allcharitydetailsV2/1234567/0": CHARITY_DETAIL}
    args = (client, a, monkeypatch, "charity-commission", "fetch_charity_commission")

    first = (await _import(*args, detail, "1234567")).json()
    income = next(c for c in first["proposed"] if c["kind"] == "annual_income")
    confirmed = await client.patch(
        f"/api/v1/claims/{income['id']}", json={"status": "confirmed"}, headers=headers
    )
    assert confirmed.status_code == 200

    moved = {**CHARITY_DETAIL, "latest_income": 912000}
    second = (
        await _import(
            *args,
            {"/charitytrustees/1234567/0": [], "/allcharitydetailsV2/1234567/0": moved},
            "1234567",
        )
    ).json()

    new_income = next(c for c in second["proposed"] if c["kind"] == "annual_income")
    assert new_income["statement"] == "The organisation's annual income was £912,000."
    assert new_income["status"] == "proposed"

    # The confirmed figure stands until somebody accepts the new one.
    still = (await client.get(f"/api/v1/claims/{income['id']}", headers=headers)).json()
    assert still["status"] == "confirmed"
    assert still["value"] == 847000


async def test_missing_key_says_which_register(client, two_tenants):
    """No key configured is a 503 naming the register, not a 500.

    This is the state a Scottish workspace is in until the OSCR approval comes
    back, so the message has to be one a user can act on.
    """
    a, _ = two_tenants
    resp = await client.post(
        "/api/v1/claims/import/oscr",
        json={"number": "SC012345"},
        headers=auth(a.owner_id, a.id),
    )
    assert resp.status_code == 503
    assert resp.json()["error"]["code"] == "register_unavailable"
    assert "OSCR" in resp.json()["error"]["message"]


@pytest.mark.parametrize(
    "route,number",
    [
        ("companies-house", "not-a-number"),
        ("charity-commission", "SC012345"),
        ("oscr", "1234567"),
    ],
)
async def test_identifiers_are_validated_before_any_request(
    client, two_tenants, register_keys, route, number
):
    """A number that reaches a register client cannot express a URL.

    That is what lets `registers.py` build URLs by format string with no
    escaping: validation here is the whole defence, so it runs before the key
    check and before the network.
    """
    a, _ = two_tenants
    resp = await client.post(
        f"/api/v1/claims/import/{route}",
        json={"number": number},
        headers=auth(a.owner_id, a.id),
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "bad_register_number"


async def test_confirming_a_proposal_supersedes_the_previous_value(client, two_tenants):
    """The register's whole point: the current figure, and the old one kept.

    This is the July monitoring-report case from the brief — the report must
    read the value the workspace holds now, not the one a bid asserted in
    January, and January's must still be answerable for.
    """
    a, _ = two_tenants
    headers = auth(a.owner_id, a.id)

    first = await client.post(
        "/api/v1/claims",
        json={
            "kind": "people_served",
            "statement": "The organisation supported 1,240 people.",
            "value": 1240,
        },
        headers=headers,
    )
    assert first.status_code == 201
    original_id = first.json()["id"]

    second = await client.post(
        "/api/v1/claims",
        json={
            "kind": "people_served",
            "statement": "The organisation supported 1,610 people.",
            "value": 1610,
        },
        headers=headers,
    )
    assert second.status_code == 201

    listed = (await client.get("/api/v1/claims", headers=headers)).json()
    live = [c for c in listed if c["kind"] == "people_served"]
    assert len(live) == 1, "two live claims for one fact is a choice nobody can make"
    assert live[0]["value"] == 1610

    # Superseded, not deleted — it is what answers "what did we say in January".
    superseded = await client.get(f"/api/v1/claims/{original_id}", headers=headers)
    assert superseded.json()["status"] == "superseded"

    async with db.tenant_tx(a.owner_id, a.id) as conn:
        revisions = await conn.fetchval(
            "select count(*) from claim_revisions where claim_id in ($1, $2)",
            original_id,
            second.json()["id"],
        )
    assert revisions == 2


async def test_verification_is_the_only_thing_that_moves_the_dates(client, two_tenants):
    a, _ = two_tenants
    headers = auth(a.owner_id, a.id)
    created = (
        await client.post(
            "/api/v1/claims",
            json={
                "kind": "volunteers",
                "statement": "The organisation works with 40 volunteers.",
                "value": 40,
            },
            headers=headers,
        )
    ).json()

    # Age it, so a date that fails to move is visible.
    async with db.tenant_tx(a.owner_id, a.id) as conn:
        await conn.execute(
            "update claims set last_verified = $2, next_review = $3 where id = $1",
            created["id"],
            date.today() - timedelta(days=400),
            date.today() - timedelta(days=35),
        )

    stale = (await client.get(f"/api/v1/claims/{created['id']}", headers=headers)).json()
    assert stale["stale"] is True

    # An ordinary edit is not a verification.
    edited = (
        await client.patch(
            f"/api/v1/claims/{created['id']}", json={"notes": "checked with Ade"}, headers=headers
        )
    ).json()
    assert edited["stale"] is True

    verified = (
        await client.patch(
            f"/api/v1/claims/{created['id']}", json={"verified": True}, headers=headers
        )
    ).json()
    assert verified["stale"] is False
    assert verified["last_verified"] == date.today().isoformat()


async def test_expiry_drives_review_and_shows_as_expired(client, two_tenants):
    """An insurance policy is current until its certificate lapses.

    Any other review cycle would either nag early or — much worse — go quiet
    after the cover has run out, which is the failure the brief's digest
    example is about.
    """
    a, _ = two_tenants
    headers = auth(a.owner_id, a.id)
    lapsed = date.today() - timedelta(days=30)
    created = (
        await client.post(
            "/api/v1/claims",
            json={
                "kind": "insurance_policy",
                "subject": "Public liability",
                "statement": "The organisation holds Public liability cover of £5,000,000.",
                "value": 5000000,
                "expires_on": lapsed.isoformat(),
            },
            headers=headers,
        )
    ).json()

    assert created["expired"] is True
    assert created["next_review"] == lapsed.isoformat()
    assert created["stale"] is True


async def test_single_valued_kind_rejects_a_subject(client, two_tenants):
    a, _ = two_tenants
    resp = await client.post(
        "/api/v1/claims",
        json={
            "kind": "annual_income",
            "subject": "Restricted funds",
            "statement": "The organisation's annual income was £10.",
        },
        headers=auth(a.owner_id, a.id),
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "unexpected_subject"


async def test_unknown_kind_is_refused_at_the_edge(client, two_tenants):
    """`kind` has no foreign key, deliberately, so this check is the only one.

    Without it a typo would store a claim nothing can ever match to a register
    field or a funder's question.
    """
    a, _ = two_tenants
    resp = await client.post(
        "/api/v1/claims",
        json={"kind": "vibes", "statement": "We are well thought of."},
        headers=auth(a.owner_id, a.id),
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "unknown_claim_kind"


async def test_retired_kind_leaves_its_claims_readable(client, two_tenants):
    """The reason `kind` is not a foreign key.

    Retiring a fact type from the catalogue must not break the register screen
    for every workspace that already holds one.
    """
    a, _ = two_tenants
    headers = auth(a.owner_id, a.id)
    async with db.tenant_tx(a.owner_id, a.id) as conn:
        await conn.execute(
            """
            insert into claims (tenant_id, kind, statement, status, source, created_by)
            values ($1, 'retired_kind', 'Something we used to track.', 'confirmed', 'typed', $2)
            """,
            a.id,
            a.owner_id,
        )
    listed = (await client.get("/api/v1/claims", headers=headers)).json()
    orphan = next(c for c in listed if c["kind"] == "retired_kind")
    assert orphan["label"] == "retired_kind"
    assert orphan["statement"] == "Something we used to track."


async def test_statement_templates_render_for_every_seeded_kind(client, two_tenants):
    """A template referencing a placeholder the fact cannot carry is a bug.

    Cheap to assert here and expensive to find on a funder's form, where it
    would surface as a literal "{value}" in a submitted answer.
    """
    a, _ = two_tenants
    async with db.tenant_tx(a.owner_id, a.id) as conn:
        kinds = await load_kinds(conn)

    assert kinds, "catalogue is empty — the seeder did not run"
    for kind in kinds.values():
        statement = render_statement(kind, "Example subject", "Example value")
        assert "{" not in statement, f"{kind.key} left a placeholder unrendered"
        assert statement.strip()


# -- proposals written from a document (worker path, exercised here) ----------


async def test_a_document_proposes_facts_that_a_person_can_tick(client, two_tenants):
    """The worker's `save_proposals` against a real database.

    Worker CI has no Postgres, so its DB-touching modules are imported across
    the monorepo and run here — the same rule as the context gatherers
    (ASSUMPTIONS #13).
    """

    a, _ = two_tenants
    headers = auth(a.owner_id, a.id)

    async with db.tenant_tx(a.owner_id, a.id) as conn:
        chunk_id = await conn.fetchval(
            "insert into doc_chunks (tenant_id, document_id, content) values ($1, $2, $3)"
            " returning id",
            a.id,
            a.document_id,
            "Total income for the year was £847,000.",
        )
        written = await save_proposals(
            conn,
            str(a.id),
            str(a.document_id),
            str(a.owner_id),
            [
                ExtractedFact(
                    kind="annual_income",
                    value=847000,
                    locator=str(chunk_id),
                    quote="Total income for the year was £847,000",
                    period="2025/26",
                ),
                ExtractedFact(
                    kind="insurance_policy",
                    subject="Public liability",
                    value=5000000,
                    locator=str(chunk_id),
                    quote="Limit of indemnity £5,000,000, expiring 12 April 2027",
                    expires_on="2027-04-12",
                ),
            ],
        )
    assert written == 2

    listed = (await client.get("/api/v1/claims", headers=headers)).json()
    by_kind = {c["kind"]: c for c in listed}

    income = by_kind["annual_income"]
    # Proposed, never asserted. Nothing reaches a draft until somebody ticks it.
    assert income["status"] == "proposed"
    assert income["source"] == "document"
    assert income["statement"] == "The organisation's annual income was £847,000."
    assert income["period"] == "2025/26"
    # The evidence link is what lets the claim be cited in a draft later.
    assert income["source_chunk_id"] == str(chunk_id)
    assert income["source_document_id"] == str(a.document_id)
    # And the quote is why a person can decide in ten seconds without opening
    # the document.
    assert "Total income for the year was £847,000" in income["notes"]

    # An expiry read off a certificate is most of why reading it was worth it:
    # it is what later makes lapsed cover visible rather than quietly asserted.
    assert by_kind["insurance_policy"]["expires_on"] == "2027-04-12"


async def test_reingesting_a_document_does_not_ask_the_same_question_twice(client, two_tenants):

    a, _ = two_tenants
    async with db.tenant_tx(a.owner_id, a.id) as conn:
        chunk_id = await conn.fetchval(
            "insert into doc_chunks (tenant_id, document_id, content) values ($1, $2, $3)"
            " returning id",
            a.id,
            a.document_id,
            "We work with 40 volunteers.",
        )
        fact = ExtractedFact(
            kind="volunteers",
            value=40,
            locator=str(chunk_id),
            quote="We work with 40 volunteers",
        )
        first = await save_proposals(conn, str(a.id), str(a.document_id), str(a.owner_id), [fact])
        second = await save_proposals(conn, str(a.id), str(a.document_id), str(a.owner_id), [fact])

    assert first == 1
    assert second == 0, "re-uploading a document must not restack the same proposals"


async def test_a_proposal_never_reaches_a_draft_until_it_is_confirmed(client, two_tenants):
    """The line the whole feature rests on, checked end to end.

    A document proposal is visible in the register and invisible to the
    drafting worker, until a person says otherwise.
    """

    a, _ = two_tenants
    headers = auth(a.owner_id, a.id)

    async with db.tenant_tx(a.owner_id, a.id) as conn:
        chunk_id = await conn.fetchval(
            "insert into doc_chunks (tenant_id, document_id, content) values ($1, $2, $3)"
            " returning id",
            a.id,
            a.document_id,
            "The organisation employs 12 people.",
        )
        await save_proposals(
            conn,
            str(a.id),
            str(a.document_id),
            str(a.owner_id),
            [
                ExtractedFact(
                    kind="employees_headcount",
                    value=12,
                    locator=str(chunk_id),
                    quote="The organisation employs 12 people",
                )
            ],
        )
        claims, _ = await load_claims(conn, date.today())
    assert "employees_headcount" not in {c.kind for c in claims}

    proposal = next(
        c
        for c in (await client.get("/api/v1/claims", headers=headers)).json()
        if c["kind"] == "employees_headcount"
    )
    await client.patch(
        f"/api/v1/claims/{proposal['id']}", json={"status": "confirmed"}, headers=headers
    )

    async with db.tenant_tx(a.owner_id, a.id) as conn:
        claims, excerpts = await load_claims(conn, date.today())

    confirmed = next(c for c in claims if c.kind == "employees_headcount")
    assert confirmed.statement == "The organisation employs 12 people."
    # Confirmed *and* citable: its chunk comes along, so a draft leaning on it
    # can point at the page it was read from.
    assert confirmed.chunk_id == chunk_id
    assert chunk_id in {e.chunk_id for e in excerpts}


# -- keeping the register true ------------------------------------------------


async def test_removing_a_member_releases_the_claims_they_owned(client, two_tenants):
    """Brief §12.3.

    The foreign key would null these on its own, so nothing would break — but
    "nothing breaks" is how a register quietly stops being anybody's job. The
    release is done explicitly and counted, so it lands in the audit trail at
    the one moment an admin could act on it.
    """
    a, _ = two_tenants
    headers = auth(a.owner_id, a.id)

    invited = await client.post(
        "/api/v1/invites", json={"email": "leaver@example.com", "role": "member"}, headers=headers
    )
    assert invited.status_code == 201
    async with db.tenant_tx(a.owner_id, a.id) as conn:
        leaver = await conn.fetchval(
            "insert into memberships (tenant_id, user_id, role, email)"
            " values ($1, $2, 'member', 'leaver@example.com') returning id",
            a.id,
            uuid4(),
        )
        await conn.execute(
            "update claims set owner_membership_id = $2 where id = $1", a.claim_id, leaver
        )

    resp = await client.delete(f"/api/v1/members/{leaver}", headers=headers)
    assert resp.status_code == 204

    claim = (await client.get(f"/api/v1/claims/{a.claim_id}", headers=headers)).json()
    # Released, not deleted: the fact is still true, it just has no owner.
    assert claim["owner_membership_id"] is None
    assert claim["status"] == "confirmed"

    async with db.tenant_tx(a.owner_id, a.id) as conn:
        meta = await conn.fetchval(
            "select meta from audit_log where action = 'member.remove'"
            " order by created_at desc limit 1"
        )
    assert json.loads(meta)["claims_disowned"] == 1


async def test_harvested_facts_arrive_as_proposals_with_no_citation(client, two_tenants):
    """A bid is the organisation repeating a claim it made elsewhere.

    Worth keeping, worth checking, and never citable — the submitted document
    is not a chunked upload, so a harvested claim points at no chunk. That puts
    it in the same position as a register fact, and honestly so.
    """
    a, _ = two_tenants
    headers = auth(a.owner_id, a.id)

    async with db.tenant_tx(a.owner_id, a.id) as conn:
        written = await save_proposals(
            conn,
            str(a.id),
            None,
            str(a.owner_id),
            [
                ExtractedFact(
                    kind="accreditation",
                    subject="Cyber Essentials Plus",
                    value="held since 2024",
                    locator="q7",
                    quote="We have held Cyber Essentials Plus since 2024",
                )
            ],
            source="draft",
        )
    assert written == 1

    claim = next(
        c
        for c in (await client.get("/api/v1/claims", headers=headers)).json()
        if c["kind"] == "accreditation"
    )
    assert claim["status"] == "proposed"
    assert claim["source"] == "draft"
    assert claim["source_chunk_id"] is None
    assert claim["source_document_id"] is None
    assert "a document you submitted" in claim["notes"]

    # And it stays out of drafts until somebody ticks it.
    async with db.tenant_tx(a.owner_id, a.id) as conn:
        claims, _ = await load_claims(conn, date.today())
    assert "accreditation" not in {c.kind for c in claims}


async def test_a_harvested_fact_the_register_already_holds_is_not_reproposed(client, two_tenants):
    """Submitting a second application must not re-ask everything the first
    one already put in front of somebody."""
    a, _ = two_tenants
    fact = ExtractedFact(
        kind="volunteers",
        value=40,
        locator="q4",
        quote="We work with 40 volunteers",
    )
    async with db.tenant_tx(a.owner_id, a.id) as conn:
        first = await save_proposals(conn, str(a.id), None, str(a.owner_id), [fact], source="draft")
        second = await save_proposals(
            conn, str(a.id), None, str(a.owner_id), [fact], source="draft"
        )
    assert (first, second) == (1, 0)
