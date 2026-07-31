"""Projects (Slice 4.5): generic containers owning documents and chat scope.

A project partitions the vault ("project docs first, primaries boosted") and
later anchors the Groundwork PM module (proj_* tables reference projects.id).
Also: per-document AI summaries (documents.summary + a retrievable summary
chunk) and the 'summary' usage kind for their generation cost.

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-30
"""

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        create table projects (
            id uuid primary key default gen_random_uuid(),
            tenant_id uuid not null references tenants(id) on delete cascade,
            name text not null,
            description text,
            archived boolean not null default false,
            created_by uuid,
            created_at timestamptz not null default now(),
            updated_at timestamptz not null default now()
        )
        """
    )
    op.execute("create index projects_tenant_idx on projects (tenant_id)")
    op.execute("alter table projects enable row level security")
    op.execute(
        """
        create policy tenant_isolation on projects for all
        using (tenant_id = app_current_tenant())
        with check (tenant_id = app_current_tenant())
        """
    )

    op.execute(
        "alter table documents"
        " add column project_id uuid references projects(id) on delete set null,"
        " add column is_primary boolean not null default false,"
        " add column summary text"
    )
    op.execute("create index documents_project_idx on documents (project_id)")
    op.execute(
        "alter table conversations"
        " add column project_id uuid references projects(id) on delete set null"
    )
    op.execute("create index conversations_project_idx on conversations (project_id)")

    op.execute("alter table doc_chunks add column is_summary boolean not null default false")

    op.execute("alter table usage_events drop constraint usage_events_kind_check")
    op.execute(
        "alter table usage_events add constraint usage_events_kind_check"
        " check (kind in ('chat', 'embed', 'parse', 'summary'))"
    )


def downgrade() -> None:
    op.execute("alter table usage_events drop constraint usage_events_kind_check")
    # Narrowing the check validates existing rows — drop the ones this
    # revision introduced ('summary') or the ADD CONSTRAINT aborts. Their
    # metering history does not survive the downgrade.
    op.execute("delete from usage_events where kind not in ('chat', 'embed', 'parse')")
    op.execute(
        "alter table usage_events add constraint usage_events_kind_check"
        " check (kind in ('chat', 'embed', 'parse'))"
    )
    op.execute("alter table doc_chunks drop column is_summary")
    op.execute("alter table conversations drop column project_id")
    op.execute(
        "alter table documents drop column project_id, drop column is_primary, drop column summary"
    )
    op.execute("drop table projects")
