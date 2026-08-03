"""Gate checklist mechanics — doc-kind items derive their done state from the
document registry; manual items are toggled by users.

Mirrors `app/groundwork/gates.py`. Kept module-local rather than shared: the
two modules' gates happen to agree today, and a shared helper would make the
next divergence a refactor of both.
"""

import json
from uuid import UUID

import asyncpg

DOC_DONE_STATUSES = ("final", "submitted")


async def recompute_doc_gates(
    conn: asyncpg.Connection, application_id: UUID, doc_type_key: str, doc_status: str
) -> None:
    """Flip every doc-kind gate item referencing this document type, so a gate
    can never disagree with the registry it reads from."""
    done = doc_status in DOC_DONE_STATUSES
    stages = await conn.fetch(
        "select id, gate from grant_stages where application_id = $1", application_id
    )
    for stage in stages:
        gate = json.loads(stage["gate"])
        changed = False
        for item in gate:
            if item.get("kind") == "doc" and item.get("ref") == doc_type_key:
                if item["done"] != done:
                    item["done"] = done
                    changed = True
        if changed:
            await conn.execute(
                "update grant_stages set gate = $2 where id = $1", stage["id"], json.dumps(gate)
            )
