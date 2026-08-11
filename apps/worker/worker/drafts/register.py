"""Draft registration (PRD §5 step 5): find or create the registry row,
append an append-only version entry, set status 'drafting' (draft-first —
nothing ever advances further without a human), audit-log the job, and mark
the job row succeeded. Metering is the engine's (`drafting/usage.py`), so a
failed job is billed too; the `ledger` here only feeds the audit meta and the
job row's totals.

Runs entirely inside one tenant transaction after the DOCX is already in
storage — an abort anywhere earlier leaves no orphaned registry rows.

Monthly reports and funding bids are per-instance documents, but
proj_documents has unique (project_id, doc_type_key), so instances get
suffixed keys (monthly_report_2026_07, funding_bid_<id8>) alongside the
seeded launcher row (ASSUMPTIONS.md #9)."""

import json
import re
from datetime import UTC, datetime
from uuid import UUID

import asyncpg

from worker.drafting.assemble import AssembledDraft
from worker.drafting.llm import LlmLedger
from worker.drafts.context import ContextPack

# Fallback stage for instance rows when the seeded launcher row is missing.
_STAGE_FALLBACK = {
    "monthly_report": "build",
    "feasibility_study": "plan",
    "funding_bid": "plan",
    "application_form": "plan",
}

_KEY_SAFE = re.compile(r"[^a-z0-9]+")


def registry_target(pack: ContextPack) -> tuple[str, str]:
    """(doc_type_key, title) for the registry row this draft lands on."""
    if pack.kind == "monthly_report":
        month = pack.report_month or pack.generated_on.strftime("%Y-%m")
        label = datetime.strptime(month, "%Y-%m").strftime("%B %Y")
        return f"monthly_report_{month.replace('-', '_')}", f"Monthly client report — {label}"
    if pack.kind == "funding_bid":
        source = pack.target_funding()
        suffix = str(pack.target_funding_id).replace("-", "")[:8]
        name = source.name if source else "funding source"
        return f"funding_bid_{suffix}", f"Funding application — {name}"
    if pack.kind == "application_form":
        # One registry row per form, so redrafting the same funder's questions
        # appends a version rather than growing a row per attempt.
        question_set = pack.question_set
        suffix = _KEY_SAFE.sub("_", question_set.key.lower()).strip("_")[:40]
        return f"application_form_{suffix}", f"{question_set.name} — {question_set.funder}"
    return "feasibility_study", "Feasibility study"


async def _target_row(
    conn: asyncpg.Connection, tenant_id: str, project_id: str, pack: ContextPack
) -> asyncpg.Record:
    doc_type_key, title = registry_target(pack)
    row = await conn.fetchrow(
        "select * from proj_documents where project_id = $1 and doc_type_key = $2",
        UUID(project_id),
        doc_type_key,
    )
    if row is not None:
        return row
    stage_key = await conn.fetchval(
        "select stage_key from proj_documents where project_id = $1 and doc_type_key = $2",
        UUID(project_id),
        pack.kind,
    )
    return await conn.fetchrow(
        """
        insert into proj_documents (tenant_id, project_id, doc_type_key, title, stage_key)
        values ($1, $2, $3, $4, $5)
        returning *
        """,
        UUID(tenant_id),
        UUID(project_id),
        doc_type_key,
        title,
        stage_key or _STAGE_FALLBACK[pack.kind],
    )


async def register_draft(
    conn: asyncpg.Connection,
    *,
    tenant_id: str,
    subject_id: str,
    user_id: str,
    job_id: str,
    pack: ContextPack,
    file_key: str,
    ledger: LlmLedger,
    draft: AssembledDraft,
) -> UUID:
    doc = await _target_row(conn, tenant_id, subject_id, pack)
    versions = json.loads(doc["versions"])
    versions.append(
        {
            "version": len(versions) + 1,
            "file_key": file_key,
            "created_at": datetime.now(UTC).isoformat(),
            "created_by": user_id,
            "note": f"AI draft ({draft.to_confirm_count} items to confirm)",
        }
    )
    await conn.execute(
        """
        update proj_documents
        set versions = $2, current_file_key = $3, status = 'drafting', updated_at = now()
        where id = $1
        """,
        doc["id"],
        json.dumps(versions),
        file_key,
    )

    await conn.execute(
        """
        insert into audit_log (tenant_id, user_id, action, target_type, target_id, meta)
        values ($1, $2, 'projects.draft', 'proj_document', $3, $4)
        """,
        UUID(tenant_id),
        UUID(user_id),
        str(doc["id"]),
        json.dumps(
            {
                "kind": pack.kind,
                "job_id": job_id,
                "llm_calls": len(ledger.calls),
                "cost_usd": round(ledger.cost_usd, 6),
                "to_confirm": draft.to_confirm_count,
                "stripped_citations": draft.stripped_citations,
                "truncated_sections": ledger.truncated_calls,
            }
        ),
    )

    await conn.execute(
        """
        update proj_draft_jobs
        set status = 'succeeded', document_id = $2, file_key = $3, to_confirm_count = $4,
            llm_calls = $5, tokens_in = $6, tokens_out = $7, cost_usd = $8,
            answers = $9, updated_at = now()
        where id = $1
        """,
        UUID(job_id),
        doc["id"],
        file_key,
        draft.to_confirm_count,
        len(ledger.calls),
        ledger.tokens_in,
        ledger.tokens_out,
        round(ledger.cost_usd, 6),
        # Null for an ordinary document — the answer sheet only exists for a
        # draft that is answering somebody else's form.
        json.dumps(draft.answers) if draft.answers else None,
    )
    return doc["id"]
