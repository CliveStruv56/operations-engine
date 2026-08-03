"""Groundwork's retrieval query sets.

The hybrid-retrieval mechanics (RRF fusion, candidate arms, the similarity
floor and the project/primary boosts) are shared —
`worker/drafting/retrieval.py`. What is Groundwork's is which questions to
ask the vault for each document kind.
"""

from worker.drafting.retrieval import (
    CANDIDATES_PER_ARM,
    MAX_EXCERPTS,
    PRIMARY_WEIGHT,
    PROJECT_WEIGHT,
    RRF_K,
    SIM_FLOOR,
    TOP_N_PER_QUERY,
    fuse,
    project_scope_weights,
    retrieve_excerpts,
)

__all__ = [
    "CANDIDATES_PER_ARM",
    "MAX_EXCERPTS",
    "PRIMARY_WEIGHT",
    "PROJECT_WEIGHT",
    "QUERY_SETS",
    "RRF_K",
    "SIM_FLOOR",
    "TOP_N_PER_QUERY",
    "fuse",
    "queries_for",
    "retrieve_excerpts",
    "scope_weights",
]

# Fixed query sets per draft kind (PRD §5.2 / §5.3). {site} interpolates the
# site address (or project name) for the site-specific arms.
QUERY_SETS: dict[str, list[str]] = {
    "feasibility_study": [
        "site description constraints access services {site}",
        "planning policy local plan context {site}",
        "housing need and demand evidence",
        "comparable community-led housing schemes and build costs",
    ],
    "funding_bid": [
        "evidence of local housing need",
        "community support engagement consultation",
    ],
}

#: Alias kept for the module's own call sites and tests.
scope_weights = project_scope_weights


def queries_for(kind: str, site: str) -> list[str]:
    return [q.format(site=site).strip() for q in QUERY_SETS.get(kind, [])]
