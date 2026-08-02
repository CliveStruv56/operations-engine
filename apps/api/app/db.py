from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import UUID

import asyncpg

from app.config import get_settings


class Database:
    """Connection pool wrapper.

    Handlers can only obtain a connection through tenant_tx()/user_tx(), which
    open a transaction and set the RLS context via transaction-local
    set_config. There is no way to get a raw connection without context, so no
    handler can accidentally query outside tenant isolation.
    """

    def __init__(self) -> None:
        self._pool: asyncpg.Pool | None = None

    async def connect(self) -> None:
        if self._pool is None:
            self._pool = await asyncpg.create_pool(
                get_settings().effective_app_database_url, min_size=1, max_size=10
            )

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None

    @property
    def _ready_pool(self) -> asyncpg.Pool:
        if self._pool is None:
            raise RuntimeError("Database.connect() has not been called")
        return self._pool

    @asynccontextmanager
    async def tenant_tx(self, user_id: UUID, tenant_id: UUID) -> AsyncIterator[asyncpg.Connection]:
        async with self._ready_pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    "select set_config('app.current_user', $1, true),"
                    " set_config('app.current_tenant', $2, true)",
                    str(user_id),
                    str(tenant_id),
                )
                yield conn

    @asynccontextmanager
    async def user_tx(self, user_id: UUID) -> AsyncIterator[asyncpg.Connection]:
        """Pre-tenant context: only the user is set. Used for membership
        resolution and invite acceptance; RLS policies keyed on
        app.current_user decide what is visible."""
        async with self._ready_pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute("select set_config('app.current_user', $1, true)", str(user_id))
                yield conn

    @asynccontextmanager
    async def platform_tx(self) -> AsyncIterator[asyncpg.Connection]:
        """THE deliberate cross-tenant exception: a read connection as the
        table-owner role (database_url, same as migrations), which RLS does
        not bind. Used ONLY by the operator console's fleet listing behind
        require_platform_admin — never in tenant-facing handlers. A direct
        connection, not a pool: admin listing is rare and must not let
        owner-role connections linger."""
        conn = await asyncpg.connect(get_settings().database_url)
        try:
            async with conn.transaction():
                yield conn
        finally:
            await conn.close()


db = Database()
