"""Hybrid retrieval (spec §5): pgvector cosine + tsvector full-text fused by
reciprocal rank, top 8 chunks handed to chat as citeable context.

`Scope` is the project-partitioning hook (Slice 4.5): `restrict_to` hard-limits
the candidate documents, `weights` boosts a document's contribution to the
fused score (project docs > 1.0, primary docs higher still). Slice 4 always
retrieves with scope=None — whole vault, equal weight.
"""

from dataclasses import dataclass, field
from uuid import UUID

import asyncpg

RRF_K = 60
CANDIDATES_PER_ARM = 24
TOP_N = 8
# Fusion boosts for project-scoped chat (Slice 4.5): the whole vault stays in
# the candidate pool, but the conversation's project docs rank first and its
# primary docs first of all.
PROJECT_WEIGHT = 1.5
PRIMARY_WEIGHT = 2.25
# A file dropped into this conversation outranks everything — attaching it is
# the most explicit relevance signal a person can give. Still a boost, not a
# restriction: the rest of the vault stays in the pool for the questions the
# attachment does not answer.
ATTACHED_WEIGHT = 3.0
# Vector candidates below this cosine similarity are noise, not evidence —
# dropping them here is what makes "the vault doesn't cover this" honest.
SIM_FLOOR = 0.25


@dataclass(frozen=True)
class Scope:
    restrict_to: frozenset[UUID] | None = None
    weights: dict[UUID, float] = field(default_factory=dict)

    def weight(self, document_id: UUID) -> float:
        return self.weights.get(document_id, 1.0)


@dataclass
class RetrievedChunk:
    chunk_id: UUID
    document_id: UUID
    title: str
    heading_path: list[str]
    page_start: int | None
    page_end: int | None
    content: str
    score: float = 0.0


def _to_chunk(row: asyncpg.Record) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=row["id"],
        document_id=row["document_id"],
        title=row["title"],
        heading_path=list(row["heading_path"] or []),
        page_start=row["page_start"],
        page_end=row["page_end"],
        content=row["content"],
    )


_SELECT = """
    select c.id, c.document_id, d.title, c.heading_path,
           c.page_start, c.page_end, c.content
"""
_FROM = """
    from doc_chunks c
    join documents d on d.id = c.document_id and d.status = 'ready'
"""


async def vector_candidates(
    conn: asyncpg.Connection, embedding: list[float], scope: Scope | None
) -> list[asyncpg.Record]:
    """Top-24 by cosine; the order-by expression must match the HNSW index
    expression from migration 0001 (embedding::halfvec) to use it."""
    vec = "[" + ",".join(f"{x:.7g}" for x in embedding) + "]"
    restrict_to = scope.restrict_to if scope else None
    restrict = "and c.document_id = any($3)" if restrict_to else ""
    args: list = [vec, SIM_FLOOR]
    if restrict_to:
        args.append(list(restrict_to))
    return await conn.fetch(
        f"""
        {_SELECT}, 1 - (c.embedding::halfvec(2048) <=> $1::halfvec(2048)) as similarity
        {_FROM}
        where c.embedding is not null {restrict}
          and 1 - (c.embedding::halfvec(2048) <=> $1::halfvec(2048)) >= $2
        order by c.embedding::halfvec(2048) <=> $1::halfvec(2048)
        limit {CANDIDATES_PER_ARM}
        """,
        *args,
    )


async def text_candidates(
    conn: asyncpg.Connection, query: str, scope: Scope | None
) -> list[asyncpg.Record]:
    restrict_to = scope.restrict_to if scope else None
    restrict = "and c.document_id = any($2)" if restrict_to else ""
    args: list = [query]
    if restrict_to:
        args.append(list(restrict_to))
    return await conn.fetch(
        f"""
        {_SELECT}, ts_rank_cd(c.tsv, q) as rank
        {_FROM}, websearch_to_tsquery('english', $1) q
        where c.tsv @@ q {restrict}
        order by rank desc
        limit {CANDIDATES_PER_ARM}
        """,
        *args,
    )


def fuse(
    ranked_lists: list[list[RetrievedChunk]],
    scope: Scope | None = None,
    top_n: int = TOP_N,
) -> list[RetrievedChunk]:
    """Reciprocal-rank fusion: score = Σ weight(doc) / (RRF_K + rank)."""
    scope = scope or Scope()
    by_id: dict[UUID, RetrievedChunk] = {}
    for chunks in ranked_lists:
        for rank, chunk in enumerate(chunks, start=1):
            entry = by_id.setdefault(chunk.chunk_id, chunk)
            entry.score += scope.weight(chunk.document_id) / (RRF_K + rank)
    return sorted(by_id.values(), key=lambda c: c.score, reverse=True)[:top_n]


async def retrieve(
    conn: asyncpg.Connection,
    embedding: list[float],
    query: str,
    scope: Scope | None = None,
) -> list[RetrievedChunk]:
    """Hybrid search under the caller's tenant transaction (RLS applies).
    The query embedding is produced by the caller — network calls never
    happen inside a tenant transaction."""
    vec_rows = await vector_candidates(conn, embedding, scope)
    txt_rows = await text_candidates(conn, query, scope)
    return fuse([[_to_chunk(r) for r in vec_rows], [_to_chunk(r) for r in txt_rows]], scope)
