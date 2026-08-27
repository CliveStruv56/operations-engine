"""Community profile PDF export jobs.

The one-page community profile PDF follows the answer-PDF shape (0024):
insert a job row and enqueue in the same tenant transaction, render in the
worker (WeasyPrint lives only in that image), poll for the presigned URL.

One row per export rather than one per profile: the trust hands this PDF to
the council or a funder, and "the version we sent in March" is a real
question — a fresh key per job keeps every rendered file addressable.

Revision ID: 0026
Revises: 0025
Create Date: 2026-08-27
"""

from alembic import op

from migrations.rls import enable_tenant_rls

revision = "0026"
down_revision = "0025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        create table community_export_jobs (
            id uuid primary key default gen_random_uuid(),
            tenant_id uuid not null references tenants(id) on delete cascade,
            kind text not null default 'profile_pdf' check (kind in ('profile_pdf')),
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
        "create index community_export_jobs_tenant_idx"
        " on community_export_jobs (tenant_id, created_at desc)"
    )
    enable_tenant_rls(["community_export_jobs"])


def downgrade() -> None:
    op.execute("drop table community_export_jobs")
