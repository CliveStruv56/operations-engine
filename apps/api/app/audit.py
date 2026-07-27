import json
from uuid import UUID

import asyncpg


async def write_audit(
    conn: asyncpg.Connection,
    tenant_id: UUID,
    user_id: UUID,
    action: str,
    target_type: str | None = None,
    target_id: str | None = None,
    meta: dict | None = None,
) -> None:
    await conn.execute(
        """
        insert into audit_log (tenant_id, user_id, action, target_type, target_id, meta)
        values ($1, $2, $3, $4, $5, $6)
        """,
        tenant_id,
        user_id,
        action,
        target_type,
        target_id,
        json.dumps(meta or {}),
    )
