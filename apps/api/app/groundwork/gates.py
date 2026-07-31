"""Gate checklist mechanics (PRD §2.1): doc-kind items derive their done state
from the document registry; manual items are toggled by users."""

import json
from uuid import UUID

import asyncpg

DOC_DONE_STATUSES = ("final", "submitted")


async def recompute_doc_gates(
    conn: asyncpg.Connection, project_id: UUID, doc_type_key: str, doc_status: str
) -> None:
    """Flip every doc-kind gate item referencing this document type. Called on
    any registry status change so gates can never disagree with the registry."""
    done = doc_status in DOC_DONE_STATUSES
    stages = await conn.fetch("select id, gate from proj_stages where project_id = $1", project_id)
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
                "update proj_stages set gate = $2 where id = $1",
                stage["id"],
                json.dumps(gate),
            )
