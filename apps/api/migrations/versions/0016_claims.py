"""Claims: one true place for what a tenant asserts about itself.

`docs/claims-register-brief.md` argues the case; this builds it. The short
version: a small organisation repeatedly asserts the same forty-odd facts to
funders, commissioners and regulators — registered identity, income, trustees,
accreditations, insurance, policies — and today they live in someone's head,
last year's Word document and a spreadsheet. Each retyping is a chance for a
figure that was true in March to be asserted, still, in July.

Two tables plus a catalogue, and each of the three shapes is deliberate.

`ref_claim_kinds` is the platform catalogue of *fact types*. It follows
`ref_question_sets` exactly: no `tenant_id`, readable in every tenant context,
writable only by the migrations role. Claims are typed rather than free prose
because every consumer needs to match a fact to something — a register field,
a funder's question, a review-date rule — and matching free prose is guesswork.

`claims` is the register itself. Tenant-scoped, so `tenant_isolation`, and
listed in `app.modules` CORE_TENANT_TABLES: unflagged, because every vertical
needs it and a tenant with no vertical modules still benefits.

`claim_revisions` is the value history. Deliberately not `audit_log`: those
rows are activity-feed material and are already scrubbed in place (0011), so
their `meta` is not something anything may query. "What did we tell the funder
in January" has to be a first-class row.

Note what does NOT write a revision: re-verifying a claim whose value has not
changed moves `last_verified` and nothing else. That distinction — still true
versus now different — is the whole point of the register.

Revision ID: 0016
Revises: 0015
Create Date: 2026-08-12
"""

from alembic import op

from migrations.rls import enable_tenant_rls

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None

REF_TABLES = ["ref_claim_kinds"]
CORE_TABLES = ["claims", "claim_revisions"]


def upgrade() -> None:
    # `kind` on `claims` is validated against this catalogue in the router,
    # NOT by a check constraint. Same reasoning as `tenant_question_sets.
    # ref_key` (0014): a hard constraint means a migration every time we learn
    # a new fact type, and each vertical module will bring a dozen. A retired
    # kind then leaves its claims readable-but-unmatched, which degrades far
    # better than a failed insert.
    op.execute(
        """
        create table ref_claim_kinds (
            key text primary key,
            label text not null,
            category text not null
                check (category in ('identity', 'governance', 'finance',
                                    'people', 'assurance', 'delivery')),
            value_kind text not null
                check (value_kind in ('text', 'number', 'money', 'date', 'list', 'boolean')),
            unit text,
            cardinality text not null default 'single'
                check (cardinality in ('single', 'multi')),
            periodic boolean not null default false,
            review_days integer,
            statement_template text not null,
            question_hints text[] not null default '{}',
            register text
                check (register in ('companies_house', 'charity_commission', 'oscr', 'ccni')),
            notes text
        )
        """
    )
    for table in REF_TABLES:
        op.execute(f"alter table {table} enable row level security")
        op.execute(f"create policy ref_read on {table} for select using (true)")

    # `subject` and `period` are the two discriminators that stop this needing
    # a migration against live tenant data later. `subject` names which
    # instance of a multi-valued kind ("Cyber Essentials Plus", a trustee's
    # name); `period` names which slice of a series ("2024/25"). Both null for
    # the ordinary standing fact, which is the overwhelming majority — so the
    # monitoring report that must read the CURRENT beneficiary number needs no
    # period-selection logic anywhere.
    #
    # `source_document_id` and `source_chunk_id` are the evidence link, copied
    # from `tenant_question_sets`: `on delete set null` leaves a claim standing
    # but unevidenced when its document goes, rather than deleting the fact.
    op.execute(
        """
        create table claims (
            id uuid primary key default gen_random_uuid(),
            tenant_id uuid not null references tenants(id) on delete cascade,
            kind text not null,
            subject text,
            period text,
            statement text not null,
            value jsonb,
            unit text,
            as_of date,
            expires_on date,
            status text not null default 'proposed'
                check (status in ('proposed', 'confirmed', 'rejected', 'superseded')),
            source text not null
                check (source in ('register', 'document', 'draft', 'typed')),
            source_ref text,
            source_document_id uuid references documents(id) on delete set null,
            source_chunk_id uuid references doc_chunks(id) on delete set null,
            owner_membership_id uuid references memberships(id) on delete set null,
            last_verified date,
            next_review date,
            notes text,
            created_by uuid,
            created_at timestamptz not null default now(),
            updated_at timestamptz not null default now()
        )
        """
    )
    # Uniqueness binds confirmed rows only. A proposal that duplicates a
    # confirmed claim is not a collision to reject — it is precisely how a
    # changed value gets noticed ("the register now says £912,000; you have
    # £847,000"). Confirming it supersedes the old row in one transaction.
    op.execute(
        """
        create unique index claims_confirmed_identity on claims
            (tenant_id, kind, coalesce(subject, ''), coalesce(period, ''))
            where status = 'confirmed'
        """
    )
    op.execute("create index claims_tenant_status_idx on claims (tenant_id, status, kind)")
    op.execute(
        "create index claims_review_idx on claims (tenant_id, next_review)"
        " where status = 'confirmed'"
    )

    op.execute(
        """
        create table claim_revisions (
            id uuid primary key default gen_random_uuid(),
            tenant_id uuid not null references tenants(id) on delete cascade,
            claim_id uuid not null references claims(id) on delete cascade,
            statement text not null,
            value jsonb,
            as_of date,
            source text not null,
            source_ref text,
            source_document_id uuid references documents(id) on delete set null,
            changed_by uuid,
            changed_at timestamptz not null default now(),
            note text
        )
        """
    )
    op.execute(
        "create index claim_revisions_claim_idx on claim_revisions"
        " (tenant_id, claim_id, changed_at desc)"
    )

    enable_tenant_rls(CORE_TABLES)


def downgrade() -> None:
    # Reverse dependency order: `claim_revisions.claim_id` references `claims`,
    # so the child goes first rather than leaning on a cascade.
    for table in ["claim_revisions", "claims"] + REF_TABLES:
        op.execute(f"drop table {table}")
