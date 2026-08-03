"""Grantwork derived figures (PRD §1.2) — pure functions, no database.

These are the numbers a trustee board reads, so the edge cases that matter
are the ones where a wrong answer is confidently wrong: an empty pipeline
that looks like a losing one, or a declined bid still carrying value.
"""

from datetime import date

from app.grants.analytics import (
    STAGE_WEIGHTS,
    funder_concentration,
    income_split,
    return_rag,
    success_rate,
    weighted_value,
)

TODAY = date(2026, 8, 3)


def test_weighted_value_uses_stage_weight_while_undecided():
    assert weighted_value("pipeline", "case", 100_000, None) == 100_000 * STAGE_WEIGHTS["case"]
    assert weighted_value("submitted", "decision", 100_000, None) == 50_000


def test_weighted_value_uses_the_decision_once_decided():
    # An award is worth what was offered, not what was asked.
    assert weighted_value("awarded", "deliver", 100_000, 60_000) == 60_000
    # A declined bid is worth nothing, whatever stage it reached.
    assert weighted_value("declined", "decision", 100_000, None) == 0.0
    assert weighted_value("withdrawn", "apply", 100_000, None) == 0.0


def test_weighted_value_falls_back_to_the_ask_when_an_award_has_no_amount():
    assert weighted_value("awarded", "deliver", 40_000, None) == 40_000


def test_weighted_value_handles_missing_amounts():
    assert weighted_value("pipeline", "case", None, None) == 0.0
    assert weighted_value("pipeline", "unknown_stage", 100_000, None) == 0.0


def test_return_rag_reds_only_once_the_funder_date_has_passed():
    assert return_rag(date(2026, 8, 2), "open", TODAY) == "red"
    assert return_rag(date(2026, 8, 3), "open", TODAY) == "amber"
    assert return_rag(date(2026, 8, 20), "upcoming", TODAY) == "amber"
    assert return_rag(date(2026, 12, 1), "upcoming", TODAY) == "green"


def test_return_rag_is_green_once_submitted_even_if_late():
    assert return_rag(date(2026, 1, 1), "submitted", TODAY) == "green"
    assert return_rag(date(2026, 1, 1), "accepted", TODAY) == "green"
    assert return_rag(None, "open", TODAY) == "green"


def test_success_rate_counts_decided_applications_only():
    apps = [
        {"status": "awarded", "amount_requested": 10_000, "amount_awarded": 8_000},
        {"status": "declined", "amount_requested": 20_000},
        {"status": "pipeline", "amount_requested": 50_000},  # live: must not count as a loss
        {"status": "submitted", "amount_requested": 30_000},
    ]
    result = success_rate(apps)
    assert result.decided == 2
    assert result.awarded == 1
    assert result.rate == 0.5
    assert result.amount_requested == 30_000
    assert result.amount_awarded == 8_000


def test_success_rate_is_none_not_zero_when_nothing_is_decided():
    """ "No data" and "never won" must not render the same."""
    result = success_rate([{"status": "pipeline", "amount_requested": 1_000}])
    assert result.decided == 0
    assert result.rate is None


def test_funder_concentration_reports_the_largest_share_of_secured_income():
    apps = [
        {"status": "awarded", "amount_awarded": 75_000, "funder_name": "Big Trust"},
        {"status": "awarded", "amount_awarded": 15_000, "funder_name": "Small Trust"},
        {"status": "complete", "amount_awarded": 10_000, "funder_name": "Small Trust"},
        {"status": "declined", "amount_awarded": 90_000, "funder_name": "Never Trust"},
    ]
    result = funder_concentration(apps)
    assert result.total == 100_000
    assert result.top_funder == "Big Trust"
    assert result.top_share == 0.75
    assert result.funder_count == 2


def test_funder_concentration_is_empty_without_secured_income():
    result = funder_concentration([{"status": "pipeline", "amount_requested": 10_000}])
    assert result.total == 0.0
    assert result.top_funder is None
    assert result.top_share is None


def test_funder_concentration_groups_unattributed_awards():
    result = funder_concentration([{"status": "awarded", "amount_awarded": 5_000}])
    assert result.top_funder == "Unattributed"


def test_income_split_separates_restricted_from_unrestricted():
    apps = [
        {"status": "awarded", "amount_awarded": 30_000, "restricted": True},
        {"status": "awarded", "amount_awarded": 10_000, "restricted": False},
        {"status": "pipeline", "amount_awarded": 99_000, "restricted": True},
    ]
    split = income_split(apps)
    assert split.restricted == 30_000
    assert split.unrestricted == 10_000
    assert split.restricted_share == 0.75


def test_income_split_share_is_none_when_nothing_is_secured():
    assert income_split([]).restricted_share is None
