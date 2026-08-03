"""Grantwork derived figures (PRD §1.2) — pure functions, never stored.

Same rule as Groundwork's RAG (`app/groundwork/rag.py`): everything here is a
function of the module's current rows, so a portfolio can never show a stale
number. Nothing in this file touches the database, which is what makes it
unit-testable without one.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date

#: Probability the pipeline assigns to an application at each stage. These are
#: planning weights for "what is this pipeline worth", not a prediction: an
#: unsubmitted bid is worth a fraction of its ask, a decided one is worth what
#: it actually won. Deliberately coarse — a charity's own history is too thin
#: to fit anything finer, and a false precision here would be read as insight.
STAGE_WEIGHTS: dict[str, float] = {
    "case": 0.05,
    "prospect": 0.10,
    "apply": 0.25,
    "decision": 0.50,
    "deliver": 1.00,
    "monitor": 1.00,
    "evaluate": 1.00,
}

#: Days before a monitoring return is due that it turns amber.
RETURN_AMBER_DAYS = 30

DECIDED_STATUSES = ("awarded", "declined")
LIVE_STATUSES = ("awarded", "complete")


def weighted_value(
    status: str,
    stage_current: str,
    amount_requested: float | None,
    amount_awarded: float | None,
) -> float:
    """What this application is worth to the pipeline today.

    A decided application is worth its decision, not its weight: an award is
    worth what was actually offered and a declined bid is worth nothing. Only
    undecided applications get the stage weighting.
    """
    if status == "awarded":
        return float(amount_awarded or amount_requested or 0.0)
    if status in ("declined", "withdrawn"):
        return 0.0
    if status == "complete":
        return float(amount_awarded or 0.0)
    return float(amount_requested or 0.0) * STAGE_WEIGHTS.get(stage_current, 0.0)


def return_rag(due_date: date | None, status: str, today: date) -> str:
    """Traffic light for one reporting obligation.

    Red once the funder's date has passed with nothing submitted — being late
    to a funder is the failure mode this module exists to prevent.
    """
    if status in ("submitted", "accepted", "na"):
        return "green"
    if due_date is None:
        return "green"
    days_left = (due_date - today).days
    if days_left < 0:
        return "red"
    if days_left <= RETURN_AMBER_DAYS:
        return "amber"
    return "green"


@dataclass(frozen=True)
class SuccessRate:
    decided: int
    awarded: int
    rate: float | None
    amount_requested: float
    amount_awarded: float


def success_rate(applications: Iterable[dict]) -> SuccessRate:
    """Win rate over *decided* applications only.

    Counting live bids as losses would make every active fundraiser look like
    a failing one, and would move the number every time a bid is opened.
    `rate` is None rather than 0.0 when nothing has been decided — "no data"
    and "never won" must not render the same.
    """
    decided = [a for a in applications if a.get("status") in DECIDED_STATUSES]
    awarded = [a for a in decided if a.get("status") == "awarded"]
    return SuccessRate(
        decided=len(decided),
        awarded=len(awarded),
        rate=(len(awarded) / len(decided)) if decided else None,
        amount_requested=sum(float(a.get("amount_requested") or 0) for a in decided),
        amount_awarded=sum(float(a.get("amount_awarded") or 0) for a in awarded),
    )


@dataclass(frozen=True)
class ConcentrationRisk:
    total: float
    top_funder: str | None
    top_share: float | None
    funder_count: int


def funder_concentration(applications: Iterable[dict]) -> ConcentrationRisk:
    """Share of secured income coming from the single largest funder.

    The number a trustee board asks for: one funder walking away is the
    commonest way a small charity's finances fall over.
    """
    by_funder: dict[str, float] = {}
    for app in applications:
        if app.get("status") not in LIVE_STATUSES:
            continue
        amount = float(app.get("amount_awarded") or 0)
        if amount <= 0:
            continue
        name = app.get("funder_name") or "Unattributed"
        by_funder[name] = by_funder.get(name, 0.0) + amount
    total = sum(by_funder.values())
    if not by_funder or total <= 0:
        return ConcentrationRisk(total=0.0, top_funder=None, top_share=None, funder_count=0)
    top_funder, top_amount = max(by_funder.items(), key=lambda kv: kv[1])
    return ConcentrationRisk(
        total=total,
        top_funder=top_funder,
        top_share=top_amount / total,
        funder_count=len(by_funder),
    )


@dataclass(frozen=True)
class IncomeSplit:
    restricted: float
    unrestricted: float

    @property
    def restricted_share(self) -> float | None:
        total = self.restricted + self.unrestricted
        return (self.restricted / total) if total > 0 else None


def income_split(applications: Iterable[dict]) -> IncomeSplit:
    """Restricted vs unrestricted split of secured income."""
    restricted = unrestricted = 0.0
    for app in applications:
        if app.get("status") not in LIVE_STATUSES:
            continue
        amount = float(app.get("amount_awarded") or 0)
        if app.get("restricted", True):
            restricted += amount
        else:
            unrestricted += amount
    return IncomeSplit(restricted=restricted, unrestricted=unrestricted)
