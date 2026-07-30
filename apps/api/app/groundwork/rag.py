"""Portfolio RAG health — derived, never stored (PRD §1).

Pure function of the project's current records so the portfolio can never
show a stale traffic light.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class RagResult:
    programme: str
    cost: str
    risk: str


def compute_rag(
    worst_milestone_overdue_days: int,
    budget_total: float,
    forecast_total: float,
    max_open_risk_score: int,
) -> RagResult:
    if worst_milestone_overdue_days > 30:
        programme = "red"
    elif worst_milestone_overdue_days > 0:
        programme = "amber"
    else:
        programme = "green"

    if budget_total > 0 and forecast_total > budget_total * 1.10:
        cost = "red"
    elif budget_total > 0 and forecast_total > budget_total:
        cost = "amber"
    else:
        cost = "green"

    if max_open_risk_score >= 16:
        risk = "red"
    elif max_open_risk_score >= 9:
        risk = "amber"
    else:
        risk = "green"

    return RagResult(programme=programme, cost=cost, risk=risk)
