"""Health card (PRD §5.4): derived RAG mirror, decisions derivation, and the
fixed HTML template's six content blocks. PDF rendering itself is covered by
a skippable test — WeasyPrint needs system pango, absent in worker CI."""

from datetime import date

import pytest

from tests.test_drafts_context import _funding, _pack
from worker.drafts.context import BudgetTotals, ConditionFacts, RiskFacts, TaskFacts
from worker.health_card import build_html, compute_rag, decisions_needed, derive_rag

TODAY = date(2026, 7, 31)


def _task(title, due, milestone=True, status="todo"):
    return TaskFacts(
        stage_key="site", title=title, due_date=due, is_milestone=milestone, status=status
    )


def _risk(description, likelihood, impact, status="open"):
    return RiskFacts(
        category="custom",
        description=description,
        likelihood=likelihood,
        impact=impact,
        score=likelihood * impact,
        status=status,
    )


def test_rag_mirror_matches_api_thresholds():
    assert compute_rag(0, 100, 100, 0) == compute_rag(0, 100, 100, 0)
    assert compute_rag(31, 0, 0, 0).programme == "red"
    assert compute_rag(1, 0, 0, 0).programme == "amber"
    assert compute_rag(0, 100, 111, 0).cost == "red"
    assert compute_rag(0, 100, 101, 0).cost == "amber"
    assert compute_rag(0, 0, 0, 16).risk == "red"
    assert compute_rag(0, 0, 0, 9).risk == "amber"
    assert compute_rag(0, 0, 0, 8).risk == "green"


def test_derive_rag_explanations():
    pack = _pack(
        kind="health_card",
        tasks=[_task("Submit planning", date(2026, 7, 21))],  # 10 days late
        budget_totals=BudgetTotals(budget=100, forecast=104, variance=4),
        risks=[_risk("Archaeology find", 4, 4)],
    )
    rag, notes = derive_rag(pack, TODAY)
    assert (rag.programme, rag.cost, rag.risk) == ("amber", "amber", "red")
    assert "10 days late" in notes["programme"]
    assert "£4 over budget" in notes["cost"]
    assert "16 out of 25" in notes["risk"]


def test_decisions_needed_derivation():
    pack = _pack(
        kind="health_card",
        tasks=[_task("Appoint contractor", date(2026, 7, 1))],
        conditions=[
            ConditionFacts(
                number="4", description="Drainage", pre_commencement=True, status="outstanding"
            ),
        ],
        budget_totals=BudgetTotals(budget=500, forecast=500),
        funding=[_funding()],  # nothing secured
    )
    decisions = decisions_needed(pack, TODAY)
    joined = " ".join(decisions)
    assert "Appoint contractor" in joined and "overdue" in joined
    assert "pre-commencement" in joined
    assert "£500 of the scheme cost" in joined

    assert decisions_needed(_pack(kind="health_card"), TODAY) == [
        "No board decisions outstanding."
    ]


def test_build_html_contains_all_six_blocks_and_brand():
    secured = _funding()
    secured.amount_secured = 180000
    pack = _pack(
        kind="health_card",
        tasks=[
            _task("Start on site", date(2026, 9, 1)),
            _task("Practical completion", date(2027, 6, 30)),
            _task("Done milestone", date(2026, 5, 1), status="done"),
        ],
        budget_totals=BudgetTotals(budget=2016000, forecast=2072500, variance=56500),
        funding=[secured],
        risks=[_risk("Planning refusal delays the scheme", 3, 4)],
    )
    html_text = build_html(pack, "#123456", TODAY)

    assert "#123456" in html_text  # tenant brand colour on the rule
    for block in (
        "Where the project is",
        "Is it on track?",
        "Money",
        "Next milestones",
        "Top risks in plain words",
        "Decisions needed from the board",
    ):
        assert block in html_text, block
    assert '<div class="stage current">Group</div>' in html_text
    assert "£2,072,500" in html_text and "£180,000" in html_text and "£1,892,500" in html_text
    assert "Start on site" in html_text and "Done milestone" not in html_text
    assert "Planning refusal delays the scheme" in html_text


def test_html_escapes_user_content():
    pack = _pack(kind="health_card", risks=[_risk("<script>alert(1)</script>", 2, 2)])
    html_text = build_html(pack, "#123456", TODAY)
    assert "<script>" not in html_text
    assert "&lt;script&gt;" in html_text


def test_pdf_is_one_page():
    try:
        import weasyprint
    except Exception:  # pango dlopen raises OSError, not ImportError
        pytest.skip("weasyprint runtime libraries unavailable")
    pack = _pack(
        kind="health_card",
        tasks=[_task("Start on site", date(2026, 9, 1))],
        budget_totals=BudgetTotals(budget=2016000, forecast=2072500, variance=56500),
        funding=[_funding()],
        risks=[_risk("Planning refusal delays the scheme", 3, 4)],
    )
    doc = weasyprint.HTML(string=build_html(pack, "#1f6d53", TODAY)).render()
    assert len(doc.pages) == 1
