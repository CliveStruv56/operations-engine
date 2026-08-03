"""The funder-facing impact card: content blocks and the guarantees that make
it safe to send outward. PDF rendering is a skippable test — WeasyPrint needs
system pango, absent in worker CI.
"""

from datetime import date

import pytest

from tests.test_grants_pipeline import (
    LATER_PERIOD_ID,
    MEASURE_ID,
    PERIOD_ID,
    TODAY,
    _pack,
    _period,
)
from worker.grants.context import ConditionFacts, OutcomeFacts
from worker.grants.impact_card import DEFAULT_ACCENT, NOT_RECORDED, build_html, render_pdf

ACCENT = "#123456"


def _html(pack=None, accent=ACCENT) -> str:
    return build_html(pack or _pack(kind="impact_card", target_period_id=None), accent, TODAY)


def test_card_shows_the_grant_headline_facts():
    html = _html()
    assert "Community garden project" in html
    assert "Borough Community Foundation" in html
    assert "£27,500" in html  # the award, not the ask
    assert "03 August 2026" in html


def test_card_falls_back_to_the_ask_before_a_decision():
    pack = _pack(kind="impact_card", target_period_id=None)
    pack.application.amount_awarded = None
    assert "£30,000" in _html(pack)


def test_measures_render_with_a_capped_bar_but_a_true_figure():
    """Over-delivery must not draw a bar wider than its track, but the number
    beside it stays honest."""
    pack = _pack(
        kind="impact_card",
        target_period_id=None,
        outcomes=[OutcomeFacts(measure_id=MEASURE_ID, reporting_period_id=PERIOD_ID, value=500.0)],
    )
    html = _html(pack)
    assert "500 people" in html
    assert "200%" in html
    assert "width:100%" in html  # capped


def test_unrecorded_measures_say_so_rather_than_showing_zero():
    html = _html()
    assert NOT_RECORDED in html


def test_narratives_are_the_charitys_own_words_newest_first():
    pack = _pack(
        kind="impact_card",
        target_period_id=None,
        periods=[_period(), _period(LATER_PERIOD_ID, "Year 2", date(2027, 4, 1))],
        outcomes=[
            OutcomeFacts(
                measure_id=MEASURE_ID,
                reporting_period_id=PERIOD_ID,
                value=180.0,
                narrative="First year narrative.",
            ),
            OutcomeFacts(
                measure_id=MEASURE_ID,
                reporting_period_id=LATER_PERIOD_ID,
                value=260.0,
                narrative="Second year narrative.",
            ),
        ],
    )
    html = _html(pack)
    assert html.index("Second year narrative.") < html.index("First year narrative.")


def test_conditions_block_counts_discharged_and_names_outstanding():
    pack = _pack(
        kind="impact_card",
        target_period_id=None,
        conditions=[
            ConditionFacts(number="1", description="Acknowledge the funder", status="discharged"),
            ConditionFacts(number="2", description="Submit returns", status="outstanding"),
        ],
    )
    html = _html(pack)
    assert "1 of 2 condition(s) discharged" in html
    assert "Outstanding: Submit returns" in html


def test_footer_states_the_provenance_and_flags_overdue_returns():
    pack = _pack(
        kind="impact_card",
        target_period_id=None,
        periods=[_period(status="open", due_date=date(2026, 7, 1), overdue=True)],
    )
    html = _html(pack)
    assert "comes from the organisation&#x27;s own records" in html
    assert "1 monitoring return(s) are past their due date" in html


def test_tenant_accent_colours_the_card_and_defaults_to_hearth():
    assert ACCENT in _html()
    assert DEFAULT_ACCENT.startswith("#")
    pack = _pack(kind="impact_card", target_period_id=None)
    assert DEFAULT_ACCENT in build_html(pack, DEFAULT_ACCENT, TODAY)


def test_content_is_escaped():
    pack = _pack(kind="impact_card", target_period_id=None)
    pack.application.title = "<script>alert(1)</script>"
    assert "<script>" not in _html(pack)
    assert "&lt;script&gt;" in _html(pack)


def test_a_grant_with_no_measures_still_renders():
    pack = _pack(kind="impact_card", target_period_id=None, measures=[], outcomes=[])
    html = _html(pack)
    assert "No impact measures have been recorded" in html
    assert "No outcome narratives have been recorded" in html


def test_pdf_is_one_page():
    pytest.importorskip("weasyprint")
    pdf = render_pdf(_html())
    assert pdf.startswith(b"%PDF")
    assert pdf.count(b"/Type /Page\n") <= 1
