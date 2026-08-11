"""Idempotent loader for shared platform reference data.

Same contract as `app.groundwork.seeds` and `app.grants.seeds`: reference data
is seed rows, never code, and every fixture upserts by key so re-running is
safe. Run with the OWNER connection (the migrations role) — the runtime role
has select only:

    uv run python -m app.refdata.seeds

The fixture ships **only question sets we author ourselves**, and the reason
is worth stating because it is the opposite of the funder catalogue's.

`grant_ref_funders` can ship recalled facts marked unverified, because a wrong
eligibility summary is a prompt to go and check. A question set cannot. Its
content is the exact wording of a funder's question and the exact character
limit on the field behind it, and a wrong limit produces an answer that will
not paste — the consultant finds out at the portal, after the writing is done.
An approximate question set is worse than no question set.

So real funders arrive by transcription, at `status='unverified'`, with a
`source_url` pointing at the published guidance they were copied from. An
operator promotes one to `status='open'` after a second read. Until then the
catalogue badges it and any draft built from it carries the warning block.
"""

import asyncio
import json
from datetime import date
from pathlib import Path

import asyncpg

FIXTURES = Path(__file__).parent / "fixtures"
QUESTION_SET_FILE = "question_sets.json"

#: The only status a fixture row may ship as. Asserted by the test suite: a
#: fixture claiming `status='open'` would put unchecked question wording and
#: unchecked character limits in front of a consultant with nothing attached
#: to say so.
SEED_STATUS = "template"


async def seed_question_sets(conn: asyncpg.Connection) -> int:
    fixture = json.loads((FIXTURES / QUESTION_SET_FILE).read_text())
    for row in fixture["question_sets"]:
        await conn.execute(
            """
            insert into ref_question_sets (key, name, funder, programme_keys, funder_keys,
                stage, source_url, questions, status, last_verified, next_review, notes)
            values ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
            on conflict (key) do update set
                name = excluded.name, funder = excluded.funder,
                programme_keys = excluded.programme_keys,
                funder_keys = excluded.funder_keys, stage = excluded.stage,
                source_url = excluded.source_url, questions = excluded.questions,
                notes = excluded.notes
            """,
            row["key"],
            row["name"],
            row["funder"],
            row["programme_keys"],
            row["funder_keys"],
            row["stage"],
            row["source_url"],
            json.dumps(row["questions"]),
            row["status"],
            date.fromisoformat(row["last_verified"]),
            date.fromisoformat(row["next_review"]),
            row["notes"],
        )
    return len(fixture["question_sets"])


async def _main() -> None:
    from app.config import get_settings

    conn = await asyncpg.connect(get_settings().database_url)
    try:
        count = await seed_question_sets(conn)
        curated = await conn.fetchval(
            "select count(*) from ref_question_sets where status <> $1", SEED_STATUS
        )
        print(f"Seeded {count} question set(s) from the fixture")
        print(
            f"  {curated} curated funder set(s) already in the catalogue.\n"
            "  Real funder sets are transcribed, not seeded — open the funder's own\n"
            "  published question list, copy each question verbatim with its stated\n"
            "  limit, record source_url, and insert with status='unverified'."
        )
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(_main())
