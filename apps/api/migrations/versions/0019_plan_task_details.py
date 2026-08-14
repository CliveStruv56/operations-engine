"""Plan tasks gain a details note; projects.has_plan is patchable.

The first plan slice stored title / due / assignee only. A short note on the
row is what makes the list usable without turning it into Groundwork tickets.

Revision ID: 0019
Revises: 0018
Create Date: 2026-08-14
"""

from alembic import op

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("alter table project_tasks add column details text")


def downgrade() -> None:
    op.execute("alter table project_tasks drop column details")
