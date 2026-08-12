"""Harvesting the facts an organisation just asserted to a funder.

Brief §3.3, and the mechanism that makes the register grow rather than decay:
every bid contains the facts the organisation will be asked for again in six
months, so the moment it says "we submitted this" is the cheapest moment there
will ever be to offer them for the register.

Everything it produces is a proposal. A bid is the organisation repeating a
claim it made somewhere else — worth keeping and worth a second look, never
worth asserting on its own say-so.
"""

import contextlib
import json

import asyncpg

from worker.claims.extract import EXTRACT_ALIAS, harvest_claims
from worker.claims.facts import load_kind_specs, save_proposals
from worker.db import tenant_tx
from worker.secrets import decrypt_llm_key


def _loads(value):
    return json.loads(value) if isinstance(value, str) else value


async def _answers_for(conn: asyncpg.Connection, application_id: str) -> list[tuple[str, str]]:
    """Answer text from this application's finished drafts, newest first.

    Only `application_form` jobs carry answers; an ordinary document's prose
    lives in the DOCX, which we would have to fetch and reparse for a
    by-product feature. Not worth it — the answer sheets are where the facts
    are stated most plainly anyway.
    """
    rows = await conn.fetch(
        """
        select answers from grant_draft_jobs
        where application_id = $1 and status = 'succeeded' and answers is not null
        order by updated_at desc limit 3
        """,
        application_id,
    )
    seen: set[str] = set()
    answers: list[tuple[str, str]] = []
    for row in rows:
        for entry in _loads(row["answers"]) or []:
            question_id = str(entry.get("question_id") or "")
            text = str(entry.get("text") or "").strip()
            # A question answered again in a later draft appears once, with the
            # newest wording — the ordering above is what makes that true.
            if not question_id or not text or question_id in seen:
                continue
            seen.add(question_id)
            answers.append((question_id, text))
    return answers


async def harvest_claims_from_application(
    ctx: dict, tenant_id: str, application_id: str, user_id: str
) -> str:
    """arq job: read a submitted application's answers for durable facts.

    Never raises into arq. Harvesting is a by-product of work somebody already
    finished, so a failure here must be invisible — they submitted their
    application, which is the thing that mattered.
    """
    pool: asyncpg.Pool = ctx["pool"]
    with contextlib.suppress(Exception):
        async with tenant_tx(pool, tenant_id) as conn:
            row = await conn.fetchrow(
                "select title from grant_applications where id = $1", application_id
            )
            if row is None:
                return "gone"
            virtual_key = decrypt_llm_key(
                await conn.fetchval(
                    "select litellm_key_encrypted from tenants where id = $1", tenant_id
                )
            )
            kinds = await load_kind_specs(conn)
            answers = await _answers_for(conn, application_id)

        if not virtual_key or not answers:
            return "nothing to harvest"

        result = await harvest_claims(virtual_key, row["title"], answers, kinds)
        if result is None:
            return "nothing to harvest"

        async with tenant_tx(pool, tenant_id) as conn:
            # Billed whether or not anything was found, for the same reason
            # every other call in this codebase is: the tokens were spent.
            await conn.execute(
                """
                insert into usage_events (tenant_id, user_id, kind, model,
                                          tokens_in, tokens_out, cost_usd)
                values ($1, $2, 'extract', $3, $4, $5, $6)
                """,
                tenant_id,
                user_id,
                EXTRACT_ALIAS,
                result.tokens_in,
                result.tokens_out,
                result.cost_usd,
            )
            written = 0
            if result.facts:
                written = await save_proposals(
                    conn,
                    tenant_id,
                    # The submitted document is not in the vault as a chunked
                    # upload, so a harvested claim points at no chunk and
                    # carries no citation — the same position a register fact
                    # is in, and honest for the same reason.
                    None,
                    user_id,
                    result.facts,
                    source="draft",
                )
        return f"proposed:{written}"
    return "failed"
