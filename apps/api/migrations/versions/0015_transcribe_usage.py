"""Widen usage_events.kind with 'transcribe' — reading a funder's published
question list into a structured question set is a model call, and hard
constraint 5 wants every one of them metered under its own name.

Reusing 'parse' was tempting and wrong: that kind means Docling turning an
uploaded file into blocks, which costs CPU and no tokens. Folding an LLM call
into it would make the one kind whose cost is always zero sometimes not.

Revision ID: 0015
Revises: 0014
Create Date: 2026-08-11
"""

from alembic import op

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None

_KINDS_NEW = "('chat', 'embed', 'parse', 'summary', 'draft', 'search', 'transcribe')"
_KINDS_OLD = "('chat', 'embed', 'parse', 'summary', 'draft', 'search')"


def upgrade() -> None:
    op.execute("alter table usage_events drop constraint usage_events_kind_check")
    op.execute(
        f"alter table usage_events add constraint usage_events_kind_check"
        f" check (kind in {_KINDS_NEW})"
    )


def downgrade() -> None:
    op.execute("alter table usage_events drop constraint usage_events_kind_check")
    # Narrowing validates existing rows — transcription metering does not survive.
    op.execute("delete from usage_events where kind = 'transcribe'")
    op.execute(
        f"alter table usage_events add constraint usage_events_kind_check"
        f" check (kind in {_KINDS_OLD})"
    )
