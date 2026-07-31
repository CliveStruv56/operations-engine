-- Staging role bootstrap (checklist §2) — run once as the `ops` superuser
-- BEFORE the first `alembic upgrade head`, replacing the placeholder password.
--
-- Migration 0001 creates ops_app with a dev password only `if not exists`;
-- pre-creating it here means staging gets the strong password and the
-- migration just applies grants. ops_app must stay RLS-enforced: LOGIN only —
-- no ownership, no BYPASSRLS, no CREATEROLE (the isolation suite depends on
-- this; see CLAUDE.md hard constraint 2).

create role ops_app login password :'ops_app_password';

-- Usage:
--   psql "$DATABASE_URL" -v ops_app_password='<generated>' -f infra/staging-roles.sql
