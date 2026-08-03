"""Groundwork module W1 (PRD §1): 9 tenant tables + 2 platform reference
tables, all additive.

proj_projects is a 1:1 extension of the core projects table (ASSUMPTIONS.md
#1): name/created_by/created_at live on the core row; the extension carries
the development-specific spine. Every proj_* tenant table gets the core RLS
pattern; reference tables are select-only for the runtime role.

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-30
"""

from alembic import op

from migrations.rls import enable_tenant_rls

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

# Tenant tables that take the standard core policy verbatim.
MODULE_TENANT_TABLES = [
    "proj_projects",
    "proj_stages",
    "proj_tasks",
    "proj_documents",
    "proj_budget_lines",
    "proj_funding_sources",
    "proj_risks",
    "proj_conditions",
    "proj_stakeholders",
]

REF_TABLES = ["proj_ref_templates", "proj_ref_programmes"]


def upgrade() -> None:
    op.execute(
        """
        create table proj_projects (
            id uuid primary key references projects(id) on delete cascade,
            tenant_id uuid not null references tenants(id) on delete cascade,
            client_org text,
            project_type text not null default 'clh_new_build',
            delivery_route text,
            status text not null default 'active'
                check (status in ('active', 'dormant', 'complete', 'archived')),
            dormancy_reason text,
            stage_current text not null default 'group',
            site_address text,
            homes_planned int,
            start_date date,
            target_completion date,
            applicability jsonb not null default '{}',
            contract_facts jsonb not null default '{}',
            updated_at timestamptz not null default now()
        )
        """
    )
    op.execute("create index on proj_projects (tenant_id, status)")

    op.execute(
        """
        create table proj_stages (
            id uuid primary key default gen_random_uuid(),
            tenant_id uuid not null,
            project_id uuid not null references proj_projects(id) on delete cascade,
            stage_key text not null,
            label text not null,
            riba_ref text,
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
            unique (project_id, stage_key)
        )
        """
    )
    op.execute("create index on proj_stages (tenant_id, project_id)")

    op.execute(
        """
        create table proj_tasks (
            id uuid primary key default gen_random_uuid(),
            tenant_id uuid not null,
            project_id uuid not null references proj_projects(id) on delete cascade,
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
    op.execute("create index on proj_tasks (tenant_id, project_id, stage_key, status)")
    op.execute("create index on proj_tasks (tenant_id, due_date) where status in ('todo','doing')")

    op.execute(
        """
        create table proj_documents (
            id uuid primary key default gen_random_uuid(),
            tenant_id uuid not null,
            project_id uuid not null references proj_projects(id) on delete cascade,
            doc_type_key text not null,
            title text not null,
            stage_key text not null,
            status text not null default 'required'
                check (status in ('required', 'drafting', 'review', 'final', 'submitted', 'na')),
            ai_draftable boolean not null default false,
            regulated boolean not null default false,
            current_file_key text,
            vault_document_id uuid references documents(id) on delete set null,
            versions jsonb not null default '[]',
            notes text,
            updated_at timestamptz not null default now(),
            unique (project_id, doc_type_key)
        )
        """
    )
    op.execute("create index on proj_documents (tenant_id, project_id, status)")

    op.execute(
        """
        create table proj_budget_lines (
            id uuid primary key default gen_random_uuid(),
            tenant_id uuid not null,
            project_id uuid not null references proj_projects(id) on delete cascade,
            category text not null,
            label text not null,
            budget numeric(12,2) not null default 0,
            forecast numeric(12,2) not null default 0,
            actual numeric(12,2) not null default 0,
            note text,
            position int not null default 0
        )
        """
    )
    op.execute("create index on proj_budget_lines (tenant_id, project_id)")

    op.execute(
        """
        create table proj_funding_sources (
            id uuid primary key default gen_random_uuid(),
            tenant_id uuid not null,
            project_id uuid not null references proj_projects(id) on delete cascade,
            programme_key text,
            name text not null,
            funder text,
            kind text not null,
            amount_sought numeric(12,2),
            amount_secured numeric(12,2),
            status text not null default 'identified'
                check (status in ('identified', 'applying', 'offered', 'secured',
                                  'drawing', 'complete', 'declined')),
            conditions text,
            drawdown_schedule jsonb not null default '[]',
            notes text,
            updated_at timestamptz not null default now()
        )
        """
    )
    op.execute("create index on proj_funding_sources (tenant_id, project_id)")

    op.execute(
        """
        create table proj_risks (
            id uuid primary key default gen_random_uuid(),
            tenant_id uuid not null,
            project_id uuid not null references proj_projects(id) on delete cascade,
            category text not null,
            description text not null,
            likelihood int not null check (likelihood between 1 and 5),
            impact int not null check (impact between 1 and 5),
            owner_name text,
            mitigation text,
            status text not null default 'open'
                check (status in ('open', 'monitoring', 'closed')),
            review_date date,
            source text not null default 'template' check (source in ('template', 'manual')),
            created_at timestamptz not null default now(),
            updated_at timestamptz not null default now()
        )
        """
    )
    op.execute("create index on proj_risks (tenant_id, project_id, status)")

    op.execute(
        """
        create table proj_conditions (
            id uuid primary key default gen_random_uuid(),
            tenant_id uuid not null,
            project_id uuid not null references proj_projects(id) on delete cascade,
            application_ref text,
            number text not null,
            description text not null,
            pre_commencement boolean not null default false,
            status text not null default 'outstanding'
                check (status in ('outstanding', 'submitted', 'discharged',
                                  'partially_discharged', 'na')),
            submitted_at date,
            discharged_at date,
            notes text
        )
        """
    )
    op.execute("create index on proj_conditions (tenant_id, project_id, status)")

    op.execute(
        """
        create table proj_stakeholders (
            id uuid primary key default gen_random_uuid(),
            tenant_id uuid not null,
            project_id uuid not null references proj_projects(id) on delete cascade,
            name text not null,
            org text,
            role text not null,
            email text, phone text,
            notes text,
            last_contact date
        )
        """
    )
    op.execute("create index on proj_stakeholders (tenant_id, project_id)")

    enable_tenant_rls(MODULE_TENANT_TABLES)

    # Platform reference data: readable by every authenticated tenant context,
    # writable only by the owner role (migrations / seed script) — RLS with a
    # select-only policy blocks runtime writes.
    op.execute(
        """
        create table proj_ref_templates (
            key text primary key,
            version int not null,
            payload jsonb not null
        )
        """
    )
    op.execute(
        """
        create table proj_ref_programmes (
            key text primary key,
            name text not null,
            funder text not null,
            nations text[] not null,
            kind text not null,
            stage_fit text[] not null,
            amount_note text,
            match_note text,
            eligibility text not null,
            status text not null,
            route_url text,
            docs_required text[] not null default '{}',
            last_verified date not null,
            next_review date not null,
            notes text
        )
        """
    )
    for table in REF_TABLES:
        op.execute(f"alter table {table} enable row level security")
        op.execute(f"create policy ref_read on {table} for select using (true)")

    op.execute("alter table usage_events drop constraint usage_events_kind_check")
    op.execute(
        "alter table usage_events add constraint usage_events_kind_check"
        " check (kind in ('chat', 'embed', 'parse', 'summary', 'draft'))"
    )


def downgrade() -> None:
    op.execute("alter table usage_events drop constraint usage_events_kind_check")
    # Narrowing the check validates existing rows — drop the ones this
    # revision introduced ('draft') or the ADD CONSTRAINT aborts. Their
    # metering history does not survive the downgrade.
    op.execute("delete from usage_events where kind not in ('chat', 'embed', 'parse', 'summary')")
    op.execute(
        "alter table usage_events add constraint usage_events_kind_check"
        " check (kind in ('chat', 'embed', 'parse', 'summary'))"
    )
    for table in REF_TABLES + list(reversed(MODULE_TENANT_TABLES)):
        op.execute(f"drop table {table}")
