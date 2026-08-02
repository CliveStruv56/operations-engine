"""Scrub conversation titles from historical unshare audit rows.

patch_conversation used to stamp meta={"title": ...} on both share and
unshare. /activity returns meta verbatim to every member, so an unshare row
kept publishing the title of a chat the owner had just made private. The
handler now omits the title on unshare; this drops the key from rows already
written. Irreversible by design — the downgrade cannot invent the titles
back, and re-leaking them would be the bug.

Revision ID: 0011
Revises: 0010
Create Date: 2026-08-02
"""

from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "update audit_log set meta = meta - 'title'"
        " where action = 'conversation.unshare' and meta ? 'title'"
    )


def downgrade() -> None:
    pass
