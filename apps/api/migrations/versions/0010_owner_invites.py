"""Widen invites.role to allow 'owner'.

The operator console creates client workspaces and hands ownership over via
an owner-role invite. Tenant-admin invites stay capped at admin|member in
the API schema (InviteCreate); only the platform-admin path issues owner
invites. accept_invite() copies the invite role into memberships, whose
check already allows 'owner'.

Revision ID: 0010
Revises: 0009
Create Date: 2026-08-02
"""

from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("alter table invites drop constraint invites_role_check")
    op.execute(
        "alter table invites add constraint invites_role_check"
        " check (role in ('owner', 'admin', 'member'))"
    )


def downgrade() -> None:
    op.execute("alter table invites drop constraint invites_role_check")
    # Narrowing validates existing rows — pending owner invites do not
    # survive the downgrade.
    op.execute("delete from invites where role = 'owner'")
    op.execute(
        "alter table invites add constraint invites_role_check check (role in ('admin', 'member'))"
    )
