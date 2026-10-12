"""Stale-document sweep: tenant discovery for the worker's recovery cron.

A killed ingest job leaves its document at `parsing` or `embedding` with
nothing that will ever move it (code review Sep 2026, WK-3). The worker's
hourly `sweep_stale_documents` marks such rows failed, but it runs as ops_app
with RLS and no tenant context. This function is its discovery step, in the
same shape as `claims_sweep_tenants` (0020): owner-run, read-only, returns
tenant ids and nothing else, revoked from public. The update itself happens in
an ordinary per-tenant transaction.

Revision ID: 0030
Revises: 0029
Create Date: 2026-10-12
"""

from alembic import op

revision = "0030"
down_revision = "0029"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        create function stale_document_tenants(p_before timestamptz)
        returns table (out_tenant_id uuid)
        language sql security definer set search_path = public as
        $$
            select distinct d.tenant_id
            from documents d
            where d.status in ('parsing', 'embedding')
              and d.updated_at < p_before
        $$
        """
    )
    op.execute("revoke execute on function stale_document_tenants(timestamptz) from public")
    op.execute("grant execute on function stale_document_tenants(timestamptz) to ops_app")


def downgrade() -> None:
    op.execute("drop function if exists stale_document_tenants(timestamptz)")
