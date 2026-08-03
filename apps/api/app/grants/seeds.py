"""Idempotent loader for Grantwork platform reference data.

Same contract as `app.groundwork.seeds`: reference data is seed rows, never
code, and every fixture upserts by key so re-running is safe. Run with the
OWNER connection (the migrations role) — the runtime role has select only:

    uv run python -m app.grants.seeds

`grant_ref_templates` holds our own product decisions (the application spine,
its standard tasks, the required-document set and the conditions commonly
attached to an award). `grant_ref_funders` holds external fact about real
funders and is loaded separately, because every row there carries a
`last_verified` date that somebody has to actually earn.
"""

import asyncio
import json
from pathlib import Path

import asyncpg

FIXTURES = Path(__file__).parent / "fixtures"
TEMPLATE_FILES = ["project_grant.json"]


async def seed_reference_data(conn: asyncpg.Connection) -> dict[str, int]:
    for filename in TEMPLATE_FILES:
        template = json.loads((FIXTURES / filename).read_text())
        await conn.execute(
            """
            insert into grant_ref_templates (key, version, payload)
            values ($1, $2, $3)
            on conflict (key) do update set version = excluded.version,
                                            payload = excluded.payload
            """,
            template["key"],
            template["version"],
            json.dumps(template["payload"]),
        )
    return {"templates": len(TEMPLATE_FILES)}


async def _main() -> None:
    from app.config import get_settings

    conn = await asyncpg.connect(get_settings().database_url)
    try:
        counts = await seed_reference_data(conn)
        print(f"Seeded {counts['templates']} Grantwork template(s)")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(_main())
