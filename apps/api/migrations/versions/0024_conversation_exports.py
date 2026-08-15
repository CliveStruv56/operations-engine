"""conversation_export_jobs — tenant-scoped tracking rows for exporting a
chat answer as a file (today: PDF, rendered by the worker). Same lifecycle
shape as proj_draft_jobs, but conversation-scoped: a chat need not belong to
a project, so bending the project table would have meant a nullable FK lie.
Polling reads under RLS, so cross-tenant job ids 404 by policy.

Revision ID: 0024
Revises: 0023
Create Date: 2026-08-15
"""

from alembic import op

from migrations.rls import enable_tenant_rls

revision = "0024"
down_revision = "0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        create table conversation_export_jobs (
            id uuid primary key default gen_random_uuid(),
            tenant_id uuid not null,
            conversation_id uuid not null references conversations(id) on delete cascade,
            message_id uuid not null references messages(id) on delete cascade,
            kind text not null default 'pdf' check (kind in ('pdf')),
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
        "create index on conversation_export_jobs (tenant_id, conversation_id, created_at desc)"
    )
    enable_tenant_rls(["conversation_export_jobs"])


def downgrade() -> None:
    op.execute("drop table conversation_export_jobs")
