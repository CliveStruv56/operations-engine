"""Tenant-scoped transactions for worker jobs. DB access mirrors the API's
conventions: connect as the non-owner ops_app role and set
app.current_tenant per transaction, so RLS applies to the worker exactly as
it does to request handlers."""

import contextlib

import asyncpg


@contextlib.asynccontextmanager
async def tenant_tx(pool: asyncpg.Pool, tenant_id: str):
    async with pool.acquire() as conn, conn.transaction():
        await conn.execute("select set_config('app.current_tenant', $1, true)", tenant_id)
        yield conn
