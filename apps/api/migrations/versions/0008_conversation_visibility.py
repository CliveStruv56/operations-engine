"""Conversation visibility: private by default, shareable with the tenant.

Chat history stays personal unless the owner explicitly shares it —
visibility 'tenant' lets every member of the tenant read (not write) the
conversation. Enforcement is app-code on top of the existing tenant RLS
policy, same as the private-chat rule it extends. 'private'/'tenant' is a
check constraint (not an enum) so a future 'project' visibility is a
one-line widen.

Revision ID: 0008
Revises: 0007
Create Date: 2026-08-02
"""

from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "alter table conversations add column visibility text not null default 'private'"
        " check (visibility in ('private', 'tenant'))"
    )


def downgrade() -> None:
    op.execute("alter table conversations drop column visibility")
