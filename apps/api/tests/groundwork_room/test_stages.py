"""Gate mechanics: manual toggle, doc auto-flip, sign-off with exceptions,
stage advance, and regression notes."""

import pytest

from tests.groundwork_room.conftest import get_stages

pytestmark = pytest.mark.usefixtures("ref_data")


async def test_gate_manual_toggle_and_computed_rejection(client, gw):
    stages = await get_stages(client, gw)
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
    site = next(s for s in await get_stages(client, gw) if s["stage_key"] == "site")
    assert next(i for i in site["gate"] if i["ref"] == "housing_needs_survey")["done"] is True

    # Back to review → the gate item reopens.
    await client.patch(
        f"/api/v1/projects/{gw['pid']}/documents/{needs['id']}",
        json={"status": "review"},
        headers=gw["h"],
    )
    site = next(s for s in await get_stages(client, gw) if s["stage_key"] == "site")
    assert next(i for i in site["gate"] if i["ref"] == "housing_needs_survey")["done"] is False


async def test_signoff_blocked_then_exceptions_then_advance(client, gw):
    stages = await get_stages(client, gw)
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

    stages = await get_stages(client, gw)
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
    stages = await get_stages(client, gw)
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
    stages = await get_stages(client, gw)
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
    stages = await get_stages(client, gw)
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
