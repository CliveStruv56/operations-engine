"""Initial schema: all Phase 1 tables with RLS.

Role model: migrations run as the table owner (bypasses RLS by design —
needed for SECURITY DEFINER helpers). The API runtime connects as `ops_app`,
which is not the owner, so every policy here is enforced on it. The isolation
test suite connects as ops_app.

Revision ID: 0001
Revises:
Create Date: 2026-07-27
"""

import os

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

# Tables that use the standard tenant_isolation policy verbatim.
STANDARD_TENANT_TABLES = [
    "documents",
    "doc_chunks",
    "conversations",
    "messages",
    "usage_events",
    "invites",
    "audit_log",
]


def upgrade() -> None:
    op.execute("create extension if not exists vector")
    op.execute("create extension if not exists pg_trgm")

    op.execute(
        """
        create function app_current_user() returns uuid
        language sql stable as
        $$ select nullif(current_setting('app.current_user', true), '')::uuid $$
        """
    )
    op.execute(
        """
        create function app_current_tenant() returns uuid
        language sql stable as
        $$ select nullif(current_setting('app.current_tenant', true), '')::uuid $$
        """
    )

    op.execute(
        """
        create table tenants (
            id uuid primary key default gen_random_uuid(),
            name text not null,
            plan text not null default 'trial'
                check (plan in ('trial', 'core', 'pro', 'managed')),
            seats int not null default 3 check (seats > 0),
            brand jsonb not null default '{}',
            features jsonb not null default '{}',
            model_mode text not null default 'standard',
            soft_budget_usd numeric(10, 2),
            stripe_customer_id text,
            stripe_subscription_id text,
            litellm_key_id text,
            trial_ends_at timestamptz,
            created_at timestamptz not null default now(),
            updated_at timestamptz not null default now()
        )
        """
    )

    op.execute(
        """
        create table memberships (
            id uuid primary key default gen_random_uuid(),
            user_id uuid not null,
            tenant_id uuid not null references tenants(id) on delete cascade,
            role text not null check (role in ('owner', 'admin', 'member')),
            created_at timestamptz not null default now(),
            unique (user_id, tenant_id)
        )
        """
    )
    op.execute("create index memberships_user_idx on memberships (user_id)")
    op.execute("create index memberships_tenant_idx on memberships (tenant_id)")

    op.execute(
        """
        create table documents (
            id uuid primary key default gen_random_uuid(),
            tenant_id uuid not null references tenants(id) on delete cascade,
            title text not null,
            storage_key text,
            mime text,
            status text not null default 'uploaded'
                check (status in ('uploaded', 'parsing', 'embedding', 'ready', 'failed')),
            error text,
            created_by uuid,
            created_at timestamptz not null default now(),
            updated_at timestamptz not null default now()
        )
        """
    )
    op.execute("create index documents_tenant_status_idx on documents (tenant_id, status)")

    op.execute(
        """
        create table doc_chunks (
            id uuid primary key default gen_random_uuid(),
            tenant_id uuid not null references tenants(id) on delete cascade,
            document_id uuid not null references documents(id) on delete cascade,
            content text not null,
            heading_path text[] not null default '{}',
            page_start int,
            page_end int,
            token_count int,
            embedding vector(2048),
            tsv tsvector generated always as (to_tsvector('english', content)) stored
        )
        """
    )
    # HNSW on the vector type caps at 2000 dims; cast to halfvec (pgvector >=0.7)
    # to index the 2048-dim Qwen3 embeddings. Queries must use the same cast.
    op.execute(
        """
        create index doc_chunks_embedding_idx on doc_chunks
        using hnsw ((embedding::halfvec(2048)) halfvec_cosine_ops)
        """
    )
    op.execute("create index doc_chunks_tsv_idx on doc_chunks using gin (tsv)")
    op.execute("create index doc_chunks_tenant_doc_idx on doc_chunks (tenant_id, document_id)")

    op.execute(
        """
        create table conversations (
            id uuid primary key default gen_random_uuid(),
            tenant_id uuid not null references tenants(id) on delete cascade,
            user_id uuid not null,
            title text,
            created_at timestamptz not null default now(),
            updated_at timestamptz not null default now()
        )
        """
    )
    op.execute("create index conversations_tenant_idx on conversations (tenant_id, updated_at)")

    op.execute(
        """
        create table messages (
            id uuid primary key default gen_random_uuid(),
            tenant_id uuid not null references tenants(id) on delete cascade,
            conversation_id uuid not null references conversations(id) on delete cascade,
            role text not null check (role in ('user', 'assistant', 'system')),
            content text not null,
            citations jsonb not null default '[]',
            model text,
            tokens_in int,
            tokens_out int,
            cost_usd numeric(12, 6),
            created_at timestamptz not null default now()
        )
        """
    )
    op.execute("create index messages_conversation_idx on messages (conversation_id, created_at)")

    op.execute(
        """
        create table usage_events (
            id uuid primary key default gen_random_uuid(),
            tenant_id uuid not null references tenants(id) on delete cascade,
            user_id uuid,
            kind text not null check (kind in ('chat', 'embed', 'parse')),
            model text,
            tokens_in int,
            tokens_out int,
            cost_usd numeric(12, 6),
            created_at timestamptz not null default now()
        )
        """
    )
    op.execute("create index usage_events_tenant_idx on usage_events (tenant_id, created_at)")

    op.execute(
        """
        create table invites (
            id uuid primary key default gen_random_uuid(),
            tenant_id uuid not null references tenants(id) on delete cascade,
            email text not null,
            role text not null default 'member' check (role in ('admin', 'member')),
            token text not null unique,
            expires_at timestamptz not null,
            accepted_at timestamptz,
            created_by uuid,
            created_at timestamptz not null default now()
        )
        """
    )
    op.execute("create index invites_tenant_idx on invites (tenant_id)")

    op.execute(
        """
        create table audit_log (
            id uuid primary key default gen_random_uuid(),
            tenant_id uuid not null references tenants(id) on delete cascade,
            user_id uuid,
            action text not null,
            target_type text,
            target_id text,
            meta jsonb not null default '{}',
            created_at timestamptz not null default now()
        )
        """
    )
    op.execute("create index audit_log_tenant_idx on audit_log (tenant_id, created_at)")

    # --- Row-level security -------------------------------------------------
    op.execute("alter table tenants enable row level security")
    op.execute(
        """
        create policy tenant_select on tenants for select
        using (
            id = app_current_tenant()
            or exists (
                select 1 from memberships m
                where m.tenant_id = tenants.id and m.user_id = app_current_user()
            )
        )
        """
    )
    # Bootstrap generates the tenant id client-side and sets the context before
    # inserting, so the check pins the insert to the claimed context.
    op.execute(
        "create policy tenant_insert on tenants for insert with check (id = app_current_tenant())"
    )
    op.execute(
        "create policy tenant_update on tenants for update"
        " using (id = app_current_tenant()) with check (id = app_current_tenant())"
    )
    # No delete policy: tenant deletion is a Phase 1 stub, done out-of-band.

    op.execute("alter table memberships enable row level security")
    op.execute(
        """
        create policy membership_select on memberships for select
        using (user_id = app_current_user() or tenant_id = app_current_tenant())
        """
    )
    op.execute(
        "create policy membership_insert on memberships for insert"
        " with check (tenant_id = app_current_tenant())"
    )
    op.execute(
        "create policy membership_update on memberships for update"
        " using (tenant_id = app_current_tenant())"
        " with check (tenant_id = app_current_tenant())"
    )
    op.execute(
        "create policy membership_delete on memberships for delete"
        " using (tenant_id = app_current_tenant())"
    )

    for table in STANDARD_TENANT_TABLES:
        op.execute(f"alter table {table} enable row level security")
        op.execute(
            f"""
            create policy tenant_isolation on {table} for all
            using (tenant_id = app_current_tenant())
            with check (tenant_id = app_current_tenant())
            """
        )

    # --- Invite acceptance (SECURITY DEFINER) -------------------------------
    # A user accepting an invite has no membership yet, so RLS forbids reading
    # the invite or inserting the membership. This owner-run function is the
    # single sanctioned bypass; it validates the token itself.
    op.execute(
        """
        create function accept_invite(p_token text, p_user uuid)
        returns table (out_tenant_id uuid, out_role text)
        language plpgsql security definer set search_path = public as
        $$
        declare
            v_invite invites%rowtype;
        begin
            select * into v_invite
            from invites
            where token = p_token and accepted_at is null and expires_at > now();
            if not found then
                raise 'invalid_invite';
            end if;
            insert into memberships (user_id, tenant_id, role)
            values (p_user, v_invite.tenant_id, v_invite.role)
            on conflict (user_id, tenant_id) do nothing;
            update invites set accepted_at = now() where id = v_invite.id;
            return query select v_invite.tenant_id, v_invite.role;
        end
        $$
        """
    )
    op.execute("revoke execute on function accept_invite(text, uuid) from public")

    # --- Runtime role -------------------------------------------------------
    # On any database where the role already exists — staging, production,
    # anything bootstrapped by infra/staging-roles.sql — this is a no-op and
    # only the grants below apply.
    #
    # When it is missing, the password comes from OPS_APP_PASSWORD. It used to
    # be the literal 'ops_app', on the assumption that production would always
    # have run staging-roles.sql first. Railway runs `alembic upgrade head`
    # automatically as a pre-deploy hook and that manual step is documented for
    # the Compose path, so the assumption did not hold: a database first
    # migrated on Railway got a credential published in this repo, with DML on
    # every table and nothing anywhere saying so.
    #
    # Dev and CI keep the shared literal deliberately — tests/conftest.py
    # connects as ops_app:ops_app — but only where ENVIRONMENT says dev.
    # Anywhere else, a missing password is a hard stop rather than a default.
    role_exists = (
        op.get_bind().execute(sa.text("select 1 from pg_roles where rolname = 'ops_app'")).scalar()
    )
    if not role_exists:
        password = os.environ.get("OPS_APP_PASSWORD", "")
        if not password:
            if os.environ.get("ENVIRONMENT", "dev") != "dev":
                raise RuntimeError(
                    "Role 'ops_app' does not exist and OPS_APP_PASSWORD is not"
                    " set. Create it with a generated password first (see"
                    " infra/staging-roles.sql), or set OPS_APP_PASSWORD for"
                    " this migration run. Refusing to invent a default: the"
                    " previous one was published in this repository."
                )
            password = "ops_app"
        # %L is Postgres's own literal quoting — DDL takes no bind parameters,
        # so the alternative is escaping a password by hand. The cast is
        # required: inside format() the server cannot infer the parameter's
        # type and fails with "could not determine data type of parameter $1".
        create_role = (
            op.get_bind()
            .execute(
                sa.text(
                    "select format('create role ops_app login password %L', cast(:pw as text))"
                ),
                {"pw": password},
            )
            .scalar()
        )
        op.execute(create_role)
    op.execute("grant usage on schema public to ops_app")
    op.execute("grant select, insert, update, delete on all tables in schema public to ops_app")
    op.execute(
        "alter default privileges in schema public"
        " grant select, insert, update, delete on tables to ops_app"
    )
    op.execute("grant execute on function accept_invite(text, uuid) to ops_app")
    op.execute("grant execute on function app_current_user() to ops_app")
    op.execute("grant execute on function app_current_tenant() to ops_app")


def downgrade() -> None:
    op.execute("drop function if exists accept_invite(text, uuid)")
    for table in reversed(STANDARD_TENANT_TABLES):
        op.execute(f"drop table if exists {table} cascade")
    op.execute("drop table if exists memberships cascade")
    op.execute("drop table if exists tenants cascade")
    op.execute("drop function if exists app_current_tenant()")
    op.execute("drop function if exists app_current_user()")
    op.execute(
        "alter default privileges in schema public"
        " revoke select, insert, update, delete on tables from ops_app"
    )
    op.execute("drop extension if exists pg_trgm")
    op.execute("drop extension if exists vector")
