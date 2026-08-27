"""Community profile: the place a tenant covers, as structured data.

The claims register (0016) is deliberately about the tenant itself — what the
organisation asserts to funders and regulators. A development trust also needs
the *place*: the ferry, the school roll, the housing stock, the number of
households. Those are facts about a community, they repeat across every funding
application and council conversation, and today they live in a consultant's
notes. This module gives them a register of their own.

Three tenant tables, feature-flagged `community` (see `app.modules`):

`community_profile` is a singleton per tenant — the place itself. Trusts that
cover several settlements tag assets rather than getting a places table;
`settlements` on the profile names the vocabulary.

`community_assets` is one table for every kind of facility. The nine domains
share ~90% of their fields, nothing filters on the per-domain extras (pupil
counts, ferry frequency), so those live in `attributes` jsonb and the form
layer suggests keys per category. Narrow per-domain tables would buy typed
columns nobody queries at a scale of tens of rows per tenant.

`community_statistics` is the numeric series — population, households — and
the bridge to the claims register: a stat that names a `claim_kind` asserts a
confirmed claim on save (source `'module'`, added below). Like `claims.kind`,
`claim_kind` is validated against the catalogue in the router, not by an FK,
so a retired kind degrades to an unmatched stat rather than a failed insert.

Revision ID: 0025
Revises: 0024
Create Date: 2026-08-27
"""

from alembic import op

from migrations.rls import enable_tenant_rls

revision = "0025"
down_revision = "0024"
branch_labels = None
depends_on = None

TABLES = ["community_profile", "community_assets", "community_statistics"]


def upgrade() -> None:
    op.execute(
        """
        create table community_profile (
            id uuid primary key default gen_random_uuid(),
            tenant_id uuid not null unique references tenants(id) on delete cascade,
            place_name text not null,
            description text,
            geography_note text,
            council_area text,
            settlements text[] not null default '{}',
            census_area_codes text[] not null default '{}',
            data_sources_note text,
            created_by uuid,
            created_at timestamptz not null default now(),
            updated_at timestamptz not null default now()
        )
        """
    )

    op.execute(
        """
        create table community_assets (
            id uuid primary key default gen_random_uuid(),
            tenant_id uuid not null references tenants(id) on delete cascade,
            category text not null
                check (category in ('transport', 'education', 'health', 'housing',
                                    'retail_services', 'community_spaces', 'energy',
                                    'employment', 'other')),
            subcategory text,
            name text not null,
            description text,
            attributes jsonb not null default '{}',
            status text not null default 'open'
                check (status in ('open', 'closed', 'seasonal', 'planned')),
            settlement text,
            contact text,
            url text,
            notes text,
            created_by uuid,
            created_at timestamptz not null default now(),
            updated_at timestamptz not null default now()
        )
        """
    )
    op.execute(
        "create index community_assets_tenant_cat_idx on community_assets (tenant_id, category)"
    )

    op.execute(
        """
        create table community_statistics (
            id uuid primary key default gen_random_uuid(),
            tenant_id uuid not null references tenants(id) on delete cascade,
            label text not null,
            value numeric not null,
            unit text,
            period text,
            as_of date,
            claim_kind text,
            source text,
            source_url text,
            notes text,
            created_by uuid,
            created_at timestamptz not null default now(),
            updated_at timestamptz not null default now()
        )
        """
    )
    # One stat per (kind, period) may feed the register — the same identity
    # rule as `claims_confirmed_identity`, so the two cannot drift apart.
    op.execute(
        """
        create unique index community_stats_claim_identity on community_statistics
            (tenant_id, claim_kind, coalesce(period, ''))
            where claim_kind is not null
        """
    )

    enable_tenant_rls(TABLES)

    # The claims register grows a place dimension. `category` gains
    # 'community' so the new kinds group under their own heading, and `source`
    # gains 'module' — a fact maintained in a module register and asserted on
    # save, which is neither 'typed' (that loses the public source URL) nor
    # 'register' (that claims a public-register lookup that never happened).
    op.execute("alter table ref_claim_kinds drop constraint ref_claim_kinds_category_check")
    op.execute(
        """
        alter table ref_claim_kinds add constraint ref_claim_kinds_category_check
            check (category in ('identity', 'governance', 'finance',
                                'people', 'assurance', 'delivery', 'community'))
        """
    )
    op.execute("alter table claims drop constraint claims_source_check")
    op.execute(
        """
        alter table claims add constraint claims_source_check
            check (source in ('register', 'document', 'draft', 'typed', 'module'))
        """
    )


def downgrade() -> None:
    op.execute("alter table claims drop constraint claims_source_check")
    op.execute(
        """
        alter table claims add constraint claims_source_check
            check (source in ('register', 'document', 'draft', 'typed'))
        """
    )
    op.execute("alter table ref_claim_kinds drop constraint ref_claim_kinds_category_check")
    op.execute(
        """
        alter table ref_claim_kinds add constraint ref_claim_kinds_category_check
            check (category in ('identity', 'governance', 'finance',
                                'people', 'assurance', 'delivery'))
        """
    )
    for table in reversed(TABLES):
        op.execute(f"drop table {table}")
