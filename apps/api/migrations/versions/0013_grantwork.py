"""Grantwork module (docs/modules/grantwork-prd.md §1): 10 tenant tables + 2
platform reference tables, all additive.

Shape follows Groundwork's, because the machine underneath is the same one:
a stage-gated spine, a typed document registry with append-only versions, a
conditions register, and a job table so draft polling inherits tenant
isolation from RLS (ASSUMPTIONS #12).

Two rulings this migration encodes (founder decision, 3 Aug 2026 — see
ASSUMPTIONS #23):

* `grant_applications` is a **standalone** table, not a 1:1 extension of core
  `projects` the way `proj_projects` is (ASSUMPTIONS #1). A charity runs a
  rolling portfolio of twenty-plus applications; making each one a core
  project would flood the sidebar and fragment the vault into twenty
  partitions, which is the opposite of what chat scoping is for.
* `application.project_id` is a **nullable soft link** to the core `projects`
  row, so a Groundwork development project and the bid that funds it can be
  tied together without either module owning the other. Groundwork's funding
  tab is untouched.

FK targets are checked by Postgres with RLS bypassed, so a cross-tenant
`funder_id` / `project_id` / `measure_id` would be accepted here. As with the
CRM (ASSUMPTIONS #19), the routers reject those with RLS-scoped existence
checks; the FKs exist for cascade behaviour, not for isolation.

Revision ID: 0013
Revises: 0012
Create Date: 2026-08-03
"""

from alembic import op

from migrations.rls import enable_tenant_rls

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None

# Tenant tables that take the standard core policy verbatim. Order matters on
# downgrade only (reversed below), but keeping it dependency-ordered here
# makes the create sequence readable.
MODULE_TENANT_TABLES = [
    "grant_funders",
    "grant_applications",
    "grant_stages",
    "grant_tasks",
    "grant_reporting_periods",
    "grant_documents",
    "grant_conditions",
    "grant_impact_measures",
    "grant_outcomes",
    "grant_draft_jobs",
]

REF_TABLES = ["grant_ref_templates", "grant_ref_funders"]


def upgrade() -> None:
    # The tenant's own funder records: who they have a relationship with.
    # `ref_key` points at the platform catalogue but is deliberately not an
    # FK — a catalogue row can be retired without orphaning the tenant's
    # history of having applied to it.
    op.execute(
        """
        create table grant_funders (
            id uuid primary key default gen_random_uuid(),
            tenant_id uuid not null references tenants(id) on delete cascade,
            ref_key text,
            name text not null,
            kind text not null default 'trust'
                check (kind in ('trust', 'lottery', 'statutory', 'corporate',
                                'community_foundation', 'other')),
            website text,
            contact_name text,
            contact_email text,
            relationship text not null default 'prospect'
                check (relationship in ('prospect', 'applied', 'funder', 'declined', 'lapsed')),
            notes text,
            created_by uuid,
            created_at timestamptz not null default now(),
            updated_at timestamptz not null default now()
        )
        """
    )
    op.execute("create index on grant_funders (tenant_id, name)")

    op.execute(
        """
        create table grant_applications (
            id uuid primary key default gen_random_uuid(),
            tenant_id uuid not null references tenants(id) on delete cascade,
            funder_id uuid references grant_funders(id) on delete set null,
            project_id uuid references projects(id) on delete set null,
            title text not null,
            reference text,
            application_type text not null default 'project_grant',
            programme_key text,
            stage_current text not null default 'case',
            status text not null default 'pipeline'
                check (status in ('pipeline', 'drafting', 'submitted', 'awarded',
                                  'declined', 'withdrawn', 'complete')),
            amount_requested numeric(12,2),
            amount_awarded numeric(12,2),
            restricted boolean not null default true,
            deadline date,
            submitted_at date,
            decision_at date,
            start_date date,
            end_date date,
            reporting_note text,
            notes text,
            created_by uuid,
            created_at timestamptz not null default now(),
            updated_at timestamptz not null default now()
        )
        """
    )
    op.execute("create index on grant_applications (tenant_id, status)")
    op.execute("create index on grant_applications (tenant_id, funder_id)")
    op.execute(
        "create index on grant_applications (tenant_id, project_id) where project_id is not null"
    )

    op.execute(
        """
        create table grant_stages (
            id uuid primary key default gen_random_uuid(),
            tenant_id uuid not null,
            application_id uuid not null references grant_applications(id) on delete cascade,
            stage_key text not null,
            label text not null,
            position int not null,
            status text not null default 'pending'
                check (status in ('pending', 'active', 'passed', 'regressed', 'na')),
            planned_start date, planned_end date,
            forecast_start date, forecast_end date,
            actual_start date, actual_end date,
            gate jsonb not null default '[]',
            gate_signed_off_by uuid,
            gate_signed_off_at timestamptz,
            gate_exceptions text,
            unique (application_id, stage_key)
        )
        """
    )
    op.execute("create index on grant_stages (tenant_id, application_id)")

    op.execute(
        """
        create table grant_tasks (
            id uuid primary key default gen_random_uuid(),
            tenant_id uuid not null,
            application_id uuid not null references grant_applications(id) on delete cascade,
            stage_key text not null,
            title text not null,
            details text,
            owner_name text,
            due_date date,
            is_milestone boolean not null default false,
            tags text[] not null default '{}',
            status text not null default 'todo'
                check (status in ('todo', 'doing', 'done', 'na')),
            source text not null default 'template'
                check (source in ('template', 'manual', 'ai')),
            completed_at timestamptz,
            position int not null default 0
        )
        """
    )
    op.execute("create index on grant_tasks (tenant_id, application_id, stage_key, status)")
    op.execute("create index on grant_tasks (tenant_id, due_date) where status in ('todo','doing')")

    # The obligation calendar. The partial index is what the overdue RAG view
    # reads: everything not yet accepted, by due date. Created before the
    # registry because a monitoring return points back at the period it
    # discharges.
    op.execute(
        """
        create table grant_reporting_periods (
            id uuid primary key default gen_random_uuid(),
            tenant_id uuid not null,
            application_id uuid not null references grant_applications(id) on delete cascade,
            label text not null,
            period_start date not null,
            period_end date not null,
            due_date date,
            status text not null default 'upcoming'
                check (status in ('upcoming', 'open', 'drafting', 'submitted', 'accepted', 'na')),
            submitted_at date,
            accepted_at date,
            notes text,
            created_at timestamptz not null default now(),
            updated_at timestamptz not null default now(),
            unique (application_id, label)
        )
        """
    )
    op.execute("create index on grant_reporting_periods (tenant_id, application_id, period_start)")
    op.execute(
        "create index on grant_reporting_periods (tenant_id, due_date)"
        " where status in ('upcoming', 'open', 'drafting')"
    )

    # The bid pack and monitoring returns. Same registry contract as
    # proj_documents: one row per document type, versions append-only, status
    # advanced by humans (draft-first). A monitoring return keeps its period
    # on `set null` rather than cascade — deleting the obligation must not
    # delete the document that answered it.
    op.execute(
        """
        create table grant_documents (
            id uuid primary key default gen_random_uuid(),
            tenant_id uuid not null,
            application_id uuid not null references grant_applications(id) on delete cascade,
            doc_type_key text not null,
            title text not null,
            stage_key text not null,
            status text not null default 'required'
                check (status in ('required', 'drafting', 'review', 'final', 'submitted', 'na')),
            ai_draftable boolean not null default false,
            reporting_period_id uuid references grant_reporting_periods(id) on delete set null,
            current_file_key text,
            vault_document_id uuid references documents(id) on delete set null,
            versions jsonb not null default '[]',
            notes text,
            updated_at timestamptz not null default now(),
            unique (application_id, doc_type_key)
        )
        """
    )
    op.execute("create index on grant_documents (tenant_id, application_id, status)")

    # Award conditions behave exactly like planning conditions, minus the
    # pre-commencement flag: here what gates money is drawdown.
    op.execute(
        """
        create table grant_conditions (
            id uuid primary key default gen_random_uuid(),
            tenant_id uuid not null,
            application_id uuid not null references grant_applications(id) on delete cascade,
            number text not null,
            description text not null,
            pre_drawdown boolean not null default false,
            status text not null default 'outstanding'
                check (status in ('outstanding', 'submitted', 'discharged',
                                  'partially_discharged', 'na')),
            due_date date,
            submitted_at date,
            discharged_at date,
            notes text
        )
        """
    )
    op.execute("create index on grant_conditions (tenant_id, application_id, status)")

    # What the application promised. Figures in a monitoring report render
    # from measures and outcomes as real tables, never from model output.
    op.execute(
        """
        create table grant_impact_measures (
            id uuid primary key default gen_random_uuid(),
            tenant_id uuid not null,
            application_id uuid not null references grant_applications(id) on delete cascade,
            name text not null,
            definition text,
            unit text not null default 'count',
            baseline numeric(14,2),
            target numeric(14,2),
            position int not null default 0,
            notes text,
            unique (application_id, name)
        )
        """
    )
    op.execute("create index on grant_impact_measures (tenant_id, application_id)")

    # What actually happened, one row per measure per reporting period.
    op.execute(
        """
        create table grant_outcomes (
            id uuid primary key default gen_random_uuid(),
            tenant_id uuid not null,
            measure_id uuid not null references grant_impact_measures(id) on delete cascade,
            reporting_period_id uuid not null
                references grant_reporting_periods(id) on delete cascade,
            value numeric(14,2),
            narrative text,
            evidence_notes text,
            recorded_by uuid,
            recorded_at timestamptz not null default now(),
            unique (measure_id, reporting_period_id)
        )
        """
    )
    op.execute("create index on grant_outcomes (tenant_id, reporting_period_id)")

    op.execute(
        """
        create table grant_draft_jobs (
            id uuid primary key default gen_random_uuid(),
            tenant_id uuid not null,
            application_id uuid not null references grant_applications(id) on delete cascade,
            kind text not null
                check (kind in ('case_for_support', 'funding_application', 'monitoring_report',
                                'impact_evaluation', 'impact_card')),
            params jsonb not null default '{}',
            status text not null default 'queued'
                check (status in ('queued', 'running', 'succeeded', 'failed')),
            error text,
            document_id uuid references grant_documents(id) on delete set null,
            file_key text,
            to_confirm_count int not null default 0,
            llm_calls int not null default 0,
            tokens_in int not null default 0,
            tokens_out int not null default 0,
            cost_usd numeric(10, 6) not null default 0,
            created_by uuid not null,
            created_at timestamptz not null default now(),
            updated_at timestamptz not null default now()
        )
        """
    )
    op.execute("create index on grant_draft_jobs (tenant_id, application_id, created_at desc)")

    enable_tenant_rls(MODULE_TENANT_TABLES)

    # Platform reference data, same contract as proj_ref_*: readable in every
    # tenant context, writable only by the owner role (migrations / seeds).
    # `last_verified` / `next_review` are load-bearing — a stale catalogue row
    # badges in the UI and warns inside the draft it parameterised.
    op.execute(
        """
        create table grant_ref_funders (
            key text primary key,
            name text not null,
            funder text not null,
            funder_type text not null,
            nations text[] not null,
            kind text not null,
            amount_note text,
            typical_award text,
            match_note text,
            eligibility text not null,
            status text not null,
            deadlines text,
            route_url text,
            docs_required text[] not null default '{}',
            reporting_note text,
            last_verified date not null,
            next_review date not null,
            notes text
        )
        """
    )
    op.execute(
        """
        create table grant_ref_templates (
            key text primary key,
            version int not null,
            payload jsonb not null
        )
        """
    )
    for table in REF_TABLES:
        op.execute(f"alter table {table} enable row level security")
        op.execute(f"create policy ref_read on {table} for select using (true)")


def downgrade() -> None:
    for table in REF_TABLES + list(reversed(MODULE_TENANT_TABLES)):
        op.execute(f"drop table {table}")
