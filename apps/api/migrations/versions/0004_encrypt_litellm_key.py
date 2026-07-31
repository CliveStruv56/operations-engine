"""Encrypt tenant LiteLLM virtual keys at rest.

Renames tenants.litellm_key_id → litellm_key_encrypted (the old name
disguised that the column holds a live secret — in LiteLLM the token IS its
own id) and Fernet-encrypts existing values with LITELLM_KEY_ENCRYPTION_KEY.
Refuses to run while cleartext keys exist and no encryption key is
configured. Already-encrypted values (Fernet tokens start "gAAAA") are
skipped, so a re-run after a partial failure is safe.

Downgrade renames the column back without decrypting — keep the same
encryption key configured if the values must stay usable, or re-provision
tenant keys.

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-31
"""

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("alter table tenants rename column litellm_key_id to litellm_key_encrypted")

    conn = op.get_bind()
    rows = conn.execute(
        sa.text(
            "select id, litellm_key_encrypted from tenants where litellm_key_encrypted is not null"
        )
    ).fetchall()
    todo = [(r[0], str(r[1])) for r in rows if not str(r[1]).startswith("gAAAA")]
    if not todo:
        return

    from app.config import get_settings

    key = get_settings().litellm_key_encryption_key
    if not key:
        raise RuntimeError(
            f"{len(todo)} tenant(s) hold cleartext LiteLLM keys —"
            " set LITELLM_KEY_ENCRYPTION_KEY before running this migration"
        )
    from cryptography.fernet import Fernet

    fernet = Fernet(key.encode())
    for tenant_id, token in todo:
        conn.execute(
            sa.text("update tenants set litellm_key_encrypted = :value where id = :id"),
            {"value": fernet.encrypt(token.encode()).decode(), "id": tenant_id},
        )


def downgrade() -> None:
    op.execute("alter table tenants rename column litellm_key_encrypted to litellm_key_id")
