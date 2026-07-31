"""Pure-logic tests for the drafting context pack and retrieval fusion.
The DB-backed gather test lives in the API suite (tests/test_worker_gather.py
there) — worker CI has no Postgres."""

from datetime import date
from uuid import uuid4

import pytest

from worker.drafts.context import (
    BudgetTotals,
    ContextPack,
    FundingSource,
    ProgrammeFacts,
    ProjectFacts,
    VaultExcerpt,
)
from worker.drafts.retrieval import PRIMARY_WEIGHT, PROJECT_WEIGHT, fuse, queries_for


def _project() -> ProjectFacts:
    return ProjectFacts(
        id=uuid4(),
        name="Dev scheme",
        project_type="clh_new_build",
        status="active",
        stage_current="group",
    )


def _pack(**overrides) -> ContextPack:
    base = dict(
        kind="monthly_report",
        generated_on=date(2026, 7, 31),
        project=_project(),
        stages=[],
        tasks=[],
        budget_lines=[],
        budget_totals=BudgetTotals(),
        funding=[],
        programmes=[],
        risks=[],
        conditions=[],
        stakeholders=[],
    )
    base.update(overrides)
    return ContextPack(**base)


def _funding(programme_key=None) -> FundingSource:
    return FundingSource(
        id=uuid4(), programme_key=programme_key, name="CLT grant", kind="grant", status="applying"
    )


def _programme(key: str, status: str = "open") -> ProgrammeFacts:
    return ProgrammeFacts(
        key=key,
        name="Programme",
        funder="Fund Co",
        kind="grant",
        eligibility="CLH bodies",
        status=status,
        last_verified=date(2026, 7, 28),
        next_review=date(2026, 10, 28),
    )


def test_record_counts_reflect_pack_contents():
    source = _funding()
    pack = _pack(funding=[source], excerpts=[])
    counts = pack.record_counts()
    assert counts["funding sources"] == 1
    assert counts["vault excerpts"] == 0
    assert set(counts) >= {"stages", "tasks", "budget lines", "risks"}


def test_target_funding_and_programme_resolution():
    linked = _funding(programme_key="cwmpas_cch")
    other = _funding()
    programme = _programme("cwmpas_cch")
    pack = _pack(
        kind="funding_bid",
        funding=[other, linked],
        programmes=[programme],
        target_funding_id=linked.id,
    )
    assert pack.target_funding() == linked
    assert pack.target_programme() == programme
    # A source without a programme link resolves to no catalogue row.
    pack_no_link = _pack(kind="funding_bid", funding=[other], target_funding_id=other.id)
    assert pack_no_link.target_programme() is None


def _excerpt(doc_id, content="text") -> VaultExcerpt:
    return VaultExcerpt(chunk_id=uuid4(), document_id=doc_id, title="Doc", content=content)


def test_fuse_boosts_project_and_primary_documents():
    vault_doc, project_doc, primary_doc = uuid4(), uuid4(), uuid4()
    weights = {project_doc: PROJECT_WEIGHT, primary_doc: PRIMARY_WEIGHT}
    # Same rank in a single arm: weight alone must decide the order.
    a, b, c = _excerpt(vault_doc), _excerpt(project_doc), _excerpt(primary_doc)
    fused = fuse([[a], [b], [c]], weights)
    assert [e.chunk_id for e in fused] == [c.chunk_id, b.chunk_id, a.chunk_id]


def test_fuse_merges_duplicate_chunks_across_arms():
    doc = uuid4()
    shared = _excerpt(doc)
    solo = _excerpt(doc)
    fused = fuse([[shared, solo], [shared]], {})
    # The chunk in both arms accumulates score and outranks the single-arm one.
    assert fused[0].chunk_id == shared.chunk_id
    assert len(fused) == 2


def test_queries_interpolate_site():
    queries = queries_for("feasibility_study", "1 High Street, Marford")
    assert len(queries) == 4
    assert any("1 High Street, Marford" in q for q in queries)
    assert queries_for("monthly_report", "x") == []


def test_pack_rejects_unknown_kind():
    pack = _pack(kind="feasibility_study")
    assert pack.instructions is None
    payload = pack.model_dump()
    payload["kind"] = "shopping_list"
    with pytest.raises(ValueError):
        ContextPack(**payload)
