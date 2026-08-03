"""One-page funder-facing impact card: a fixed HTML template rendered by
WeasyPrint — no LLM anywhere, so every figure on it is a recorded row.

That is the point of the format. A funder reading this is reading the
charity's own data, not a model's summary of it, which is why the card is
safe to send outward when a draft never is.

Tenant `brand.accent` colours the header rule only — exports are the one
place a tenant colour is allowed (ASSUMPTIONS #17).

WeasyPrint imports lazily (it needs system pango/cairo, same pattern as the
Docling import) so this module — and the HTML-only tests — work without it.
"""

import asyncio
import contextlib
import html
from datetime import date
from uuid import UUID

import asyncpg

from worker.db import tenant_tx
from worker.grants.context import GrantPack, gather
from worker.storage import upload_bytes

PDF_MIME = "application/pdf"
DEFAULT_ACCENT = "#B14E2E"  # Hearth terracotta; tenants.brand overrides
NOT_RECORDED = "not recorded"


def _esc(value: object) -> str:
    return html.escape(str(value))


def _money(value: float | None) -> str:
    return f"£{value:,.0f}" if value else "—"


def _amount(value: float | None, unit: str) -> str:
    if value is None:
        return NOT_RECORDED
    rendered = f"{value:,.0f}" if float(value).is_integer() else f"{value:,.2f}"
    return f"{rendered} {unit}".strip()


_CSS = """
@page { size: A4; margin: 14mm 16mm; }
body { font-family: Helvetica, Arial, sans-serif; font-size: 10pt; color: #1a1a1a; margin: 0; }
h1 { font-size: 17pt; margin: 0 0 1mm; }
.sub { color: #555; margin: 0 0 4mm; }
.rule { height: 2.5mm; background: ACCENT; margin-bottom: 5mm; }
h2 { font-size: 10.5pt; text-transform: uppercase; letter-spacing: 0.06em;
     margin: 5mm 0 2mm; color: #444; }
.facts { display: flex; gap: 6mm; }
.facts div { flex: 1; border: 0.4mm solid #ddd; border-radius: 1mm; padding: 2.5mm; }
.facts .big { font-size: 13pt; font-weight: bold; }
table { width: 100%; border-collapse: collapse; }
th { text-align: left; font-size: 8.5pt; text-transform: uppercase; letter-spacing: 0.04em;
     color: #666; padding: 0 2mm 1mm 0; }
td { padding: 1.2mm 2mm 1.2mm 0; vertical-align: middle; border-top: 0.2mm solid #eee; }
.bar { height: 3mm; background: #eee; border-radius: 1.5mm; width: 34mm; }
.bar span { display: block; height: 3mm; background: ACCENT; border-radius: 1.5mm; }
ul { margin: 0; padding-left: 5mm; }
li { margin-bottom: 1mm; }
.muted { color: #666; }
.foot { margin-top: 6mm; font-size: 8.5pt; color: #666; border-top: 0.2mm solid #ddd;
        padding-top: 2mm; }
"""

_PAGE = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>{css}</style></head><body>
<h1>{title}</h1>
<p class="sub">{funder} · Impact summary · {date}</p>
<div class="rule"></div>

<h2>The grant</h2>
<div class="facts">
  <div><div class="muted">Awarded</div><div class="big">{awarded}</div></div>
  <div><div class="muted">Period</div><div class="big">{period}</div></div>
  <div><div class="muted">Reporting</div><div class="big">{reporting}</div></div>
</div>

<h2>What we set out to achieve, and where we are</h2>
{measures}

<h2>In our own words</h2>
<ul>{narratives}</ul>

<h2>Grant conditions</h2>
<ul>{conditions}</ul>

<p class="foot">{foot}</p>
</body></html>
"""


def _measures_html(pack: GrantPack) -> str:
    rows = pack.cumulative_progress()
    if not rows:
        return "<p class='muted'>No impact measures have been recorded for this grant yet.</p>"
    cells = []
    for row in rows:
        share = row["share"]
        # The bar caps at 100% so over-delivery cannot render as a bar wider
        # than its track; the figure beside it still shows the real number.
        width = min(max(share or 0, 0), 1) * 100
        bar = (
            f"<div class='bar'><span style='width:{width:.0f}%'></span></div>"
            if share is not None
            else "<span class='muted'>—</span>"
        )
        cells.append(
            "<tr>"
            f"<td>{_esc(row['name'])}</td>"
            f"<td>{_esc(_amount(row['target'], row['unit']))}</td>"
            f"<td>{_esc(_amount(row['value'], row['unit']))}</td>"
            f"<td>{bar}</td>"
            f"<td>{_esc(f'{share * 100:,.0f}%') if share is not None else '—'}</td>"
            "</tr>"
        )
    head = "<tr><th>Measure</th><th>Target</th><th>Achieved</th><th></th><th></th></tr>"
    return f"<table>{head}{''.join(cells)}</table>"


def _narratives_html(pack: GrantPack) -> str:
    order = {p.id: p.period_start for p in pack.periods}
    written = sorted(
        (o for o in pack.outcomes if o.narrative),
        key=lambda o: order.get(o.reporting_period_id, date.min),
        reverse=True,
    )[:3]
    if not written:
        return "<li class='muted'>No outcome narratives have been recorded yet.</li>"
    return "".join(f"<li>{_esc(o.narrative)}</li>" for o in written)


def _conditions_html(pack: GrantPack) -> str:
    if not pack.conditions:
        return "<li class='muted'>No award conditions recorded.</li>"
    outstanding = [
        c for c in pack.conditions if c.status in ("outstanding", "partially_discharged")
    ]
    discharged = len(pack.conditions) - len(outstanding)
    items = [f"<li>{discharged} of {len(pack.conditions)} condition(s) discharged.</li>"]
    items.extend(f"<li>Outstanding: {_esc(c.description)}</li>" for c in outstanding[:3])
    return "".join(items)


def build_html(pack: GrantPack, brand_accent: str, today: date) -> str:
    application = pack.application
    period = "—"
    if application.start_date and application.end_date:
        period = (
            f"{application.start_date.strftime('%b %Y')}–{application.end_date.strftime('%b %Y')}"
        )

    submitted = [p for p in pack.periods if p.status in ("submitted", "accepted")]
    overdue = [p for p in pack.periods if p.overdue]
    reporting = f"{len(submitted)}/{len(pack.periods)}" if pack.periods else "—"

    foot = (
        f"Prepared from {len(pack.measures)} recorded impact measure(s) and "
        f"{len(pack.outcomes)} recorded outcome(s) on {today.strftime('%d %B %Y')}. "
        "Every figure on this page comes from the organisation's own records."
    )
    if overdue:
        foot += f" {len(overdue)} monitoring return(s) are past their due date."

    return _PAGE.format(
        css=_CSS.replace("ACCENT", brand_accent),
        title=_esc(application.title),
        funder=_esc(application.funder_name or "Grant funding"),
        date=today.strftime("%d %B %Y"),
        awarded=_esc(_money(application.amount_awarded or application.amount_requested)),
        period=_esc(period),
        reporting=_esc(reporting),
        measures=_measures_html(pack),
        narratives=_narratives_html(pack),
        conditions=_conditions_html(pack),
        foot=_esc(foot),
    )


def render_pdf(html_text: str) -> bytes:
    from weasyprint import HTML  # lazy: needs system pango/cairo

    return HTML(string=html_text).write_pdf()


# -- arq job ------------------------------------------------------------------


async def _mark_failed(pool: asyncpg.Pool, tenant_id: str, job_id: str, error: str) -> None:
    async with tenant_tx(pool, tenant_id) as conn:
        await conn.execute(
            "update grant_draft_jobs set status = 'failed', error = $2, updated_at = now()"
            " where id = $1",
            UUID(job_id),
            error[:500],
        )


async def generate_impact_card(
    ctx: dict, tenant_id: str, application_id: str, job_id: str, user_id: str
) -> str:
    pool: asyncpg.Pool = ctx["pool"]
    loop = asyncio.get_running_loop()
    today = date.today()

    async with tenant_tx(pool, tenant_id) as conn:
        job = await conn.fetchrow("select 1 from grant_draft_jobs where id = $1", UUID(job_id))
        if job is None:
            return "gone"  # deleted between enqueue and run
        await conn.execute(
            "update grant_draft_jobs set status = 'running', updated_at = now() where id = $1",
            UUID(job_id),
        )

    try:
        async with tenant_tx(pool, tenant_id) as conn:
            pack = await gather(conn, UUID(application_id), "impact_card", {}, today)
            brand = await conn.fetchval(
                "select brand->>'accent' from tenants where id = $1", tenant_id
            )

        html_text = build_html(pack, brand or DEFAULT_ACCENT, today)
        pdf = await loop.run_in_executor(None, render_pdf, html_text)

        file_key = f"{tenant_id}/grants/{application_id}/drafts/{job_id}.pdf"
        await loop.run_in_executor(None, upload_bytes, file_key, pdf, PDF_MIME)

        async with tenant_tx(pool, tenant_id) as conn:
            await conn.execute(
                """
                update grant_draft_jobs
                set status = 'succeeded', file_key = $2, updated_at = now()
                where id = $1
                """,
                UUID(job_id),
                file_key,
            )
            await conn.execute(
                """
                insert into audit_log (tenant_id, user_id, action, target_type, target_id, meta)
                values ($1, $2, 'grants.impact_card', 'grant_draft_job', $3, '{}')
                """,
                UUID(tenant_id),
                UUID(user_id),
                job_id,
            )
        return "succeeded"
    except BaseException as exc:
        reason = (
            "Impact card generation was interrupted — try again"
            if isinstance(exc, asyncio.CancelledError)
            else f"Impact card generation failed ({type(exc).__name__}: {str(exc)[:160]})"
        )
        with contextlib.suppress(BaseException):
            await _mark_failed(pool, tenant_id, job_id, reason)
        raise
