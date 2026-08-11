"""Publishing a workspace's transcribed form into the platform catalogue.

This is the moat being built, one form at a time: a set that lives in
`ref_question_sets` is read by every workspace, and drafts against it carry no
"we have not checked this" warning. So the bar to get in is deliberately
higher than the bar to transcribe one for yourself.

Three gates, and each exists because of a specific way this could go wrong:

- The source set must be **verified and in date**. Promoting an unverified one
  would publish question wording and character limits nobody has read against
  the funder's own form — the exact thing the seed fixture is forbidden from
  doing, arriving by a different door.
- **No question may be missing its limit.** A blank limit is honest in a
  workspace's own copy, where the person who left it blank knows. Published,
  it is a silent gap in somebody else's draft.
- The operator must **affirm they checked it too**. A tenant verifying a form
  for their own use is not the same act as making it everybody's.

Runs on the owner connection because `ref_question_sets` has no tenant to
scope it to and is read-only to the runtime role (ASSUMPTIONS #28).
"""

import json
from typing import Any

import asyncpg

from app.errors import ApiError
from app.refdata.schemas import PromoteCandidate, PromoteIn

#: How long a promoted row stands before it is due for re-reading. Matches the
#: funder catalogue's convention.
REVIEW_DAYS = 90


def _loads(value: Any) -> Any:
    return json.loads(value) if isinstance(value, str) else value


async def list_candidates(conn: asyncpg.Connection) -> list[PromoteCandidate]:
    """Every workspace's transcribed forms, newest first.

    Cross-tenant by nature — the operator is looking for work worth
    publishing, and it could be in any workspace.
    """
    rows = await conn.fetch(
        """
        select q.tenant_id, t.name as tenant_name, q.key, q.name, q.funder, q.stage,
               q.status, q.source_url, q.questions, q.last_verified, q.next_review,
               (q.next_review <= current_date) as stale,
               exists (select 1 from ref_question_sets r where r.key = q.key) as in_catalogue
        from tenant_question_sets q
        join tenants t on t.id = q.tenant_id
        order by q.updated_at desc
        """
    )
    out = []
    for row in rows:
        questions = _loads(row["questions"]) or []
        out.append(
            PromoteCandidate(
                **{
                    k: row[k]
                    for k in (
                        "tenant_id",
                        "tenant_name",
                        "key",
                        "name",
                        "funder",
                        "stage",
                        "status",
                        "source_url",
                        "last_verified",
                        "next_review",
                        "stale",
                        "in_catalogue",
                    )
                },
                question_count=len(questions),
                limits_missing=sum(1 for q in questions if q.get("limit") is None),
            )
        )
    return out


async def promote(conn: asyncpg.Connection, body: PromoteIn) -> dict:
    """Copy one tenant set into the platform catalogue. Returns audit meta."""
    if not body.confirmed_against_source:
        raise ApiError(
            422,
            "confirmation_required",
            "Confirm you have read these questions and limits against the funder's own form",
        )

    row = await conn.fetchrow(
        """
        select key, name, funder, stage, source_url, questions, status, notes,
               programme_keys, funder_keys, (next_review <= current_date) as stale
        from tenant_question_sets where tenant_id = $1 and key = $2
        """,
        body.tenant_id,
        body.key,
    )
    if row is None:
        raise ApiError(404, "not_found", "That workspace has no form with that key")
    if row["status"] != "open" or row["stale"]:
        raise ApiError(
            422,
            "source_unverified",
            "The workspace has not confirmed this form against the funder's own form yet",
        )

    questions = _loads(row["questions"]) or []
    if not questions:
        raise ApiError(422, "no_questions", "That form has no questions on it")
    missing = [q["id"] for q in questions if q.get("limit") is None]
    if missing:
        raise ApiError(
            422,
            "limits_missing",
            f"{len(missing)} question(s) have no limit recorded. A blank limit is a silent "
            "gap in every workspace's draft once this is published.",
        )
    if not row["source_url"]:
        raise ApiError(
            422, "source_url_required", "A published form must say where its questions came from"
        )

    exists = await conn.fetchval("select 1 from ref_question_sets where key = $1", body.key)
    if exists and not body.replace:
        raise ApiError(
            409,
            "already_published",
            "The catalogue already holds this key — publish again with replace to update it",
        )

    await conn.execute(
        f"""
        insert into ref_question_sets (key, name, funder, programme_keys, funder_keys, stage,
                                       source_url, questions, status, last_verified,
                                       next_review, notes)
        values ($1, $2, $3, $4, $5, $6, $7, $8, 'open', current_date,
                current_date + {REVIEW_DAYS}, $9)
        on conflict (key) do update set
            name = excluded.name, funder = excluded.funder, stage = excluded.stage,
            source_url = excluded.source_url, questions = excluded.questions,
            status = excluded.status, last_verified = excluded.last_verified,
            next_review = excluded.next_review, notes = excluded.notes
        """,
        row["key"],
        row["name"],
        row["funder"],
        list(row["programme_keys"] or []),
        list(row["funder_keys"] or []),
        row["stage"],
        row["source_url"],
        json.dumps(questions),
        body.notes or row["notes"],
    )
    return {
        "key": row["key"],
        "funder": row["funder"],
        "questions": len(questions),
        "source_tenant": str(body.tenant_id),
        "replaced": bool(exists),
    }


async def withdraw(conn: asyncpg.Connection, key: str) -> None:
    """Remove a form from the catalogue.

    Workspaces that already drafted against it keep their answer sheets —
    those live on the job row — and any workspace that transcribed its own
    copy still has it.
    """
    removed = await conn.fetchval("delete from ref_question_sets where key = $1 returning key", key)
    if removed is None:
        raise ApiError(404, "not_found", "The catalogue has no form with that key")
