"""Worker-side hybrid retrieval for vault-grounded drafts — a deliberate
mirror of the API's `app/retrieval.py` (RRF k=60, 24 candidates per arm,
similarity floor 0.25, project-doc fusion boosts). `app.retrieval` is not
importable from the worker package, so the SQL is duplicated here the same
way `embed.py` duplicates the API's LiteLLM client; keep the two in step.

The mechanics are module-agnostic. What differs per vertical is *which*
queries to run and *which* documents to boost, so both are supplied by the
module rather than defined here.

Stays asyncpg + pydantic only so the API test suite can exercise it against
its migrated database.
"""

from uuid import UUID

import asyncpg

from worker.drafting.pack import VaultExcerpt

RRF_K = 60
CANDIDATES_PER_ARM = 24
TOP_N_PER_QUERY = 8
MAX_EXCERPTS = 16
PROJECT_WEIGHT = 1.5
PRIMARY_WEIGHT = 2.25
SIM_FLOOR = 0.25

_SELECT = """
    select c.id, c.document_id, d.title, c.page_start, c.page_end, c.content
"""
_FROM = """
    from doc_chunks c
    join documents d on d.id = c.document_id and d.status = 'ready'
"""


async def project_scope_weights(
    conn: asyncpg.Connection, project_id: UUID
) -> dict[UUID, float]:
    """Project docs outrank the general vault; primary docs outrank all —
    same boosts as project-scoped chat."""
    rows = await conn.fetch(
        "select id, is_primary from documents where project_id = $1", project_id
    )
    return {r["id"]: PRIMARY_WEIGHT if r["is_primary"] else PROJECT_WEIGHT for r in rows}


async def _vector_candidates(
    conn: asyncpg.Connection, embedding: list[float]
) -> list[asyncpg.Record]:
    vec = "[" + ",".join(f"{x:.7g}" for x in embedding) + "]"
    return await conn.fetch(
        f"""
        {_SELECT}
        {_FROM}
        where c.embedding is not null
          and 1 - (c.embedding::halfvec(2048) <=> $1::halfvec(2048)) >= $2
        order by c.embedding::halfvec(2048) <=> $1::halfvec(2048)
        limit {CANDIDATES_PER_ARM}
        """,
        vec,
        SIM_FLOOR,
    )


async def _text_candidates(conn: asyncpg.Connection, query: str) -> list[asyncpg.Record]:
    return await conn.fetch(
        f"""
        {_SELECT}, ts_rank_cd(c.tsv, q) as rank
        {_FROM}, websearch_to_tsquery('english', $1) q
        where c.tsv @@ q
        order by rank desc
        limit {CANDIDATES_PER_ARM}
        """,
        query,
    )


def _to_excerpt(row: asyncpg.Record) -> VaultExcerpt:
    return VaultExcerpt(
        chunk_id=row["id"],
        document_id=row["document_id"],
        title=row["title"],
        page_start=row["page_start"],
        page_end=row["page_end"],
        content=row["content"],
    )


def fuse(
    ranked_lists: list[list[VaultExcerpt]],
    weights: dict[UUID, float],
    top_n: int = TOP_N_PER_QUERY,
) -> list[VaultExcerpt]:
    """Reciprocal-rank fusion: score = Σ weight(doc) / (RRF_K + rank)."""
    scores: dict[UUID, float] = {}
    by_id: dict[UUID, VaultExcerpt] = {}
    for chunks in ranked_lists:
        for rank, chunk in enumerate(chunks, start=1):
            by_id.setdefault(chunk.chunk_id, chunk)
            weight = weights.get(chunk.document_id, 1.0)
            scores[chunk.chunk_id] = scores.get(chunk.chunk_id, 0.0) + weight / (RRF_K + rank)
    ranked = sorted(by_id.values(), key=lambda c: scores[c.chunk_id], reverse=True)
    return ranked[:top_n]


async def retrieve_excerpts(
    conn: asyncpg.Connection,
    queries: list[str],
    embeddings: list[list[float]],
    weights: dict[UUID, float],
) -> list[VaultExcerpt]:
    """Run every fixed query (embeddings produced by the caller, outside the
    tenant transaction), fuse per query, then union across queries capped at
    MAX_EXCERPTS unique chunks."""
    merged: dict[UUID, VaultExcerpt] = {}
    for query, embedding in zip(queries, embeddings, strict=True):
        vec_rows = await _vector_candidates(conn, embedding)
        txt_rows = await _text_candidates(conn, query)
        fused = fuse(
            [[_to_excerpt(r) for r in vec_rows], [_to_excerpt(r) for r in txt_rows]], weights
        )
        for excerpt in fused:
            merged.setdefault(excerpt.chunk_id, excerpt)
    return list(merged.values())[:MAX_EXCERPTS]
