"""DRAFT-001, database half: the engine's usage write against real schema.

`worker/drafting/usage.py` is now the single place a draft's cost is recorded,
on success *and* on every failure path. Worker CI has no Postgres, so — as
with the context gatherers (ASSUMPTIONS #13) — the module is imported across
the monorepo and exercised here: the `usage_events_kind_check` constraint, the
column set, and RLS all have to hold, and none of that is visible to the
worker's offline test of the engine's control flow
(`apps/worker/tests/test_drafting_usage.py`).
"""

import sys
from pathlib import Path
from uuid import uuid4

import asyncpg
import pytest

from app.db import db
from tests.conftest import seed_tenant

sys.path.append(str(Path(__file__).resolve().parents[2] / "worker"))

from worker.drafting.llm import LlmCall, LlmLedger  # noqa: E402
from worker.drafting.usage import write_usage  # noqa: E402


def _ledger() -> LlmLedger:
    ledger = LlmLedger()
    ledger.calls = [LlmCall("drafter", 1_000, 400), LlmCall("reasoner", 2_000, 800)]
    ledger.embed_tokens = 4_000
    ledger.embed_cost_usd = 0.0004
    return ledger


async def _drafting_usage(tenant) -> list[asyncpg.Record]:
    async with db.tenant_tx(tenant.owner_id, tenant.id) as conn:
        return await conn.fetch(
            """
            select kind, model, tokens_in, tokens_out, cost_usd from usage_events
            where kind in ('draft', 'embed') order by kind, model
            """
        )


async def test_a_ledger_lands_as_one_row_per_call(client):
    tenant = await seed_tenant(client, f"usage-{uuid4().hex[:6]}")
    ledger = _ledger()

    async with db.tenant_tx(tenant.owner_id, tenant.id) as conn:
        await write_usage(conn, str(tenant.id), str(tenant.owner_id), ledger)

    rows = await _drafting_usage(tenant)
    assert [(r["kind"], r["model"]) for r in rows] == [
        ("draft", "drafter"),
        ("draft", "reasoner"),
        ("embed", "embedder"),
    ]
    assert [r["tokens_in"] for r in rows] == [1_000, 2_000, 4_000]
    # The embedding row leaves tokens_out null — an embedding has no output.
    assert [r["tokens_out"] for r in rows] == [400, 800, None]
    # The engine's totals are what the usage page and the soft cap read.
    assert float(sum(r["cost_usd"] for r in rows)) == pytest.approx(ledger.cost_usd, abs=1e-6)


async def test_an_empty_ledger_writes_nothing(client):
    """A job that failed before its first call must not book a zero charge."""
    tenant = await seed_tenant(client, f"usage0-{uuid4().hex[:6]}")

    async with db.tenant_tx(tenant.owner_id, tenant.id) as conn:
        await write_usage(conn, str(tenant.id), str(tenant.owner_id), LlmLedger())

    assert await _drafting_usage(tenant) == []


async def test_metering_cannot_be_written_into_another_tenant(client):
    """RLS is the boundary here too — the engine passes the tenant id as a
    string, and a wrong one must be refused by policy, not by app code."""
    a = await seed_tenant(client, f"usagea-{uuid4().hex[:6]}")
    b = await seed_tenant(client, f"usageb-{uuid4().hex[:6]}")

    async with db.tenant_tx(a.owner_id, a.id) as conn:
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await write_usage(conn, str(b.id), str(b.owner_id), _ledger())

    assert await _drafting_usage(b) == []
