"""Grantwork's retrieval query sets and vault scoping.

The hybrid-retrieval mechanics (RRF fusion, candidate arms, similarity floor,
per-document boosts) are shared — `worker/drafting/retrieval.py`. What is
Grantwork's is which questions to ask the vault, and which documents to
favour when an application is tied to a Groundwork project.
"""

from uuid import UUID

import asyncpg

from worker.drafting.retrieval import project_scope_weights

#: Fixed query sets per draft kind. `monitoring_report` is deliberately absent:
#: a monitoring return is an account of what this grant did, and those facts
#: live in the module's own rows. An empty list means the engine skips the
#: embedding call entirely, so the cheapest draft is also the best-grounded.
QUERY_SETS: dict[str, list[str]] = {
    "case_for_support": [
        "evidence of need in the community we serve",
        "who our beneficiaries are and what they tell us",
        "outcomes and evaluation of our previous work",
        "letters of support and community consultation",
    ],
    "funding_application": [
        "evidence of local need and demand for this work",
        "community support consultation and partnership letters",
    ],
    "impact_evaluation": [
        "beneficiary stories and case studies",
        "evaluation findings and lessons learned",
    ],
}


def queries_for(kind: str, pack) -> list[str]:  # noqa: ANN001 — pack type is the module's own
    return list(QUERY_SETS.get(kind, []))


async def scope_weights(conn: asyncpg.Connection, application_id: UUID) -> dict[UUID, float]:
    """Boost the linked project's vault documents, when there is one.

    This is the cross-module soft link earning its keep (ASSUMPTIONS #23): a
    bid that funds a Groundwork development project should draw on that
    project's documents first. A standalone application has no project, so it
    retrieves across the tenant's whole vault with no boosts — correct, since
    a charity's need evidence is rarely filed under one project.
    """
    project_id = await conn.fetchval(
        "select project_id from grant_applications where id = $1", application_id
    )
    if project_id is None:
        return {}
    return await project_scope_weights(conn, project_id)
