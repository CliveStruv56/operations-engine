"""Grantwork's context pack and its gatherer.

Facts about an application come from here and only from here — the grounding
contract in `worker/drafting/prompts.py` depends on it, and the figures in a
monitoring return render as real tables from these records rather than from
anything the model wrote.

Deliberately dependency-light (asyncpg + pydantic only), for the same reason
as Groundwork's (ASSUMPTIONS #13): the **API** test suite imports this module
and runs the gather against its migrated database, which worker CI has no
Postgres for.
"""

import json
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

import asyncpg
from pydantic import BaseModel, Field

from worker.drafting.pack import DraftPackBase

DRAFT_KINDS = (
    "case_for_support",
    "funding_application",
    "monitoring_report",
    "impact_evaluation",
    "impact_card",
)

DOC_TITLES = {
    "case_for_support": "Case for support",
    "funding_application": "Funding application",
    "monitoring_report": "Monitoring return",
    "impact_evaluation": "End-of-grant evaluation",
}

#: Statuses that mean the funder has committed money.
LIVE_STATUSES = ("awarded", "complete")


def _f(value: Any) -> float | None:
    """asyncpg returns numeric as Decimal; the pack is JSON-serialised into
    prompts, so money lands as float at the edge rather than in every caller."""
    return float(value) if isinstance(value, Decimal | int | float) else None


class ApplicationFacts(BaseModel):
    id: UUID
    title: str
    reference: str | None = None
    application_type: str
    programme_key: str | None = None
    stage_current: str
    status: str
    amount_requested: float | None = None
    amount_awarded: float | None = None
    restricted: bool = True
    deadline: date | None = None
    submitted_at: date | None = None
    decision_at: date | None = None
    start_date: date | None = None
    end_date: date | None = None
    reporting_note: str | None = None
    notes: str | None = None
    funder_name: str | None = None
    funder_kind: str | None = None
    project_name: str | None = None


class StageFacts(BaseModel):
    stage_key: str
    label: str
    position: int
    status: str
    planned_start: date | None = None
    planned_end: date | None = None
    actual_start: date | None = None
    actual_end: date | None = None
    gate: list[dict[str, Any]] = Field(default_factory=list)
    gate_signed_off_at: datetime | None = None
    gate_exceptions: str | None = None


class TaskFacts(BaseModel):
    stage_key: str
    title: str
    details: str | None = None
    owner_name: str | None = None
    due_date: date | None = None
    is_milestone: bool = False
    tags: list[str] = Field(default_factory=list)
    status: str


class ConditionFacts(BaseModel):
    number: str
    description: str
    pre_drawdown: bool = False
    status: str
    due_date: date | None = None
    submitted_at: date | None = None
    discharged_at: date | None = None


class PeriodFacts(BaseModel):
    id: UUID
    label: str
    period_start: date
    period_end: date
    due_date: date | None = None
    status: str
    submitted_at: date | None = None
    accepted_at: date | None = None
    overdue: bool = False


class MeasureFacts(BaseModel):
    id: UUID
    name: str
    definition: str | None = None
    unit: str
    baseline: float | None = None
    target: float | None = None
    position: int = 0


class OutcomeFacts(BaseModel):
    measure_id: UUID
    reporting_period_id: UUID
    value: float | None = None
    narrative: str | None = None
    evidence_notes: str | None = None


class CatalogueFacts(BaseModel):
    """The funder-catalogue row this application was parameterised from.

    `status` and `stale` are what drive the first-page warning: a row nobody
    has verified must never produce a confident-looking bid (ASSUMPTIONS #24).
    """

    key: str
    name: str
    funder: str
    kind: str
    amount_note: str | None = None
    match_note: str | None = None
    eligibility: str
    status: str
    deadlines: str | None = None
    docs_required: list[str] = Field(default_factory=list)
    reporting_note: str | None = None
    last_verified: date
    next_review: date
    stale: bool = False


class GrantPack(DraftPackBase):
    kind: str = Field(
        pattern="^(case_for_support|funding_application|monitoring_report"
        "|impact_evaluation|impact_card)$"
    )
    application: ApplicationFacts
    stages: list[StageFacts] = Field(default_factory=list)
    tasks: list[TaskFacts] = Field(default_factory=list)
    conditions: list[ConditionFacts] = Field(default_factory=list)
    periods: list[PeriodFacts] = Field(default_factory=list)
    measures: list[MeasureFacts] = Field(default_factory=list)
    outcomes: list[OutcomeFacts] = Field(default_factory=list)
    catalogue: CatalogueFacts | None = None
    #: Which reporting period a monitoring return covers.
    target_period_id: UUID | None = None

    # -- derived views the tables and prompts use ----------------------------

    def target_period(self) -> PeriodFacts | None:
        for period in self.periods:
            if period.id == self.target_period_id:
                return period
        return None

    def outcomes_for(self, period_id: UUID) -> dict[UUID, OutcomeFacts]:
        return {o.measure_id: o for o in self.outcomes if o.reporting_period_id == period_id}

    def measure_progress(self, period_id: UUID | None) -> list[dict[str, Any]]:
        """Measures joined to the period's recorded values — the rows the
        impact table renders. Never model output."""
        recorded = self.outcomes_for(period_id) if period_id else {}
        rows = []
        for measure in self.measures:
            outcome = recorded.get(measure.id)
            value = outcome.value if outcome else None
            rows.append(
                {
                    "name": measure.name,
                    "unit": measure.unit,
                    "baseline": measure.baseline,
                    "target": measure.target,
                    "value": value,
                    "narrative": outcome.narrative if outcome else None,
                    "share": (
                        value / measure.target
                        if value is not None and measure.target not in (None, 0)
                        else None
                    ),
                }
            )
        return rows

    def cumulative_progress(self) -> list[dict[str, Any]]:
        """Latest recorded value per measure across every period, for the
        end-of-grant evaluation."""
        order = {p.id: p.period_start for p in self.periods}
        latest: dict[UUID, OutcomeFacts] = {}
        for outcome in self.outcomes:
            if outcome.value is None:
                continue
            current = latest.get(outcome.measure_id)
            if current is None or order.get(outcome.reporting_period_id, date.min) > order.get(
                current.reporting_period_id, date.min
            ):
                latest[outcome.measure_id] = outcome
        rows = []
        for measure in self.measures:
            outcome = latest.get(measure.id)
            value = outcome.value if outcome else None
            rows.append(
                {
                    "name": measure.name,
                    "unit": measure.unit,
                    "baseline": measure.baseline,
                    "target": measure.target,
                    "value": value,
                    "share": (
                        value / measure.target
                        if value is not None and measure.target not in (None, 0)
                        else None
                    ),
                }
            )
        return rows

    # -- drafting hooks (worker/drafting/pack.py) ----------------------------

    def doc_title(self) -> str:
        title = DOC_TITLES.get(self.kind, self.kind)
        period = self.target_period()
        if self.kind == "monitoring_report" and period is not None:
            title = f"{title} — {period.label}"
        if self.kind == "funding_application" and self.application.funder_name:
            title = f"{title} — {self.application.funder_name}"
        return title

    def subject_lines(self) -> list[str]:
        lines = [self.application.title]
        if self.application.funder_name:
            lines.append(f"Funder: {self.application.funder_name}")
        if self.application.reference:
            lines.append(f"Funder reference: {self.application.reference}")
        if self.application.project_name:
            lines.append(f"Linked project: {self.application.project_name}")
        return lines

    def prompt_notes(self) -> list[str]:
        notes = []
        period = self.target_period()
        if period is not None:
            notes.append(
                f"Reporting period: {period.label} "
                f"({period.period_start.isoformat()} to {period.period_end.isoformat()})."
            )
        notes.extend(super().prompt_notes())
        if self.catalogue is not None:
            notes.append(
                f'This application targets "{self.catalogue.name}" '
                f"({self.catalogue.funder}). Write to that funder's eligibility and "
                "documentation notes as they appear in the data — do not assert any "
                "requirement that is not there."
            )
        if self.kind == "monitoring_report":
            # Figures discipline only — which sections carry a rendered table
            # is said per section (`drafting/prompts.section_prompt`). Saying
            # it here reached "Financial position", which has no table, and the
            # draft duly referred a funder to one (DRAFT-002).
            notes.append(
                "Comment on what the recorded figures show; never restate or estimate "
                "them, and mark a missing figure [TO CONFIRM: …] rather than inferring it."
            )
        return notes

    def record_counts(self) -> dict[str, int]:
        return {
            "stages": len(self.stages),
            "tasks": len(self.tasks),
            "award conditions": len(self.conditions),
            "reporting periods": len(self.periods),
            "impact measures": len(self.measures),
            "recorded outcomes": len(self.outcomes),
            "vault excerpts": len(self.excerpts),
        }

    def warning_block(self) -> str | None:
        """A bid built on an unchecked catalogue row must say so on page one.

        Seeded rows ship `status='unverified'` and stale (ASSUMPTIONS #24), so
        this fires by default until an operator has actually verified the
        funder's criteria — which is the whole point of that convention.
        """
        if self.kind != "funding_application" or self.catalogue is None:
            return None
        if self.catalogue.status == "open" and not self.catalogue.stale:
            return None
        return (
            f"Funder catalogue entry “{self.catalogue.name}” was “{self.catalogue.status}” "
            f"when last checked {self.catalogue.last_verified.isoformat()}"
            f"{' and is past its review date' if self.catalogue.stale else ''} — "
            "confirm the current criteria and deadline with the funder before submitting."
        )

    def source_notes(self) -> list[str]:
        if self.catalogue is None:
            return []
        note = (
            f"Funder catalogue entry “{self.catalogue.name}” ({self.catalogue.funder}), "
            f"facts last checked {self.catalogue.last_verified.isoformat()}."
        )
        if self.catalogue.stale:
            note += " Warning: past its review date — confirm before relying on it."
        return [note]


def _loads(value: Any) -> Any:
    # asyncpg returns jsonb as str (no codec registered) — decode at the edge.
    return json.loads(value) if isinstance(value, str) else value


async def gather(
    conn: asyncpg.Connection,
    application_id: UUID,
    kind: str,
    params: dict[str, Any],
    today: date,
) -> GrantPack:
    """Select an application's whole spine under the caller's tenant
    transaction (RLS applies). Vault excerpts are attached afterwards by the
    engine — retrieval needs network embeds, which never happen inside a
    tenant transaction."""
    if kind not in DRAFT_KINDS:
        raise ValueError(f"Unknown draft kind: {kind}")

    row = await conn.fetchrow(
        """
        select a.*, f.name as funder_name, f.kind as funder_kind, p.name as project_name
        from grant_applications a
        left join grant_funders f on f.id = a.funder_id
        left join projects p on p.id = a.project_id
        where a.id = $1
        """,
        application_id,
    )
    if row is None:
        raise ValueError("Application not found")
    application = ApplicationFacts(
        **{
            **dict(row),
            "amount_requested": _f(row["amount_requested"]),
            "amount_awarded": _f(row["amount_awarded"]),
        }
    )

    stage_rows = await conn.fetch(
        "select * from grant_stages where application_id = $1 order by position", application_id
    )
    stages = [StageFacts(**{**dict(r), "gate": _loads(r["gate"])}) for r in stage_rows]

    task_rows = await conn.fetch(
        """
        select t.* from grant_tasks t
        join grant_stages s on s.application_id = t.application_id
                           and s.stage_key = t.stage_key
        where t.application_id = $1
        order by s.position, t.position
        """,
        application_id,
    )
    tasks = [TaskFacts(**{**dict(r), "tags": list(r["tags"] or [])}) for r in task_rows]

    condition_rows = await conn.fetch(
        "select * from grant_conditions where application_id = $1"
        " order by pre_drawdown desc, number",
        application_id,
    )
    conditions = [ConditionFacts(**dict(r)) for r in condition_rows]

    period_rows = await conn.fetch(
        "select * from grant_reporting_periods where application_id = $1 order by period_start",
        application_id,
    )
    periods = [
        PeriodFacts(
            **dict(r),
            overdue=(
                r["status"] in ("upcoming", "open", "drafting")
                and r["due_date"] is not None
                and r["due_date"] < today
            ),
        )
        for r in period_rows
    ]

    measure_rows = await conn.fetch(
        "select * from grant_impact_measures where application_id = $1 order by position, name",
        application_id,
    )
    measures = [
        MeasureFacts(**{**dict(r), "baseline": _f(r["baseline"]), "target": _f(r["target"])})
        for r in measure_rows
    ]

    outcome_rows = await conn.fetch(
        """
        select o.* from grant_outcomes o
        join grant_impact_measures m on m.id = o.measure_id
        where m.application_id = $1
        """,
        application_id,
    )
    outcomes = [OutcomeFacts(**{**dict(r), "value": _f(r["value"])}) for r in outcome_rows]

    catalogue = None
    if application.programme_key:
        cat = await conn.fetchrow(
            "select * from grant_ref_funders where key = $1", application.programme_key
        )
        if cat is not None:
            catalogue = CatalogueFacts(
                **{**dict(cat), "docs_required": list(cat["docs_required"] or [])},
                stale=cat["next_review"] < today,
            )

    target_period_id: UUID | None = None
    if kind == "monitoring_report":
        raw = params.get("reporting_period_id")
        target_period_id = UUID(str(raw)) if raw else None
        if target_period_id not in {p.id for p in periods}:
            raise ValueError("Reporting period not found on this application")

    return GrantPack(
        kind=kind,
        generated_on=today,
        application=application,
        stages=stages,
        tasks=tasks,
        conditions=conditions,
        periods=periods,
        measures=measures,
        outcomes=outcomes,
        catalogue=catalogue,
        target_period_id=target_period_id,
        instructions=(str(params["instructions"])[:2000] if params.get("instructions") else None),
    )
