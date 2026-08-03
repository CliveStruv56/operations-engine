"""Idempotent loader for Grantwork platform reference data.

Same contract as `app.groundwork.seeds`: reference data is seed rows, never
code, and every fixture upserts by key so re-running is safe. Run with the
OWNER connection (the migrations role) — the runtime role has select only:

    uv run python -m app.grants.seeds

Two fixtures, and the difference between them matters.

`grant_ref_templates` is **our own product decision** — the application
spine, its standard tasks, the required-document set and the conditions
commonly attached to an award. We author it, so we can assert it.

`grant_ref_funders` is **external fact about real funders**, compiled from
model knowledge and never checked by a person. Every row therefore ships
`status='unverified'` with `next_review` equal to `last_verified`, so it is
stale the moment it loads. That is not a defect — it makes both existing
safety mechanisms fire on day one: the catalogue badges the row in the UI,
and any draft parameterised by it carries the first-page warning block
(`status != 'open'`) plus a stale source note. An operator promotes a row by
checking every field against the funder's own current guidance, then setting
`status='open'` and `next_review` 90 days out — in the database, not here.

The upsert is deliberately **narrow on re-run**: it refreshes the descriptive
columns but never touches `status`, `last_verified` or `next_review`, so
re-seeding cannot silently demote a row an operator has verified back to
unverified. Correcting seed *content* is safe; erasing somebody's
verification is not.
"""

import asyncio
import json
from datetime import date
from pathlib import Path

import asyncpg

FIXTURES = Path(__file__).parent / "fixtures"
TEMPLATE_FILES = ["project_grant.json"]
FUNDER_FILE = "funders.json"

#: The state every seeded catalogue row starts in. Asserted by the test suite:
#: a fixture that ships `status='open'` or a future `next_review` would put
#: unchecked funder facts in front of a charity with no warning attached.
SEED_STATUS = "unverified"


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
    funders = await seed_funder_catalogue(conn)
    return {"templates": len(TEMPLATE_FILES), "funders": funders}


async def seed_funder_catalogue(conn: asyncpg.Connection) -> int:
    fixture = json.loads((FIXTURES / FUNDER_FILE).read_text())
    for row in fixture["funders"]:
        await conn.execute(
            """
            insert into grant_ref_funders (key, name, funder, funder_type, nations, kind,
                amount_note, typical_award, match_note, eligibility, status, deadlines,
                route_url, docs_required, reporting_note, last_verified, next_review, notes)
            values ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16,
                    $17, $18)
            on conflict (key) do update set
                name = excluded.name, funder = excluded.funder,
                funder_type = excluded.funder_type, nations = excluded.nations,
                kind = excluded.kind, amount_note = excluded.amount_note,
                typical_award = excluded.typical_award, match_note = excluded.match_note,
                eligibility = excluded.eligibility, deadlines = excluded.deadlines,
                route_url = excluded.route_url, docs_required = excluded.docs_required,
                reporting_note = excluded.reporting_note, notes = excluded.notes
            """,
            row["key"],
            row["name"],
            row["funder"],
            row["funder_type"],
            row["nations"],
            row["kind"],
            row["amount_note"],
            row["typical_award"],
            row["match_note"],
            row["eligibility"],
            row["status"],
            row["deadlines"],
            row["route_url"],
            row["docs_required"],
            row["reporting_note"],
            date.fromisoformat(row["last_verified"]),
            date.fromisoformat(row["next_review"]),
            row["notes"],
        )
    return len(fixture["funders"])


async def _main() -> None:
    from app.config import get_settings

    conn = await asyncpg.connect(get_settings().database_url)
    try:
        counts = await seed_reference_data(conn)
        unverified = await conn.fetchval(
            "select count(*) from grant_ref_funders where status = $1", SEED_STATUS
        )
        print(f"Seeded {counts['templates']} template(s), {counts['funders']} funder row(s)")
        if unverified:
            print(
                f"\n  {unverified} catalogue row(s) are status='{SEED_STATUS}' and stale.\n"
                "  They badge in the UI and warn inside any draft built from them.\n"
                "  Verify each against the funder's own guidance, then set\n"
                "  status='open' and next_review = current_date + 90 in the database."
            )
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(_main())
