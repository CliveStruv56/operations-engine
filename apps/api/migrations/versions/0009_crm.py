"""CRM module: tenant-wide contact book (contacts, companies, project links).

Companies are first-class so an address is entered once and shared by its
people; contacts carry only an optional free-text address for the rare
person whose address differs. Project association is a join table, not a
uuid[] on the contact — deleting a project must not leave dangling ids, and
the "contacts on this project" panel needs an indexed reverse lookup.
Per-tenant unique lowercased email is the dedupe anchor for CSV import.

Revision ID: 0009
Revises: 0008
Create Date: 2026-08-02
"""

from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None

MODULE_TENANT_TABLES = ["crm_companies", "crm_contacts", "crm_contact_projects"]


def upgrade() -> None:
    op.execute(
        """
        create table crm_companies (
            id uuid primary key default gen_random_uuid(),
            tenant_id uuid not null references tenants(id) on delete cascade,
            name text not null,
            website text,
            email text,
            phone text,
            address_line1 text,
            address_line2 text,
            city text,
            postcode text,
            notes text,
            created_by uuid,
            created_at timestamptz not null default now(),
            updated_at timestamptz not null default now()
        )
        """
    )
    op.execute("create index on crm_companies (tenant_id, name)")
    op.execute(
        "create index crm_companies_name_trgm on crm_companies using gin (name gin_trgm_ops)"
    )

    op.execute(
        """
        create table crm_contacts (
            id uuid primary key default gen_random_uuid(),
            tenant_id uuid not null references tenants(id) on delete cascade,
            company_id uuid references crm_companies(id) on delete set null,
            name text not null,
            job_title text,
            email text,
            phone text,
            mobile text,
            address text,
            notes text,
            tags text[] not null default '{}',
            created_by uuid,
            created_at timestamptz not null default now(),
            updated_at timestamptz not null default now()
        )
        """
    )
    op.execute("create index on crm_contacts (tenant_id, name)")
    op.execute("create index on crm_contacts (tenant_id, company_id)")
    op.execute("create index crm_contacts_tags on crm_contacts using gin (tags)")
    op.execute("create index crm_contacts_name_trgm on crm_contacts using gin (name gin_trgm_ops)")
    op.execute(
        """
        create unique index crm_contacts_email_uniq on crm_contacts (tenant_id, lower(email))
        where email is not null
        """
    )

    op.execute(
        """
        create table crm_contact_projects (
            id uuid primary key default gen_random_uuid(),
            tenant_id uuid not null,
            contact_id uuid not null references crm_contacts(id) on delete cascade,
            project_id uuid not null references projects(id) on delete cascade,
            created_at timestamptz not null default now(),
            unique (contact_id, project_id)
        )
        """
    )
    op.execute("create index on crm_contact_projects (tenant_id, project_id)")

    for table in MODULE_TENANT_TABLES:
        op.execute(f"alter table {table} enable row level security")
        op.execute(
            f"""
            create policy tenant_isolation on {table} for all
            using (tenant_id = app_current_tenant())
            with check (tenant_id = app_current_tenant())
            """
        )


def downgrade() -> None:
    for table in reversed(MODULE_TENANT_TABLES):
        op.execute(f"drop table {table}")
