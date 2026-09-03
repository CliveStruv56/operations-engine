"""The runtime connection is RLS-bound, and published passwords are detectable.

Both halves of the 3 Sep review finding DB-1/DB-2. The isolation suite proves
the *policies* are right; nothing proved the *connection* they are applied to
was, which is the gap that let one unset variable disable tenant isolation
without a symptom.
"""

import asyncpg
import pytest

from app.config import Settings
from app.db import assert_rls_enforced
from migrations.rolecheck import PUBLISHED_PASSWORDS, password_matches
from tests.conftest import APP_URL, OWNER_URL


def test_effective_app_database_url_has_no_owner_fallback():
    """A missing APP_DATABASE_URL must raise, not silently use the owner."""
    settings = Settings(
        _env_file=None, database_url="postgresql://ops:ops@localhost/x", app_database_url=""
    )
    with pytest.raises(RuntimeError, match="APP_DATABASE_URL"):
        _ = settings.effective_app_database_url


def test_effective_app_database_url_returns_the_runtime_role():
    settings = Settings(
        _env_file=None,
        database_url="postgresql://ops:ops@localhost/x",
        app_database_url="postgresql://ops_app:pw@localhost/x",
    )
    assert settings.effective_app_database_url == "postgresql://ops_app:pw@localhost/x"


async def test_assert_rls_enforced_passes_for_the_runtime_role():
    """ops_app owns nothing and is neither superuser nor BYPASSRLS."""
    pool = await asyncpg.create_pool(APP_URL, min_size=1, max_size=1)
    try:
        await assert_rls_enforced(pool)
    finally:
        await pool.close()


async def test_assert_rls_enforced_refuses_the_owner_connection():
    """The exact misconfiguration the removed fallback used to produce.

    `ops` is the migration owner: superuser in dev/CI and the owner of every
    table everywhere, so RLS does not bind it. Serving tenant traffic on this
    connection is the failure this guard exists to make impossible.
    """
    pool = await asyncpg.create_pool(OWNER_URL, min_size=1, max_size=1)
    try:
        with pytest.raises(RuntimeError, match="Refusing to start"):
            await assert_rls_enforced(pool)
    finally:
        await pool.close()


@pytest.mark.parametrize("rolname", sorted(PUBLISHED_PASSWORDS))
async def test_published_password_is_detected(rolname: str):
    """Round-trip through Postgres: hash the literal, then identify it.

    Uses the server's own SCRAM implementation to build the verifier, so this
    fails if the derivation in rolecheck.py drifts from what Postgres stores.
    """
    conn = await asyncpg.connect(OWNER_URL)
    try:
        await conn.execute("set password_encryption = 'scram-sha-256'")
        # Roles are cluster-wide, so an interrupted earlier run can leave one.
        await conn.execute("drop role if exists rolecheck_probe")
        await conn.execute("create role rolecheck_probe login password 'ops_app'")
        stored = await conn.fetchval(
            "select rolpassword from pg_authid where rolname = 'rolecheck_probe'"
        )
    finally:
        await conn.execute("drop role if exists rolecheck_probe")
        await conn.close()

    assert password_matches(stored, "ops_app", "rolecheck_probe") is True
    assert password_matches(stored, "not-the-password", "rolecheck_probe") is False


@pytest.mark.parametrize(
    "password",
    ["simple-Passw0rd", "has'quote", 'has"double', "back\\slash", "semi;colon--comment"],
)
async def test_role_creation_sql_quotes_the_password(password: str):
    """Migration 0001 builds `create role` DDL around a password it is given.

    DDL takes no bind parameters, so the password is interpolated — which makes
    the quoting the whole safety story. This asserts the exact expression 0001
    uses, including the cast: without it Postgres cannot infer the parameter's
    type inside format() and the migration dies on any fresh database that
    needs the role, which is the one path the rest of the suite never reaches
    (ops_app already exists cluster-wide).
    """
    conn = await asyncpg.connect(OWNER_URL)
    try:
        await conn.execute("set password_encryption = 'scram-sha-256'")
        await conn.execute("drop role if exists rolecheck_probe_ddl")
        ddl = await conn.fetchval(
            "select format('create role rolecheck_probe_ddl login password %L', cast($1 as text))",
            password,
        )
        await conn.execute(ddl)
        stored = await conn.fetchval(
            "select rolpassword from pg_authid where rolname = 'rolecheck_probe_ddl'"
        )
        await conn.execute("drop role if exists rolecheck_probe_ddl")
    finally:
        await conn.close()

    # The password Postgres stored is the one we asked for: quoting neither
    # truncated it at a quote nor let any of it be read as SQL.
    assert password_matches(stored, password, "rolecheck_probe_ddl") is True


def test_password_matches_never_guesses():
    """Unknown or absent verifiers are 'no', never 'maybe'.

    This feeds a guard that blocks deploys, so a false positive is an outage.
    """
    assert password_matches(None, "ops", "ops") is False
    assert password_matches("", "ops", "ops") is False
    assert password_matches("SCRAM-SHA-256$not-a-verifier", "ops", "ops") is False
    assert password_matches("some-future-format$xyz", "ops", "ops") is False
