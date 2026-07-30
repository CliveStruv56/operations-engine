"""Idempotent loader for Groundwork platform reference data (PRD §0.7, §2).

Reference data is seed data, never code: the CLH template and funding
catalogue live in fixtures/*.json and upsert by key, so re-running is safe.
Run with the OWNER connection (migrations role):

    uv run python -m app.groundwork.seeds
"""

import asyncio
import json
from datetime import date
from pathlib import Path

import asyncpg

FIXTURES = Path(__file__).parent / "fixtures"


async def seed_reference_data(conn: asyncpg.Connection) -> dict[str, int]:
    template = json.loads((FIXTURES / "clh_new_build.json").read_text())
    await conn.execute(
        """
        insert into proj_ref_templates (key, version, payload)
        values ($1, $2, $3)
        on conflict (key) do update set version = excluded.version,
                                        payload = excluded.payload
        """,
        template["key"],
        template["version"],
        json.dumps(template["payload"]),
    )

    programmes = json.loads((FIXTURES / "programmes.json").read_text())
    for p in programmes:
        await conn.execute(
            """
            insert into proj_ref_programmes (key, name, funder, nations, kind, stage_fit,
                amount_note, match_note, eligibility, status, route_url, docs_required,
                last_verified, next_review, notes)
            values ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15)
            on conflict (key) do update set
                name = excluded.name, funder = excluded.funder,
                nations = excluded.nations, kind = excluded.kind,
                stage_fit = excluded.stage_fit, amount_note = excluded.amount_note,
                match_note = excluded.match_note, eligibility = excluded.eligibility,
                status = excluded.status, route_url = excluded.route_url,
                docs_required = excluded.docs_required,
                last_verified = excluded.last_verified,
                next_review = excluded.next_review, notes = excluded.notes
            """,
            p["key"],
            p["name"],
            p["funder"],
            p["nations"],
            p["kind"],
            p["stage_fit"],
            p["amount_note"],
            p["match_note"],
            p["eligibility"],
            p["status"],
            p["route_url"],
            p["docs_required"],
            date.fromisoformat(p["last_verified"]),
            date.fromisoformat(p["next_review"]),
            p["notes"],
        )
    return {"templates": 1, "programmes": len(programmes)}


async def _main() -> None:
    from app.config import get_settings

    conn = await asyncpg.connect(get_settings().database_url)
    try:
        counts = await seed_reference_data(conn)
        print(f"Seeded {counts['templates']} template(s), {counts['programmes']} programmes")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(_main())
