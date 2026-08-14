"""CCNI snapshot: the Northern Ireland charity register as reference data.

CCNI has no per-charity lookup API — the register is published as a bulk CSV
export, refreshed daily on their side. So Northern Ireland works from an
operator-refreshed snapshot (claims brief, jurisdictions): the operator runs
`python -m app.claims.ccni` with the owner connection, the table is replaced
whole, and tenant lookups read from it inside their ordinary RLS context.
Reference data like `ref_question_sets`: no tenant column, no RLS, writes are
the owner role's alone by code discipline.

The single-row meta table is what keeps the snapshot honest — a lookup can
say when the operator last refreshed it, and review dates on imported claims
derive from that date, not from a freshness the snapshot cannot promise.

Revision ID: 0021
Revises: 0020
Create Date: 2026-08-14
"""

from alembic import op

revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Name, status and public record fields only — the CSV also carries
    # contact details we deliberately do not store (same data-minimisation
    # posture as the officer clients).
    op.execute(
        """
        create table ref_ccni_charities (
            reg_number text primary key,
            name text not null,
            status text not null,
            date_registered date,
            address text,
            website text,
            company_number text,
            total_income numeric,
            total_spending numeric,
            financial_year_end date,
            charitable_purposes text,
            what_it_does text,
            who_it_helps text,
            trustees text[] not null default '{}'
        )
        """
    )
    op.execute(
        """
        create table ref_ccni_snapshot (
            id boolean primary key default true check (id),
            loaded_at timestamptz not null,
            source text not null,
            row_count int not null
        )
        """
    )


def downgrade() -> None:
    op.execute("drop table if exists ref_ccni_snapshot")
    op.execute("drop table if exists ref_ccni_charities")
