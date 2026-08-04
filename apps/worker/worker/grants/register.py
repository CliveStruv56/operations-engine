"""Draft registration: find or create the registry row, append an
append-only version, set status 'drafting' — draft-first, so nothing ever
advances further without a human — audit-log the job and mark it succeeded.
Metering is the engine's (`drafting/usage.py`), so a failed job is billed
too; the `ledger` here only feeds the audit meta and the job row's totals.

Runs entirely inside one tenant transaction after the DOCX is already in
storage, so an abort anywhere earlier leaves no orphaned registry rows.

`grant_documents` has `unique (application_id, doc_type_key)`, so per-instance
documents get suffixed keys the same way Groundwork's do (ASSUMPTIONS #9).
Only monitoring returns are per-instance here: an application has many
reporting periods but exactly one case for support, one bid and one final
evaluation, which version onto their seeded launcher rows.
"""

import json
from datetime import UTC, datetime
from uuid import UUID

import asyncpg

from worker.drafting.assemble import AssembledDraft
from worker.drafting.llm import LlmLedger
from worker.grants.context import DOC_TITLES, GrantPack

#: Stage a registry row falls back to when its seeded launcher is missing.
_STAGE_FALLBACK = {
    "case_for_support": "case",
    "funding_application": "apply",
    "monitoring_report": "monitor",
    "impact_evaluation": "evaluate",
}


def registry_target(pack: GrantPack) -> tuple[str, str]:
    """(doc_type_key, title) for the registry row this draft lands on."""
    if pack.kind == "monitoring_report":
        period = pack.target_period()
        suffix = str(pack.target_period_id).replace("-", "")[:8]
        label = period.label if period else "period"
        return f"monitoring_report_{suffix}", f"{DOC_TITLES[pack.kind]} — {label}"
    return pack.kind, DOC_TITLES[pack.kind]


async def _target_row(
    conn: asyncpg.Connection, tenant_id: str, application_id: str, pack: GrantPack
) -> asyncpg.Record:
    doc_type_key, title = registry_target(pack)
    row = await conn.fetchrow(
        "select * from grant_documents where application_id = $1 and doc_type_key = $2",
        UUID(application_id),
        doc_type_key,
    )
    if row is not None:
        return row
    stage_key = await conn.fetchval(
        "select stage_key from grant_documents where application_id = $1 and doc_type_key = $2",
        UUID(application_id),
        pack.kind,
    )
    return await conn.fetchrow(
        """
        insert into grant_documents (tenant_id, application_id, doc_type_key, title,
                                     stage_key, reporting_period_id)
        values ($1, $2, $3, $4, $5, $6)
        returning *
        """,
        UUID(tenant_id),
        UUID(application_id),
        doc_type_key,
        title,
        stage_key or _STAGE_FALLBACK[pack.kind],
        # Instance rows carry the obligation they answer, so the registry can
        # show which return discharged which period.
        pack.target_period_id,
    )


async def register_draft(
    conn: asyncpg.Connection,
    *,
    tenant_id: str,
    subject_id: str,
    user_id: str,
    job_id: str,
    pack: GrantPack,
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
        update grant_documents
        set versions = $2, current_file_key = $3, status = 'drafting', updated_at = now()
        where id = $1
        """,
        doc["id"],
        json.dumps(versions),
        file_key,
    )

    # Drafting a monitoring return moves its obligation off "upcoming" — the
    # calendar must not still say nothing has started.
    if pack.kind == "monitoring_report" and pack.target_period_id is not None:
        await conn.execute(
            """
            update grant_reporting_periods set status = 'drafting', updated_at = now()
            where id = $1 and status in ('upcoming', 'open')
            """,
            pack.target_period_id,
        )

    await conn.execute(
        """
        insert into audit_log (tenant_id, user_id, action, target_type, target_id, meta)
        values ($1, $2, 'grants.draft', 'grant_document', $3, $4)
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
        update grant_draft_jobs
        set status = 'succeeded', document_id = $2, file_key = $3, to_confirm_count = $4,
            llm_calls = $5, tokens_in = $6, tokens_out = $7, cost_usd = $8, updated_at = now()
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
    )
    return doc["id"]
