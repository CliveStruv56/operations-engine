from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import UUID

import asyncpg

from app.config import get_settings

#: Everything that would make row-level security inert for the connection we
#: are about to serve tenant traffic on. `rolsuper` and `rolbypassrls` are the
#: documented exemptions; table ownership is the one that actually bit us,
#: because the owner is exempt from any policy that is not FORCEd and none of
#: ours are (platform_tx depends on that).
_ROLE_CHECK = """
select current_user                         as role_name,
       r.rolsuper                           as is_superuser,
       r.rolbypassrls                       as bypasses_rls,
       (select count(*) from pg_class c
         where c.relkind = 'r'
           and c.relnamespace = 'public'::regnamespace
           and c.relowner = r.oid)          as owned_tables
  from pg_roles r
 where r.rolname = current_user
"""


async def assert_rls_enforced(pool: asyncpg.Pool) -> None:
    """Refuse to serve on a connection that RLS does not bind.

    Hard constraint 2 says tenant isolation is enforced by Postgres, not by
    app code. That is only true while the connection the app holds is subject
    to the policies — and a mis-set DSN is enough to make it not be, with no
    other symptom. Checking costs one query at boot and converts the worst
    failure mode in the system from silent into a refusal to start.
    """
    row = await pool.fetchrow(_ROLE_CHECK)
    if row is None:  # pragma: no cover — current_user always has a pg_roles row
        raise RuntimeError("Could not determine the database role; refusing to start.")
    faults = []
    if row["is_superuser"]:
        faults.append("is a superuser")
    if row["bypasses_rls"]:
        faults.append("has BYPASSRLS")
    if row["owned_tables"]:
        faults.append(f"owns {row['owned_tables']} table(s) in public")
    if faults:
        raise RuntimeError(
            f"Refusing to start: the API is connected as {row['role_name']!r}, which "
            + " and ".join(faults)
            + ". Every tenant_isolation policy would be inert on this connection."
            " Point APP_DATABASE_URL at the non-owner runtime role (ops_app)."
        )


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
            await assert_rls_enforced(self._pool)

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
        """THE deliberate cross-tenant exception: a connection as the
        table-owner role (database_url, same as migrations), which RLS does
        not bind. Used ONLY by the operator console behind
        require_platform_admin — never in tenant-facing handlers. A direct
        connection, not a pool: operator actions are rare and must not let
        owner-role connections linger.

        Two uses, both cross-tenant by nature: reading the fleet listing, and
        writing the platform reference catalogues, which have no tenant to
        scope them to and are deliberately read-only to `ops_app`
        (ASSUMPTIONS #28)."""
        conn = await asyncpg.connect(get_settings().database_url)
        try:
            async with conn.transaction():
                yield conn
        finally:
            await conn.close()


db = Database()
