"""The one blessed RLS shape for module tenant tables.

Every module migration had been copy-pasting the same two statements per
table. That is the duplication where a slip is invisible: enable RLS but
forget the policy and the table is unreadable; write the policy but forget
`with check` and it is writable across tenants. Neither turns a test red on
its own — `test_every_module_table_has_rls` now does, and this helper makes
getting it right the path of least effort.

Deliberately migrations-local rather than imported from `app`: schema
history must not shift under us when application code is refactored. The
emitted SQL is fixed. A table that needs a different policy shape (one keyed
through a parent, say) writes its own SQL rather than growing options here.
"""

from alembic import op


def enable_tenant_rls(tables: list[str] | tuple[str, ...]) -> None:
    """Enable RLS and install the standard `tenant_isolation` policy.

    Assumes each table has a `tenant_id` column. Call after the tables exist.
    """
    for table in tables:
        op.execute(f"alter table {table} enable row level security")
        op.execute(
            f"""
            create policy tenant_isolation on {table} for all
            using (tenant_id = app_current_tenant())
            with check (tenant_id = app_current_tenant())
            """
        )
