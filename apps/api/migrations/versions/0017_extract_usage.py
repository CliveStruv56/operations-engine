"""Widen usage_events.kind with 'extract' — reading an uploaded document for
facts the organisation could add to its claims register is a model call, and
hard constraint 5 wants every one of them metered under its own name.

Not 'parse': that kind means Docling turning a file into blocks, which costs
CPU and no tokens, and 0015 already recorded why folding an LLM call into it
would ruin the one kind whose cost is always zero.

Not 'summary' either, though both fire on upload and both use the same alias.
They answer different questions on the usage screen — "what is this document
about" runs on every upload, while extraction runs only on documents that look
like they hold organisational facts, and the whole cost argument for phase 4
rests on being able to see that difference.

Revision ID: 0017
Revises: 0016
Create Date: 2026-08-12
"""

from alembic import op

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None

_KINDS_NEW = "('chat', 'embed', 'parse', 'summary', 'draft', 'search', 'transcribe', 'extract')"
_KINDS_OLD = "('chat', 'embed', 'parse', 'summary', 'draft', 'search', 'transcribe')"


def upgrade() -> None:
    op.execute("alter table usage_events drop constraint usage_events_kind_check")
    op.execute(
        f"alter table usage_events add constraint usage_events_kind_check"
        f" check (kind in {_KINDS_NEW})"
    )


def downgrade() -> None:
    op.execute("alter table usage_events drop constraint usage_events_kind_check")
    # Narrowing validates existing rows — extraction metering does not survive.
    op.execute("delete from usage_events where kind = 'extract'")
    op.execute(
        f"alter table usage_events add constraint usage_events_kind_check"
        f" check (kind in {_KINDS_OLD})"
    )
