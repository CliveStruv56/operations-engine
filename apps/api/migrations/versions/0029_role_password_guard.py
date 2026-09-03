"""Refuse to migrate a database still using a password published in this repo.

Migration 0001 has, until now, created `ops_app` with the literal password
`ops_app` whenever the role was missing. `infra/staging-roles.sql` is supposed
to pre-empt that with a generated password, but it is a manual step documented
for the Docker Compose path — and staging deploys through Railway, which runs
`alembic upgrade head` as an automatic pre-deploy hook. So the guard against
the default lived on a path nobody uses.

0001 is fixed forward (it now demands OPS_APP_PASSWORD outside dev). That does
nothing for a database already created, which is what this migration is for: it
checks the stored verifiers for `ops` and `ops_app` against the two published
literals and refuses to proceed if either still matches. Failing here fails the
pre-deploy hook, so Railway keeps the previous deployment serving — the site
stays up and the deploy stops, which is the right way round.

Skipped when ENVIRONMENT is dev (the default), where the shared password is the
point: `tests/conftest.py` connects as `ops_app:ops_app` and CI's Postgres
service runs `ops:ops`.

Revision ID: 0029
Revises: 0028
Create Date: 2026-09-03
"""

import os

import sqlalchemy as sa
from alembic import op

from migrations.rolecheck import PUBLISHED_PASSWORDS, password_matches

revision = "0029"
down_revision = "0028"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if os.environ.get("ENVIRONMENT", "dev") == "dev":
        return

    conn = op.get_bind()
    # rolpassword lives in pg_authid, which is superuser-only. A migration role
    # without it cannot answer the question, and "cannot tell" must not block a
    # deploy — so ask permission first rather than letting a failed read abort
    # the surrounding transaction.
    readable = conn.execute(
        sa.text("select has_table_privilege(current_user, 'pg_authid', 'select')")
    ).scalar()
    if not readable:
        return

    rows = conn.execute(
        sa.text("select rolname, rolpassword from pg_authid where rolname = any(:names)"),
        {"names": list(PUBLISHED_PASSWORDS)},
    ).fetchall()

    weak = sorted(
        name for name, stored in rows if password_matches(stored, PUBLISHED_PASSWORDS[name], name)
    )
    if weak:
        raise RuntimeError(
            "Refusing to migrate: database role(s) "
            + ", ".join(repr(n) for n in weak)
            + " still use the password published in this repository. Anyone who"
            " has cloned it can authenticate. Rotate before deploying:\n"
            '  psql "$DATABASE_URL" -c "alter role <role> with password \'<strong>\'"\n'
            "then update APP_DATABASE_URL (api, worker), DATABASE_URL (api),"
            " OPS_DATABASE_URL (backup) and POSTGRES_PASSWORD (postgres) to"
            " match. Verify over the private network, never over localhost —"
            " the postgres image trusts 127.0.0.1 and will accept any password"
            " there. See docs/code-review-sep-2026.md DB-2."
        )


def downgrade() -> None:
    # A guard, not a schema change: nothing to undo.
    pass
