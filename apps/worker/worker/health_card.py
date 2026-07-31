"""One-page health card (PRD §5.4): a fixed HTML template rendered by
WeasyPrint — no LLM anywhere. Plain-English blocks: project + client, stage
bar, three traffic lights with one-line explanations, money summary, next 3
milestones, top 3 risks, decisions needed. Tenant brand colour on the
header rule.

WeasyPrint imports lazily (it needs system pango/cairo, same pattern as the
Docling import) so the module — and the HTML-only tests — work without it.
"""

import asyncio
import contextlib
import html
from dataclasses import dataclass
from datetime import date
from uuid import UUID

import asyncpg

from worker.db import tenant_tx
from worker.drafts.context import ContextPack, gather
from worker.storage import upload_bytes

PDF_MIME = "application/pdf"
DEFAULT_ACCENT = "#1f6d53"  # core ledger accent; tenants.brand overrides

STAGE_ORDER = ["group", "site", "plan", "build", "live"]
STAGE_LABELS = {"group": "Group", "site": "Site", "plan": "Plan", "build": "Build", "live": "Live"}


# -- derived RAG --------------------------------------------------------------
# Mirror of the API's app/groundwork/rag.py (not importable from the worker,
# same as retrieval) — keep the thresholds in step.


@dataclass(frozen=True)
class Rag:
    programme: str
    cost: str
    risk: str


def compute_rag(
    worst_milestone_overdue_days: int,
    budget_total: float,
    forecast_total: float,
    max_open_risk_score: int,
) -> Rag:
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

    return Rag(programme=programme, cost=cost, risk=risk)


def derive_rag(pack: ContextPack, today: date) -> tuple[Rag, dict[str, str]]:
    """RAG plus the one-line plain-English explanation for each light."""
    overdue = [
        (today - t.due_date).days
        for t in pack.tasks
        if t.is_milestone and t.due_date and t.status in ("todo", "doing") and t.due_date < today
    ]
    worst = max(overdue, default=0)
    top_risk = max((r.score for r in pack.risks if r.status == "open"), default=0)
    rag = compute_rag(worst, pack.budget_totals.budget, pack.budget_totals.forecast, top_risk)

    notes = {
        "programme": (
            "Milestones are on track."
            if worst == 0
            else f"The worst overdue milestone is {worst} days late."
        ),
        "cost": (
            "Forecast is within budget."
            if rag.cost == "green"
            else f"Forecast is £{pack.budget_totals.variance:,.0f} over budget."
        ),
        "risk": (
            "No high-scoring open risks."
            if top_risk < 9
            else f"The top open risk scores {top_risk} out of 25."
        ),
    }
    return rag, notes


def decisions_needed(pack: ContextPack, today: date) -> list[str]:
    items: list[str] = []
    for t in pack.tasks:
        if t.is_milestone and t.due_date and t.status in ("todo", "doing") and t.due_date < today:
            items.append(f"“{t.title}” is overdue ({t.due_date.strftime('%d %b %Y')}).")
    pre = [c for c in pack.conditions if c.pre_commencement and c.status == "outstanding"]
    if pre:
        items.append(
            f"{len(pre)} pre-commencement planning condition(s) still outstanding — "
            "work cannot start until they are discharged."
        )
    gap = pack.budget_totals.forecast - sum(s.amount_secured or 0 for s in pack.funding)
    if gap > 0:
        items.append(f"£{gap:,.0f} of the scheme cost is not yet covered by secured funding.")
    return items[:4] or ["No board decisions outstanding."]


# -- template -----------------------------------------------------------------

_CSS = """
@page { size: A4; margin: 14mm 16mm; }
body { font-family: Helvetica, Arial, sans-serif; font-size: 10pt; color: #1a1a1a; margin: 0; }
h1 { font-size: 17pt; margin: 0 0 1mm; }
.sub { color: #555; margin: 0 0 4mm; }
.rule { height: 2.5mm; background: ACCENT; margin-bottom: 5mm; }
h2 { font-size: 10.5pt; text-transform: uppercase; letter-spacing: 0.06em;
     margin: 5mm 0 2mm; color: #444; }
.stages { display: flex; gap: 2mm; }
.stage { flex: 1; text-align: center; padding: 2mm 0; border: 0.4mm solid #ccc;
         border-radius: 1mm; color: #888; }
.stage.current { background: ACCENT; border-color: ACCENT; color: white; font-weight: bold; }
.stage.passed { border-color: ACCENT; color: ACCENT; }
.lights td { padding: 1mm 2mm 1mm 0; vertical-align: middle; }
.dot { display: inline-block; width: 4mm; height: 4mm; border-radius: 50%; }
.dot.green { background: #2e7d32; } .dot.amber { background: #ef6c00; }
.dot.red { background: #c62828; }
.money { display: flex; gap: 6mm; }
.money div { flex: 1; border: 0.4mm solid #ddd; border-radius: 1mm; padding: 2.5mm; }
.money .big { font-size: 13pt; font-weight: bold; }
ul { margin: 0; padding-left: 5mm; }
li { margin-bottom: 1mm; }
.muted { color: #666; }
"""

_PAGE = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>{css}</style></head><body>
<h1>{project}</h1>
<p class="sub">{client} · Project health card · {date}</p>
<div class="rule"></div>

<h2>Where the project is</h2>
<div class="stages">{stages}</div>

<h2>Is it on track?</h2>
<table class="lights">{lights}</table>

<h2>Money</h2>
<div class="money">
  <div><div class="muted">Total scheme cost</div><div class="big">£{cost}</div></div>
  <div><div class="muted">Funding secured</div><div class="big">£{secured}</div></div>
  <div><div class="muted">Gap to close</div><div class="big">£{gap}</div></div>
</div>

<h2>Next milestones</h2>
<ul>{milestones}</ul>

<h2>Top risks in plain words</h2>
<ul>{risks}</ul>

<h2>Decisions needed from the board</h2>
<ul>{decisions}</ul>
</body></html>
"""


def _esc(value: object) -> str:
    return html.escape(str(value))


def build_html(pack: ContextPack, brand_accent: str, today: date) -> str:
    rag, notes = derive_rag(pack, today)
    current_pos = STAGE_ORDER.index(pack.project.stage_current)

    def _stage_class(i: int) -> str:
        return "current" if i == current_pos else "passed" if i < current_pos else ""

    stages = "".join(
        f'<div class="stage {_stage_class(i)}">{STAGE_LABELS[key]}</div>'
        for i, key in enumerate(STAGE_ORDER)
    )

    lights = "".join(
        f'<tr><td><span class="dot {colour}"></span></td>'
        f"<td><strong>{label}</strong></td><td>{_esc(note)}</td></tr>"
        for label, colour, note in [
            ("Programme", rag.programme, notes["programme"]),
            ("Cost", rag.cost, notes["cost"]),
            ("Risk", rag.risk, notes["risk"]),
        ]
    )

    secured = sum(s.amount_secured or 0 for s in pack.funding)
    gap = max(pack.budget_totals.forecast - secured, 0)

    upcoming = sorted(
        (t for t in pack.tasks if t.is_milestone and t.due_date and t.status in ("todo", "doing")),
        key=lambda t: t.due_date,
    )[:3]
    milestones = (
        "".join(
            f"<li>{_esc(t.title)} "
            f"<span class='muted'>— {t.due_date.strftime('%d %b %Y')}</span></li>"
            for t in upcoming
        )
        or "<li class='muted'>No dated milestones yet.</li>"
    )

    risks = (
        "".join(f"<li>{_esc(r.description)}</li>" for r in pack.risks[:3] if r.status == "open")
        or "<li class='muted'>No open risks.</li>"
    )

    decisions = "".join(f"<li>{_esc(d)}</li>" for d in decisions_needed(pack, today))

    return _PAGE.format(
        css=_CSS.replace("ACCENT", brand_accent),
        project=_esc(pack.project.name),
        client=_esc(pack.project.client_org or "Community-led housing project"),
        date=today.strftime("%d %B %Y"),
        stages=stages,
        lights=lights,
        cost=f"{pack.budget_totals.forecast:,.0f}",
        secured=f"{secured:,.0f}",
        gap=f"{gap:,.0f}",
        milestones=milestones,
        risks=risks,
        decisions=decisions,
    )


def render_pdf(html_text: str) -> bytes:
    from weasyprint import HTML  # lazy: needs system pango/cairo

    return HTML(string=html_text).write_pdf()


# -- arq job ------------------------------------------------------------------


async def _mark_failed(pool: asyncpg.Pool, tenant_id: str, job_id: str, error: str) -> None:
    async with tenant_tx(pool, tenant_id) as conn:
        await conn.execute(
            "update proj_draft_jobs set status = 'failed', error = $2, updated_at = now()"
            " where id = $1",
            UUID(job_id),
            error[:500],
        )


async def generate_health_card(
    ctx: dict, tenant_id: str, project_id: str, job_id: str, user_id: str
) -> str:
    pool: asyncpg.Pool = ctx["pool"]
    loop = asyncio.get_running_loop()
    today = date.today()

    async with tenant_tx(pool, tenant_id) as conn:
        job = await conn.fetchrow("select 1 from proj_draft_jobs where id = $1", UUID(job_id))
        if job is None:
            return "gone"
        await conn.execute(
            "update proj_draft_jobs set status = 'running', updated_at = now() where id = $1",
            UUID(job_id),
        )

    try:
        async with tenant_tx(pool, tenant_id) as conn:
            pack = await gather(conn, UUID(project_id), "health_card", {}, today)
            brand = await conn.fetchval(
                "select brand->>'accent' from tenants where id = $1", tenant_id
            )

        html_text = build_html(pack, brand or DEFAULT_ACCENT, today)
        pdf = await loop.run_in_executor(None, render_pdf, html_text)

        file_key = f"{tenant_id}/projects/{project_id}/drafts/{job_id}.pdf"
        await loop.run_in_executor(None, upload_bytes, file_key, pdf, PDF_MIME)

        async with tenant_tx(pool, tenant_id) as conn:
            await conn.execute(
                """
                update proj_draft_jobs
                set status = 'succeeded', file_key = $2, updated_at = now()
                where id = $1
                """,
                UUID(job_id),
                file_key,
            )
            await conn.execute(
                """
                insert into audit_log (tenant_id, user_id, action, target_type, target_id, meta)
                values ($1, $2, 'projects.health_card', 'proj_draft_job', $3, '{}')
                """,
                UUID(tenant_id),
                UUID(user_id),
                job_id,
            )
        return "succeeded"
    except BaseException as exc:
        reason = (
            "Health card generation was interrupted — try again"
            if isinstance(exc, asyncio.CancelledError)
            else f"Health card generation failed ({type(exc).__name__}: {str(exc)[:160]})"
        )
        with contextlib.suppress(BaseException):
            await _mark_failed(pool, tenant_id, job_id, reason)
        raise
