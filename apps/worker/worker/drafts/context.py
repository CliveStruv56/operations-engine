"""Context-pack gatherer (PRD §5 step 1): SQL selects into a typed pack that
every drafting prompt and every assembled table draws from. Facts about the
project come from here and only here.

Deliberately dependency-light (asyncpg + pydantic only): the API test suite
imports this module to run the gather against its migrated database, which
the worker's own CI does not have.
"""

import json
from datetime import date, datetime
from typing import Any
from uuid import UUID

import asyncpg
from pydantic import BaseModel, Field

from worker.claims.facts import claim_source_notes, claims_warning, load_claims
from worker.drafting.pack import DraftPackBase, VaultExcerpt
from worker.drafting.questions import load_question_set, source_note_for, warning_for

__all__ = ["VaultExcerpt"]  # re-exported: this was its original home

DRAFT_KINDS = (
    "monthly_report",
    "feasibility_study",
    "funding_bid",
    "health_card",
    "application_form",
)

DOC_TITLES = {
    "monthly_report": "Monthly client report",
    "feasibility_study": "Feasibility study",
    "funding_bid": "Funding application",
    "application_form": "Application form",
}


class ProjectFacts(BaseModel):
    id: UUID
    name: str
    client_org: str | None = None
    project_type: str
    delivery_route: str | None = None
    status: str
    stage_current: str
    site_address: str | None = None
    homes_planned: int | None = None
    start_date: date | None = None
    target_completion: date | None = None
    applicability: dict[str, Any] = Field(default_factory=dict)
    contract_facts: dict[str, Any] = Field(default_factory=dict)


class StageFacts(BaseModel):
    stage_key: str
    label: str
    riba_ref: str | None = None
    position: int
    status: str
    planned_start: date | None = None
    planned_end: date | None = None
    forecast_start: date | None = None
    forecast_end: date | None = None
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
    completed_at: datetime | None = None


class BudgetLine(BaseModel):
    category: str
    label: str
    budget: float
    forecast: float
    actual: float
    note: str | None = None


class BudgetTotals(BaseModel):
    budget: float = 0.0
    forecast: float = 0.0
    actual: float = 0.0
    variance: float = 0.0  # forecast - budget


class FundingSource(BaseModel):
    id: UUID
    programme_key: str | None = None
    name: str
    funder: str | None = None
    kind: str
    amount_sought: float | None = None
    amount_secured: float | None = None
    status: str
    conditions: str | None = None
    drawdown_schedule: list[dict[str, Any]] = Field(default_factory=list)
    notes: str | None = None


class ProgrammeFacts(BaseModel):
    key: str
    name: str
    funder: str
    kind: str
    amount_note: str | None = None
    match_note: str | None = None
    eligibility: str
    status: str
    docs_required: list[str] = Field(default_factory=list)
    last_verified: date
    next_review: date
    stale: bool = False


class RiskFacts(BaseModel):
    category: str
    description: str
    likelihood: int
    impact: int
    score: int
    owner_name: str | None = None
    mitigation: str | None = None
    status: str


class ConditionFacts(BaseModel):
    application_ref: str | None = None
    number: str
    description: str
    pre_commencement: bool = False
    status: str
    submitted_at: date | None = None
    discharged_at: date | None = None


class StakeholderFacts(BaseModel):
    name: str
    org: str | None = None
    role: str
    last_contact: date | None = None


class ContextPack(DraftPackBase):
    kind: str = Field(
        pattern="^(monthly_report|feasibility_study|funding_bid|health_card|application_form)$"
    )
    project: ProjectFacts
    stages: list[StageFacts]
    tasks: list[TaskFacts]
    budget_lines: list[BudgetLine]
    budget_totals: BudgetTotals
    funding: list[FundingSource]
    programmes: list[ProgrammeFacts]
    target_funding_id: UUID | None = None
    risks: list[RiskFacts]
    conditions: list[ConditionFacts]
    stakeholders: list[StakeholderFacts]
    report_month: str | None = None  # 'YYYY-MM' for monthly reports

    def record_counts(self) -> dict[str, int]:
        return {
            "stages": len(self.stages),
            "tasks": len(self.tasks),
            "budget lines": len(self.budget_lines),
            "funding sources": len(self.funding),
            "risks": len(self.risks),
            "planning conditions": len(self.conditions),
            "stakeholders": len(self.stakeholders),
            "vault excerpts": len(self.excerpts),
        }

    def target_funding(self) -> FundingSource | None:
        for source in self.funding:
            if source.id == self.target_funding_id:
                return source
        return None

    def target_programme(self) -> ProgrammeFacts | None:
        source = self.target_funding()
        if source is None or source.programme_key is None:
            return None
        for programme in self.programmes:
            if programme.key == source.programme_key:
                return programme
        return None

    # -- drafting hooks (worker/drafting/pack.py) ----------------------------

    def doc_title(self) -> str:
        title = DOC_TITLES[self.kind]
        if self.kind == "monthly_report" and self.report_month:
            title = f"{title} — {self.report_month}"
        if self.kind == "funding_bid" and self.target_funding() is not None:
            title = f"{title} — {self.target_funding().name}"
        if self.kind == "application_form" and self.question_set is not None:
            title = f"{self.question_set.name} — {self.question_set.funder}"
        return title

    def subject_lines(self) -> list[str]:
        lines = [self.project.name]
        if self.project.client_org:
            lines.append(f"Prepared for {self.project.client_org}")
        if self.project.site_address:
            lines.append(self.project.site_address)
        return lines

    def prompt_notes(self) -> list[str]:
        notes = []
        if self.report_month:
            notes.append(f"Reporting period: {self.report_month}.")
        notes.extend(super().prompt_notes())
        if self.kind == "funding_bid" and self.target_funding() is not None:
            source = self.target_funding()
            notes.append(
                f'This bid targets the funding source "{source.name}" '
                f"(programme key: {source.programme_key or 'none'}). Tailor the "
                "section to that programme's eligibility and documentation notes "
                "in the data."
            )
        return notes

    def warning_block(self) -> str | None:
        # Two independent problems, both worth the first page: the form may be
        # out of date, and a fact the draft leans on may be. `assemble.py`
        # renders one bold paragraph, so they are joined rather than competing
        # for the slot.
        warnings = [self._form_or_programme_warning(), claims_warning(self.claims)]
        present = [w for w in warnings if w]
        return "\n".join(present) if present else None

    def _form_or_programme_warning(self) -> str | None:
        if self.kind == "application_form":
            return warning_for(self.question_set)
        programme = self.target_programme()
        if self.kind != "funding_bid" or programme is None or programme.status == "open":
            return None
        return (
            f"Programme status was “{programme.status}” when last verified "
            f"{programme.last_verified.isoformat()} — confirm before submitting."
        )

    def source_notes(self) -> list[str]:
        notes = source_note_for(self.question_set) + claim_source_notes(self.claims)
        for programme in self.programmes:
            note = (
                f"Funding programme “{programme.name}” ({programme.funder}), "
                f"catalogue facts last verified {programme.last_verified.isoformat()}."
            )
            if programme.stale:
                note += " Warning: past its review date — confirm before relying on it."
            notes.append(note)
        return notes


def _loads(value: Any) -> Any:
    # asyncpg returns jsonb as str (no codec registered) — decode at the edge.
    return json.loads(value) if isinstance(value, str) else value


async def gather(
    conn: asyncpg.Connection,
    project_id: UUID,
    kind: str,
    params: dict[str, Any],
    today: date,
) -> ContextPack:
    """Select the full module spine for one project under the caller's
    tenant transaction (RLS applies). Vault excerpts are attached by the
    caller afterwards — retrieval needs network embeds, which never happen
    inside a tenant transaction."""
    if kind not in DRAFT_KINDS:
        raise ValueError(f"Unknown draft kind: {kind}")

    row = await conn.fetchrow(
        """
        select pp.*, p.name
        from proj_projects pp join projects p on p.id = pp.id
        where pp.id = $1
        """,
        project_id,
    )
    if row is None:
        raise ValueError("Project not found")
    project = ProjectFacts(
        **{
            **dict(row),
            "applicability": _loads(row["applicability"]),
            "contract_facts": _loads(row["contract_facts"]),
        }
    )

    stage_rows = await conn.fetch(
        "select * from proj_stages where project_id = $1 order by position", project_id
    )
    stages = [StageFacts(**{**dict(r), "gate": _loads(r["gate"])}) for r in stage_rows]

    task_rows = await conn.fetch(
        """
        select t.* from proj_tasks t
        join proj_stages s on s.project_id = t.project_id and s.stage_key = t.stage_key
        where t.project_id = $1
        order by s.position, t.position
        """,
        project_id,
    )
    tasks = [TaskFacts(**{**dict(r), "tags": list(r["tags"] or [])}) for r in task_rows]

    budget_rows = await conn.fetch(
        "select * from proj_budget_lines where project_id = $1 order by position, category",
        project_id,
    )
    budget_lines = [BudgetLine(**dict(r)) for r in budget_rows]
    totals = BudgetTotals(
        budget=sum(line.budget for line in budget_lines),
        forecast=sum(line.forecast for line in budget_lines),
        actual=sum(line.actual for line in budget_lines),
        variance=sum(line.forecast - line.budget for line in budget_lines),
    )

    funding_rows = await conn.fetch(
        "select * from proj_funding_sources where project_id = $1 order by updated_at",
        project_id,
    )
    funding = [
        FundingSource(**{**dict(r), "drawdown_schedule": _loads(r["drawdown_schedule"])})
        for r in funding_rows
    ]

    programme_keys = sorted({s.programme_key for s in funding if s.programme_key})
    programme_rows = await conn.fetch(
        "select * from proj_ref_programmes where key = any($1)", programme_keys
    )
    programmes = [
        ProgrammeFacts(
            **{**dict(r), "docs_required": list(r["docs_required"] or [])},
            stale=r["next_review"] < today,
        )
        for r in programme_rows
    ]

    risk_rows = await conn.fetch(
        """
        select *, likelihood * impact as score from proj_risks
        where project_id = $1 and status <> 'closed'
        order by likelihood * impact desc, created_at
        """,
        project_id,
    )
    risks = [RiskFacts(**dict(r)) for r in risk_rows]

    condition_rows = await conn.fetch(
        "select * from proj_conditions where project_id = $1 order by number", project_id
    )
    conditions = [ConditionFacts(**dict(r)) for r in condition_rows]

    stakeholder_rows = await conn.fetch(
        "select * from proj_stakeholders where project_id = $1 order by name", project_id
    )
    stakeholders = [StakeholderFacts(**dict(r)) for r in stakeholder_rows]

    target_funding_id: UUID | None = None
    if kind == "funding_bid":
        raw = params.get("funding_source_id")
        target_funding_id = UUID(str(raw)) if raw else None
        if target_funding_id not in {s.id for s in funding}:
            raise ValueError("Funding source not found on this project")

    question_set = None
    if kind == "application_form":
        key = str(params.get("question_set_key") or "")
        question_set = await load_question_set(conn, key, today, _loads) if key else None
        if question_set is None:
            raise ValueError("Question set not found")

    claims, claim_excerpts = await load_claims(conn, today)

    return ContextPack(
        kind=kind,
        generated_on=today,
        question_set=question_set,
        claims=claims,
        claim_excerpts=claim_excerpts,
        project=project,
        stages=stages,
        tasks=tasks,
        budget_lines=budget_lines,
        budget_totals=totals,
        funding=funding,
        programmes=programmes,
        target_funding_id=target_funding_id,
        risks=risks,
        conditions=conditions,
        stakeholders=stakeholders,
        instructions=(str(params["instructions"])[:2000] if params.get("instructions") else None),
        report_month=(str(params["month"]) if params.get("month") else None),
    )
