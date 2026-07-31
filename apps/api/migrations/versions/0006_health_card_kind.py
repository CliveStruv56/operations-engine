"""Groundwork W4 (PRD §5.4): widen proj_draft_jobs.kind with 'health_card' —
the one-page PDF shares the draft-job tracking/polling machinery.

Revision ID: 0006
Revises: 0005
Create Date: 2026-07-31
"""

from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None

_KINDS_NEW = "('monthly_report', 'feasibility_study', 'funding_bid', 'health_card')"
_KINDS_OLD = "('monthly_report', 'feasibility_study', 'funding_bid')"


def upgrade() -> None:
    op.execute("alter table proj_draft_jobs drop constraint proj_draft_jobs_kind_check")
    op.execute(
        f"alter table proj_draft_jobs add constraint proj_draft_jobs_kind_check"
        f" check (kind in {_KINDS_NEW})"
    )


def downgrade() -> None:
    op.execute("alter table proj_draft_jobs drop constraint proj_draft_jobs_kind_check")
    # Narrowing validates existing rows — health-card jobs don't survive.
    op.execute("delete from proj_draft_jobs where kind = 'health_card'")
    op.execute(
        f"alter table proj_draft_jobs add constraint proj_draft_jobs_kind_check"
        f" check (kind in {_KINDS_OLD})"
    )
