"""Alembic upgrade/downgrade must both run cleanly (spec §11 ops criteria).

Runs against a throwaway database so it cannot disturb the suite's seeded data.
"""

import os

import psycopg
from alembic import command
from alembic.config import Config

from tests.conftest import PG_HOST, PG_PORT

MIG_DB = "ops_engine_migtest"


def test_migrations_are_reversible():
    admin_url = f"postgresql://ops:ops@{PG_HOST}:{PG_PORT}/postgres"
    with psycopg.connect(admin_url, autocommit=True) as conn:
        conn.execute(f"drop database if exists {MIG_DB} (force)")
        conn.execute(f"create database {MIG_DB}")

    base = os.path.join(os.path.dirname(__file__), "..")
    cfg = Config(os.path.join(base, "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(base, "migrations"))

    url = f"postgresql://ops:ops@{PG_HOST}:{PG_PORT}/{MIG_DB}"
    previous = os.environ["DATABASE_URL"]
    os.environ["DATABASE_URL"] = url
    from app.config import get_settings

    try:
        get_settings.cache_clear()
        command.upgrade(cfg, "head")
        # Downgrades must survive real data: narrowing usage_events_kind_check
        # validates existing rows, so plant the kinds later revisions added.
        with psycopg.connect(url, autocommit=True) as conn:
            row = conn.execute(
                "insert into tenants (name) values ('migtest') returning id"
            ).fetchone()
            conn.execute(
                "insert into usage_events (tenant_id, kind) values (%s, 'summary'), (%s, 'draft')",
                (row[0], row[0]),
            )
        command.downgrade(cfg, "base")
        command.upgrade(cfg, "head")
    finally:
        os.environ["DATABASE_URL"] = previous
        get_settings.cache_clear()

    with psycopg.connect(url) as conn:
        tables = {
            r[0]
            for r in conn.execute(
                "select tablename from pg_tables where schemaname = 'public'"
            ).fetchall()
        }
    assert "tenants" in tables and "doc_chunks" in tables
