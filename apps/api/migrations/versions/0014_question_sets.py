"""Question sets: what a funder actually asks, as reference data.

A funder's application is a fixed list of questions with hard character
limits, and the portals themselves tell applicants to draft offline and paste
in. So the questions belong in the same place as every other external fact we
assert on a tenant's behalf — a catalogue with `last_verified`/`next_review`,
not a hardcoded skeleton.

Two tables, because there are two sources of truth with different trust:

`ref_question_sets` is **platform-curated** — an operator transcribes a
funder's published questions and limits, and re-verifies them on a cycle. It
follows `proj_ref_programmes` exactly: no `tenant_id`, readable in every
tenant context, writable only by the migrations role.

`tenant_question_sets` is **the tenant's own** — a set they typed in or
imported for a funder we have not curated. Tenant-scoped, so it carries the
standard `tenant_isolation` policy and is listed in `app.modules`
CORE_TENANT_TABLES (unflagged: a tenant with only `projects` and a tenant with
only `grants` both need it).

Also widens both modules' draft-job tables for the new `application_form`
kind, and adds the `answers` column that makes the answer sheet possible —
the per-question prose exists in the engine today and is thrown away once the
DOCX is built.

Revision ID: 0014
Revises: 0013
Create Date: 2026-08-11
"""

from alembic import op

from migrations.rls import enable_tenant_rls

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None

REF_TABLES = ["ref_question_sets"]
CORE_TABLES = ["tenant_question_sets"]

_PROJ_KINDS_NEW = (
    "('monthly_report', 'feasibility_study', 'funding_bid', 'health_card', 'application_form')"
)
_PROJ_KINDS_OLD = "('monthly_report', 'feasibility_study', 'funding_bid', 'health_card')"

_GRANT_KINDS_NEW = (
    "('case_for_support', 'funding_application', 'monitoring_report', 'impact_evaluation',"
    " 'impact_card', 'application_form')"
)
_GRANT_KINDS_OLD = (
    "('case_for_support', 'funding_application', 'monitoring_report', 'impact_evaluation',"
    " 'impact_card')"
)

# Shared column list. `questions` is jsonb rather than a child table on
# purpose: a question set is read whole, written whole by an operator, and
# never queried across sets. A row-per-question table would buy nothing and
# cost a join on the hot drafting path.
_QUESTION_SET_COLUMNS = """
    name text not null,
    funder text not null,
    programme_keys text[] not null default '{}',
    funder_keys text[] not null default '{}',
    stage text not null default 'full'
        check (stage in ('eoi', 'full', 'monitoring')),
    source_url text,
    questions jsonb not null,
    status text not null default 'unverified',
    last_verified date not null,
    next_review date not null,
    notes text
"""


def upgrade() -> None:
    op.execute(
        f"""
        create table ref_question_sets (
            key text primary key,
            {_QUESTION_SET_COLUMNS}
        )
        """
    )
    for table in REF_TABLES:
        op.execute(f"alter table {table} enable row level security")
        op.execute(f"create policy ref_read on {table} for select using (true)")

    # `ref_key` points at the platform catalogue when a tenant has edited a
    # curated set, and is deliberately not an FK — retiring a catalogue row
    # must not orphan a tenant's own copy (same reasoning as
    # `grant_funders.ref_key`, 0013).
    op.execute(
        f"""
        create table tenant_question_sets (
            id uuid primary key default gen_random_uuid(),
            tenant_id uuid not null references tenants(id) on delete cascade,
            key text not null,
            ref_key text,
            source_document_id uuid references documents(id) on delete set null,
            {_QUESTION_SET_COLUMNS},
            created_at timestamptz not null default now(),
            updated_at timestamptz not null default now(),
            unique (tenant_id, key)
        )
        """
    )
    enable_tenant_rls(CORE_TABLES)

    op.execute("alter table proj_draft_jobs drop constraint proj_draft_jobs_kind_check")
    op.execute(
        f"alter table proj_draft_jobs add constraint proj_draft_jobs_kind_check"
        f" check (kind in {_PROJ_KINDS_NEW})"
    )
    op.execute("alter table grant_draft_jobs drop constraint grant_draft_jobs_kind_check")
    op.execute(
        f"alter table grant_draft_jobs add constraint grant_draft_jobs_kind_check"
        f" check (kind in {_GRANT_KINDS_NEW})"
    )

    # The answer sheet. Null for every kind but `application_form` — the other
    # kinds are documents, not per-field answers.
    for table in ("proj_draft_jobs", "grant_draft_jobs"):
        op.execute(f"alter table {table} add column answers jsonb")


def downgrade() -> None:
    for table in ("proj_draft_jobs", "grant_draft_jobs"):
        op.execute(f"alter table {table} drop column answers")

    op.execute("alter table grant_draft_jobs drop constraint grant_draft_jobs_kind_check")
    # Narrowing validates existing rows — application-form jobs do not survive.
    op.execute("delete from grant_draft_jobs where kind = 'application_form'")
    op.execute(
        f"alter table grant_draft_jobs add constraint grant_draft_jobs_kind_check"
        f" check (kind in {_GRANT_KINDS_OLD})"
    )
    op.execute("alter table proj_draft_jobs drop constraint proj_draft_jobs_kind_check")
    op.execute("delete from proj_draft_jobs where kind = 'application_form'")
    op.execute(
        f"alter table proj_draft_jobs add constraint proj_draft_jobs_kind_check"
        f" check (kind in {_PROJ_KINDS_OLD})"
    )

    for table in CORE_TABLES + REF_TABLES:
        op.execute(f"drop table {table}")
