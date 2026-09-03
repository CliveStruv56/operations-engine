"""Tenant-scoped transactions for worker jobs. DB access mirrors the API's
conventions: connect as the non-owner ops_app role and set
app.current_tenant per transaction, so RLS applies to the worker exactly as
it does to request handlers."""

import contextlib

import asyncpg

#: Mirrors app/db.py's check in the API. The worker had nothing equivalent:
#: it has no isolation suite of its own, so a mis-set APP_DATABASE_URL here
#: would have gone unnoticed for as long as the jobs kept succeeding — which
#: they would, since the owner role can read and write everything.
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
    """Refuse to start on a connection RLS does not bind. See app/db.py."""
    row = await pool.fetchrow(_ROLE_CHECK)
    if row is None:  # pragma: no cover
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
            f"Refusing to start: the worker is connected as {row['role_name']!r}, which "
            + " and ".join(faults)
            + ". Every tenant_isolation policy would be inert on this connection."
            " Point APP_DATABASE_URL at the non-owner runtime role (ops_app)."
        )


@contextlib.asynccontextmanager
async def tenant_tx(pool: asyncpg.Pool, tenant_id: str):
    async with pool.acquire() as conn, conn.transaction():
        await conn.execute("select set_config('app.current_tenant', $1, true)", tenant_id)
        yield conn
