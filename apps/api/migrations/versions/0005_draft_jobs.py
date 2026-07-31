"""Groundwork W3 (PRD §5): proj_draft_jobs — tenant-scoped tracking rows for
AI drafting jobs, written by the API at enqueue and by the worker through the
job lifecycle. Polling reads this table under RLS, so cross-tenant job ids
404 without app-level checks.

Revision ID: 0005
Revises: 0004
Create Date: 2026-07-31
"""

from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        create table proj_draft_jobs (
            id uuid primary key default gen_random_uuid(),
            tenant_id uuid not null,
            project_id uuid not null references proj_projects(id) on delete cascade,
            kind text not null
                check (kind in ('monthly_report', 'feasibility_study', 'funding_bid')),
            params jsonb not null default '{}',
            status text not null default 'queued'
                check (status in ('queued', 'running', 'succeeded', 'failed')),
            error text,
            document_id uuid references proj_documents(id) on delete set null,
            file_key text,
            to_confirm_count int not null default 0,
            llm_calls int not null default 0,
            tokens_in int not null default 0,
            tokens_out int not null default 0,
            cost_usd numeric(10, 6) not null default 0,
            created_by uuid not null,
            created_at timestamptz not null default now(),
            updated_at timestamptz not null default now()
        )
        """
    )
    op.execute("create index on proj_draft_jobs (tenant_id, project_id, created_at desc)")
    op.execute("alter table proj_draft_jobs enable row level security")
    op.execute(
        """
        create policy tenant_isolation on proj_draft_jobs for all
        using (tenant_id = app_current_tenant())
        with check (tenant_id = app_current_tenant())
        """
    )


def downgrade() -> None:
    op.execute("drop table proj_draft_jobs")
