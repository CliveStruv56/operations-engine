from app.litellm import estimate_cost_usd
from app.routing import select_route


def test_default_is_workhorse():
    assert select_route(None, 1_000) == "workhorse"
    assert select_route("chat", 1_000) == "workhorse"
    assert select_route("", 0) == "workhorse"


def test_analyse_and_report_route_to_drafter():
    assert select_route("analyse", 1_000) == "drafter"
    assert select_route("report", 1_000) == "drafter"


def test_financial_routes_to_reasoner():
    assert select_route("financial", 1_000) == "reasoner"


def test_slides_and_research_route_to_drafter():
    assert select_route("slides", 1_000) == "drafter"
    assert select_route("research", 1_000) == "drafter"


def test_large_context_routes_to_longdoc_regardless_of_kind():
    assert select_route(None, 100_001) == "longdoc"
    assert select_route("financial", 250_000) == "longdoc"


def test_boundary_stays_off_longdoc():
    assert select_route("financial", 100_000) == "reasoner"


def test_soft_cap_pins_to_workhorse():
    assert select_route("financial", 1_000, soft_cap_hit=True) == "workhorse"
    assert select_route("report", 1_000, soft_cap_hit=True) == "workhorse"
    # Too large for workhorse: longdoc still wins (it is also cheapest).
    assert select_route("financial", 200_000, soft_cap_hit=True) == "longdoc"


def test_cost_estimate_matches_price_table():
    # workhorse: $0.06/M in, $0.40/M out
    assert estimate_cost_usd("workhorse", 1_000_000, 1_000_000) == 0.46
    assert estimate_cost_usd("workhorse", 0, 0) == 0.0
    # unknown alias falls back to workhorse pricing rather than crashing
    assert estimate_cost_usd("mystery", 1_000_000, 0) == 0.06
