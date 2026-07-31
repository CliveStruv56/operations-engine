"""Shared fixtures for the Groundwork project-room (W2) suite: a tenant with
the module enabled and a set-up project, plus a stage-list helper."""

from uuid import uuid4

import pytest

from tests.conftest import auth, seed_tenant
from tests.test_groundwork import (
    enable_module,
    gw_setup,
    ref_data,  # noqa: F401
)


@pytest.fixture
async def gw(client):
    t = await seed_tenant(client, f"room-{uuid4().hex[:6]}")
    await enable_module(t)
    out = await gw_setup(client, t)
    return {"t": t, "pid": out["project_id"], "h": auth(t.owner_id, t.id)}


async def get_stages(client, gw):
    resp = await client.get(f"/api/v1/projects/{gw['pid']}/stages", headers=gw["h"])
    assert resp.status_code == 200, resp.text
    return resp.json()
