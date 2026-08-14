"""Core project plans: optional tasks on a vault container.

General (sidebar) projects stay document-and-chat containers. A second create
kind attaches a thin task list — title, due date, workspace-member assignee —
plus a default "Project brief" vault document. This is not Groundwork:
`proj_tasks` stays on the development spine and still requires a stage_key.

`has_plan` lives on `projects` so an empty task list is still a planned
project. `project_tasks` is unflagged core (like claims): every tenant can
use it, and it is listed in CORE_TENANT_TABLES for the RLS coverage check.

Revision ID: 0018
Revises: 0017
Create Date: 2026-08-14
"""

from alembic import op

from migrations.rls import enable_tenant_rls

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None

CORE_TABLES = ["project_tasks"]


def upgrade() -> None:
    op.execute("alter table projects add column has_plan boolean not null default false")
    op.execute(
        """
        create table project_tasks (
            id uuid primary key default gen_random_uuid(),
            tenant_id uuid not null references tenants(id) on delete cascade,
            project_id uuid not null references projects(id) on delete cascade,
            title text not null,
            status text not null default 'todo'
                check (status in ('todo', 'doing', 'done')),
            due_date date,
            assignee_membership_id uuid references memberships(id) on delete set null,
            position int not null default 0,
            completed_at timestamptz,
            created_at timestamptz not null default now()
        )
        """
    )
    op.execute("create index on project_tasks (tenant_id, project_id, status)")
    op.execute(
        "create index on project_tasks (tenant_id, due_date) where status in ('todo', 'doing')"
    )
    enable_tenant_rls(CORE_TABLES)


def downgrade() -> None:
    op.execute("drop table project_tasks")
    op.execute("alter table projects drop column has_plan")
