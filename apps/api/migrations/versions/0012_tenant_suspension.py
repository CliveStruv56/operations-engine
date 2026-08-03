"""Reversible workspace suspension for the operator console.

The console could create a workspace but never withdraw one — a mistyped or
abandoned client had to be edited out of the database by hand. Suspension is
the reversible half of that: `suspended_at` non-null makes tenant resolution
403 for every member, so the workspace goes dark without losing anything.

Deliberately not a delete. Hard deletion has to reach outside Postgres (the
R2 prefix and the tenant's LiteLLM virtual key) and the tenants table still
has no RLS delete policy, so a purge is its own piece of work.

Revision ID: 0012
Revises: 0011
Create Date: 2026-08-03
"""

from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("alter table tenants add column suspended_at timestamptz")
    op.execute("alter table tenants add column suspended_reason text")
    # Partial index: the fleet listing filters on it and suspension is rare.
    op.execute(
        "create index tenants_suspended on tenants (suspended_at) where suspended_at is not null"
    )


def downgrade() -> None:
    op.execute("drop index if exists tenants_suspended")
    op.execute("alter table tenants drop column suspended_reason")
    op.execute("alter table tenants drop column suspended_at")
