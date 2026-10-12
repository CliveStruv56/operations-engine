"""WK-3: documents a killed ingest left at parsing/embedding are swept to
failed. Worker CI has no Postgres, so — as with the other worker modules
exercised here — `worker/stale.py` is imported across the monorepo and run
against the real schema, as ops_app, through the migration-0030 discovery
function."""

import sys
from datetime import timedelta
from pathlib import Path

import asyncpg

from app.db import db
from tests.conftest import APP_URL, seed_tenant

sys.path.append(str(Path(__file__).resolve().parents[2] / "worker"))

from worker.stale import INTERRUPTED_REASON, sweep_stale_documents  # noqa: E402


async def _set(tenant, status: str, age: timedelta) -> None:
    async with db.tenant_tx(tenant.owner_id, tenant.id) as conn:
        await conn.execute(
            "update documents set status = $2, updated_at = now() - $3 where id = $1",
            tenant.document_id,
            status,
            age,
        )


async def _status(tenant) -> tuple[str, str | None]:
    async with db.tenant_tx(tenant.owner_id, tenant.id) as conn:
        row = await conn.fetchrow(
            "select status, error from documents where id = $1", tenant.document_id
        )
    return row["status"], row["error"]


async def test_sweep_fails_only_stranded_documents(client):
    stuck = await seed_tenant(client, "stale-stuck")
    embedding = await seed_tenant(client, "stale-embedding")
    live = await seed_tenant(client, "stale-live")
    done = await seed_tenant(client, "stale-done")
    await _set(stuck, "parsing", timedelta(hours=3))
    await _set(embedding, "embedding", timedelta(hours=5))
    await _set(live, "parsing", timedelta(minutes=10))  # an ingest still running
    await _set(done, "ready", timedelta(days=3))

    pool = await asyncpg.create_pool(APP_URL, min_size=1, max_size=2)
    try:
        result = await sweep_stale_documents({"pool": pool})
        # Idempotent: a second run finds nothing left to do.
        again = await sweep_stale_documents({"pool": pool})
    finally:
        await pool.close()

    assert await _status(stuck) == ("failed", INTERRUPTED_REASON)
    assert await _status(embedding) == ("failed", INTERRUPTED_REASON)
    assert await _status(live) == ("parsing", None)
    assert (await _status(done))[0] == "ready"
    assert int(result.rsplit(":", 1)[1]) >= 2  # other tests' rows are never this old
    assert again == "tenants:0 failed:0"


async def test_discovery_is_not_callable_by_public(client):
    """Same posture as claims_sweep_tenants: ops_app only, never PUBLIC."""
    async with db.platform_tx() as conn:
        acl = await conn.fetchval(
            "select proacl::text from pg_proc where proname = 'stale_document_tenants'"
        )
    entries = acl.strip("{}").split(",")
    assert any(e.startswith("ops_app=X") for e in entries)
    assert not any(e.startswith("=") for e in entries)  # "=X/owner" is PUBLIC
