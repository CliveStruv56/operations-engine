"""Email digests: a per-member preference and the sweep's tenant discovery.

The claims brief (§14.1 steps 2–3) needs two things Postgres-side: somewhere
to record that a person has unsubscribed from digest email, and a way for the
worker's cron sweep — which runs as ops_app with RLS and no tenant context —
to learn which tenants have claims due at all. The function below is that
discovery: an owner-run, read-only escape that returns tenant ids and nothing
else, so the sweep can then do its real work inside an ordinary per-tenant
transaction. It deliberately mirrors `accept_invite`'s posture: the narrowest
possible SECURITY DEFINER surface, revoked from public.

Revision ID: 0020
Revises: 0019
Create Date: 2026-08-14
"""

from alembic import op

revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # False = receives digests. The unsubscribe link in each digest flips it;
    # there is no admin override — the preference belongs to the recipient.
    op.execute("alter table memberships add column digest_opt_out boolean not null default false")

    op.execute(
        """
        create function claims_sweep_tenants(p_today date)
        returns table (out_tenant_id uuid)
        language sql security definer set search_path = public as
        $$
            select distinct c.tenant_id
            from claims c
            join tenants t on t.id = c.tenant_id
            where t.suspended_at is null
              and c.status = 'confirmed'
              and ((c.next_review is not null and c.next_review <= p_today)
                   or (c.expires_on is not null and c.expires_on < p_today))
        $$
        """
    )
    op.execute("revoke execute on function claims_sweep_tenants(date) from public")
    op.execute("grant execute on function claims_sweep_tenants(date) to ops_app")


def downgrade() -> None:
    op.execute("drop function if exists claims_sweep_tenants(date)")
    op.execute("alter table memberships drop column digest_opt_out")
