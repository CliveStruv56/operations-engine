"""Documents can belong to a conversation: chat attachments.

A file dropped into a chat is a vault document like any other — same upload
flow, same ingest pipeline, same RLS — with one extra edge: the conversation
it was dropped into. Retrieval boosts those documents above even a project's
primary sources for that conversation, because a file somebody just attached
is the most explicit relevance signal there is.

`on delete set null`: deleting the conversation keeps the document — it is in
the vault, the person uploaded it, and chat scope was an edge, not ownership.

Revision ID: 0022
Revises: 0021
Create Date: 2026-08-14
"""

from alembic import op

revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "alter table documents add column conversation_id uuid"
        " references conversations(id) on delete set null"
    )
    op.execute(
        "create index documents_conversation_idx on documents (conversation_id)"
        " where conversation_id is not null"
    )


def downgrade() -> None:
    op.execute("drop index if exists documents_conversation_idx")
    op.execute("alter table documents drop column conversation_id")
