"""Budget lines with derived totals, funding CRUD, and the programme
catalogue (nation + status filters)."""

import pytest

pytestmark = pytest.mark.usefixtures("ref_data")


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
