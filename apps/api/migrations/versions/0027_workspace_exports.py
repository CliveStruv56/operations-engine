"""Workspace export jobs: the whole workspace as one downloadable archive.

The first self-serve offboarding/backup path — the security page has
promised "your documents and records are yours" since launch, and until now
honouring that was a manual, contractual exercise. Same job shape as the
answer-PDF (0024) and community-PDF (0026) exports: insert + enqueue in one
tenant transaction, assemble in the worker, poll for a presigned URL.

Core and unflagged, like the claims register: every tenant deserves a way
out, whatever modules they bought.

Revision ID: 0027
Revises: 0026
Create Date: 2026-08-27
"""

from alembic import op

from migrations.rls import enable_tenant_rls

revision = "0027"
down_revision = "0026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        create table workspace_export_jobs (
            id uuid primary key default gen_random_uuid(),
            tenant_id uuid not null references tenants(id) on delete cascade,
            kind text not null default 'archive' check (kind in ('archive')),
            status text not null default 'queued'
                check (status in ('queued', 'running', 'succeeded', 'failed')),
            error text,
            file_key text,
            created_by uuid not null,
            created_at timestamptz not null default now(),
            updated_at timestamptz not null default now()
        )
        """
    )
    op.execute(
        "create index workspace_export_jobs_tenant_idx"
        " on workspace_export_jobs (tenant_id, created_at desc)"
    )
    enable_tenant_rls(["workspace_export_jobs"])


def downgrade() -> None:
    op.execute("drop table workspace_export_jobs")
