"""The community profile as a one-page branded PDF.

No LLM anywhere: the profile, figures and facilities are already recorded —
this is rows → HTML → WeasyPrint. This is the sheet a development trust
hands the council, a funder, or somebody thinking of moving to the island,
so it leads with the place and its headline figures and keeps everything on
one page where the data allows.

Tenant `brand.accent` colours the header rule only — exports are the one
place a tenant colour is allowed (ASSUMPTIONS #17). WeasyPrint imports
lazily (system pango/cairo), same as the health card, so the HTML-only
tests run without it.
"""

import asyncio
import contextlib
import html
import json
from datetime import date
from typing import Any
from uuid import UUID

import asyncpg

from worker.db import tenant_tx
from worker.storage import upload_bytes

PDF_MIME = "application/pdf"
DEFAULT_ACCENT = "#1f6d53"  # deep green; tenants.brand overrides

#: Mirrors the web's ASSET_CATEGORY_LABELS (apps/web/lib/community.ts) — the
#: PDF must read the way the profile page reads.
CATEGORY_ORDER = (
    "transport",
    "education",
    "health",
    "housing",
    "retail_services",
    "community_spaces",
    "energy",
    "employment",
    "other",
)
CATEGORY_LABELS = {
    "transport": "Getting here and around",
    "education": "Schools and learning",
    "health": "Health and wellbeing",
    "housing": "Housing",
    "retail_services": "Shops and services",
    "community_spaces": "Community spaces",
    "energy": "Energy",
    "employment": "Work and employers",
    "other": "Everything else",
}

_CSS = """
@page { size: A4; margin: 14mm 16mm; }
body { font-family: Helvetica, Arial, sans-serif; font-size: 9.5pt; color: #1a1a1a;
       margin: 0; line-height: 1.4; }
h1 { font-size: 17pt; margin: 0 0 1mm; }
.sub { color: #555; margin: 0 0 4mm; }
.rule { height: 2.5mm; background: ACCENT; margin-bottom: 4mm; }
.intro { margin: 0 0 2mm; }
h2 { font-size: 10pt; text-transform: uppercase; letter-spacing: 0.06em;
     margin: 4mm 0 1.5mm; color: #444; }
.facts { display: flex; flex-wrap: wrap; gap: 4mm; }
.facts div { flex: 1 1 36mm; border: 0.4mm solid #ddd; border-radius: 1mm; padding: 2mm 2.5mm; }
.facts .big { font-size: 13pt; font-weight: bold; }
.facts .prov { font-size: 7.5pt; color: #666; margin-top: 0.5mm; }
ul { margin: 0; padding-left: 5mm; }
li { margin-bottom: 0.8mm; }
.muted { color: #666; }
.detail { color: #555; font-size: 8.5pt; }
.foot { margin-top: 5mm; font-size: 8pt; color: #666; border-top: 0.2mm solid #ddd;
        padding-top: 2mm; }
"""

_PAGE = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>{css}</style></head><body>
<h1>{place}</h1>
<p class="sub">{sub}</p>
<div class="rule"></div>
{intro}
{figures}
{facilities}
<p class="foot">{foot}</p>
</body></html>
"""


def _esc(value: object) -> str:
    return html.escape(str(value))


def _fmt_value(value: Any) -> str:
    n = float(value)
    return f"{int(n):,}" if n.is_integer() else str(n)


def _attr_label(value: Any) -> str:
    if value is True:
        return "yes"
    if value is False:
        return "no"
    return str(value)


def _intro_html(profile: dict) -> str:
    parts = []
    if profile.get("description"):
        parts.append(f'<p class="intro">{_esc(profile["description"])}</p>')
    if profile.get("geography_note"):
        parts.append(f'<p class="intro muted">{_esc(profile["geography_note"])}</p>')
    if profile.get("settlements"):
        parts.append(
            f'<p class="intro muted">Settlements: {_esc(", ".join(profile["settlements"]))}</p>'
        )
    return "\n".join(parts)


def _figures_html(stats: list[dict]) -> str:
    if not stats:
        return ""
    cards = []
    for s in stats:
        value = _fmt_value(s["value"]) + (f" {_esc(s['unit'])}" if s["unit"] else "")
        provenance = " — ".join(filter(None, [s["period"], s["source"]]))
        prov = f'<div class="prov">{_esc(provenance)}</div>' if provenance else ""
        cards.append(
            f'<div><div class="muted">{_esc(s["label"])}</div>'
            f'<div class="big">{value}</div>{prov}</div>'
        )
    return f'<h2>The place in numbers</h2><div class="facts">{"".join(cards)}</div>'


def _facilities_html(assets: list[dict]) -> str:
    sections = []
    for category in CATEGORY_ORDER:
        rows = [a for a in assets if a["category"] == category]
        if not rows:
            continue
        items = []
        for a in rows:
            attributes = a["attributes"]
            if isinstance(attributes, str):
                attributes = json.loads(attributes)
            meta = ", ".join(filter(None, [a["subcategory"], a["settlement"]]))
            line = f"<b>{_esc(a['name'])}</b>"
            if meta:
                line += f" — {_esc(meta)}"
            if a["status"] != "open":
                line += f" <span class='muted'>({_esc(a['status'])})</span>"
            details = " · ".join(
                f"{_esc(k.replace('_', ' '))}: {_esc(_attr_label(v))}"
                for k, v in attributes.items()
            )
            if details:
                line += f' <span class="detail">{details}</span>'
            items.append(f"<li>{line}</li>")
        sections.append(f"<h2>{_esc(CATEGORY_LABELS[category])}</h2><ul>{''.join(items)}</ul>")
    return "\n".join(sections)


def build_html(
    profile: dict,
    stats: list[dict],
    assets: list[dict],
    *,
    tenant_name: str,
    accent: str,
    today: date,
) -> str:
    sub_parts = [profile.get("council_area"), "Community profile", today.strftime("%d %B %Y")]
    foot_parts = []
    if profile.get("data_sources_note"):
        foot_parts.append(f"Sources: {profile['data_sources_note']}")
    foot_parts.append(f"Prepared by {tenant_name} with Flowgrid")
    return _PAGE.format(
        css=_CSS.replace("ACCENT", accent),
        place=_esc(profile["place_name"]),
        sub=_esc(" · ".join(p for p in sub_parts if p)),
        intro=_intro_html(profile),
        figures=_figures_html(stats),
        facilities=_facilities_html(assets),
        foot=_esc(" · ".join(foot_parts)),
    )


def render_pdf(html_text: str) -> bytes:
    from weasyprint import HTML  # lazy: needs system pango/cairo

    return HTML(string=html_text).write_pdf()


# -- arq job ------------------------------------------------------------------


async def _mark_failed(pool: asyncpg.Pool, tenant_id: str, job_id: str, error: str) -> None:
    async with tenant_tx(pool, tenant_id) as conn:
        await conn.execute(
            "update community_export_jobs"
            " set status = 'failed', error = $2, updated_at = now() where id = $1",
            UUID(job_id),
            error[:500],
        )


async def render_community_pdf(ctx: dict, tenant_id: str, job_id: str, user_id: str) -> str:
    pool: asyncpg.Pool = ctx["pool"]
    loop = asyncio.get_running_loop()
    today = date.today()

    async with tenant_tx(pool, tenant_id) as conn:
        job = await conn.fetchrow(
            "select * from community_export_jobs where id = $1", UUID(job_id)
        )
        if job is None:
            return "gone"
        await conn.execute(
            "update community_export_jobs"
            " set status = 'running', updated_at = now() where id = $1",
            UUID(job_id),
        )

    try:
        async with tenant_tx(pool, tenant_id) as conn:
            profile = await conn.fetchrow(
                """
                select place_name, description, geography_note, council_area,
                       settlements, data_sources_note
                from community_profile
                """
            )
            if profile is None:
                raise RuntimeError("the profile vanished before the export ran")
            # Register-fed figures lead — they are what a report opens with.
            stats = await conn.fetch(
                """
                select label, value, unit, period, source from community_statistics
                order by (claim_kind is null), label, period nulls first
                """
            )
            assets = await conn.fetch(
                """
                select category, subcategory, name, status, settlement, attributes
                from community_assets order by category, name
                """
            )
            tenant = await conn.fetchrow(
                "select name, brand->>'accent' as accent from tenants where id = $1",
                UUID(tenant_id),
            )

        html_text = build_html(
            dict(profile),
            [dict(r) for r in stats],
            [dict(r) for r in assets],
            tenant_name=tenant["name"] if tenant else "Flowgrid workspace",
            accent=(tenant["accent"] if tenant else None) or DEFAULT_ACCENT,
            today=today,
        )
        pdf = await loop.run_in_executor(None, render_pdf, html_text)

        file_key = f"{tenant_id}/community/exports/{job_id}.pdf"
        await loop.run_in_executor(None, upload_bytes, file_key, pdf, PDF_MIME)

        async with tenant_tx(pool, tenant_id) as conn:
            await conn.execute(
                """
                update community_export_jobs
                set status = 'succeeded', file_key = $2, updated_at = now()
                where id = $1
                """,
                UUID(job_id),
                file_key,
            )
            await conn.execute(
                """
                insert into audit_log (tenant_id, user_id, action, target_type, target_id, meta)
                values ($1, $2, 'community.profile_pdf_rendered', 'community_export_job', $3, '{}')
                """,
                UUID(tenant_id),
                UUID(user_id),
                job_id,
            )
        return "succeeded"
    except BaseException as exc:
        reason = (
            "PDF export was interrupted — try again"
            if isinstance(exc, asyncio.CancelledError)
            else f"PDF export failed ({type(exc).__name__}: {str(exc)[:160]})"
        )
        with contextlib.suppress(BaseException):
            await _mark_failed(pool, tenant_id, job_id, reason)
        raise
