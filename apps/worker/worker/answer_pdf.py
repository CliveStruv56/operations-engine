"""A chat answer rendered as a one-page-or-more branded PDF.

No LLM anywhere: the answer is already written and its citations already
resolved — this is markdown → HTML → WeasyPrint, with the tenant's brand
colour on the header rule (brand appears in exports only, never app chrome)
and the answer's numbered sources as an appendix.

WeasyPrint imports lazily (system pango/cairo), same as the health card, so
the HTML-only tests run without it.
"""

import asyncio
import contextlib
import html
import json
from datetime import date
from uuid import UUID

import asyncpg
from markdown_it import MarkdownIt

from worker.db import tenant_tx
from worker.drafting.assemble import CITATION_RE
from worker.pdf import render_pdf
from worker.storage import upload_bytes

PDF_MIME = "application/pdf"
DEFAULT_ACCENT = "#b14e2e"  # Hearth terracotta; tenants.brand overrides

#: commonmark + tables; html off, so any raw HTML the model produced is
#: escaped rather than rendered (the commonmark preset would allow it).
#:
#: Images are disabled outright. `html: False` does not cover them —
#: `![](http://…)` is markdown, not HTML, and renders to an `<img>` that
#: WeasyPrint would then fetch from inside the private network. The renderer
#: refuses remote fetches too (worker/pdf.py); this is the belt to that
#: braces, and it keeps an injected image out of the document entirely rather
#: than failing the export. An answer has no legitimate images: every figure a
#: tenant sees is text plus citations.
_MD = MarkdownIt("commonmark", {"html": False}).enable("table").disable("image")

_CSS = """
@page { size: A4; margin: 16mm 18mm; }
body { font-family: Helvetica, Arial, sans-serif; font-size: 10.5pt;
       color: #1a1a1a; margin: 0; line-height: 1.45; }
h1.title { font-size: 16pt; margin: 0 0 1mm; }
.sub { color: #555; margin: 0 0 4mm; font-size: 9pt; }
.rule { height: 2.5mm; background: ACCENT; margin-bottom: 5mm; }
h1, h2, h3 { margin: 4mm 0 1.5mm; }
h1 { font-size: 13pt; } h2 { font-size: 11.5pt; } h3 { font-size: 10.5pt; }
table { border-collapse: collapse; margin: 2mm 0; }
th, td { border: 0.3mm solid #ccc; padding: 1.2mm 2.5mm; text-align: left; }
th { background: #f4f4f4; }
ul, ol { margin: 1mm 0; padding-left: 6mm; }
blockquote { margin: 2mm 0; padding-left: 3mm; border-left: 1mm solid #ddd; color: #555; }
code { font-family: Courier, monospace; font-size: 9pt; }
.sources { margin-top: 6mm; border-top: 0.3mm solid #ccc; padding-top: 2.5mm; }
.sources h2 { font-size: 9.5pt; text-transform: uppercase; letter-spacing: 0.06em; color: #444; }
.sources ol { font-size: 9pt; color: #444; }
"""

_PAGE = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>{css}</style></head><body>
<h1 class="title">{title}</h1>
<p class="sub">{tenant} · Drafted with Flowgrid · {date}</p>
<div class="rule"></div>
{body}
{sources}
</body></html>
"""


def _strip_unresolved_markers(text: str) -> str:
    """Rows written before a marker shape was recognised can still carry raw
    ids — the same defensive strip the web answer view applies."""

    def _sub(match) -> str:
        if match.group("prefixed") is not None:
            return ""
        return "" if len(match.group("bare") or "") >= 8 else match.group(0)

    return CITATION_RE.sub(_sub, text)


def answer_title(content: str, conversation_title: str | None) -> str:
    """The answer's own first heading, else the conversation's name."""
    for line in content.splitlines():
        text = line.lstrip("#").replace("**", "").strip()
        if line.lstrip().startswith("#") and text:
            return text[:120]
    return (conversation_title or "Chat answer")[:120]


def build_html(
    content: str,
    citations: list[dict],
    *,
    title: str,
    tenant_name: str,
    accent: str,
    today: date,
) -> str:
    body = _MD.render(_strip_unresolved_markers(content))
    sources = ""
    if citations:
        items = []
        for c in sorted(citations, key=lambda c: c.get("n", 0)):
            entry = html.escape(str(c.get("title", "Untitled")))
            if c.get("page_start"):
                entry += f", p.{c['page_start']}–{c['page_end']}"
            if c.get("url"):
                entry += f" — {html.escape(str(c['url']))}"
            items.append(f"<li>{entry}</li>")
        sources = f'<div class="sources"><h2>Sources</h2><ol>{"".join(items)}</ol></div>'
    return _PAGE.format(
        css=_CSS.replace("ACCENT", accent),
        title=html.escape(title),
        tenant=html.escape(tenant_name),
        date=today.strftime("%d %B %Y"),
        body=body,
        sources=sources,
    )


# -- arq job ------------------------------------------------------------------


async def _mark_failed(pool: asyncpg.Pool, tenant_id: str, job_id: str, error: str) -> None:
    async with tenant_tx(pool, tenant_id) as conn:
        await conn.execute(
            "update conversation_export_jobs"
            " set status = 'failed', error = $2, updated_at = now() where id = $1",
            UUID(job_id),
            error[:500],
        )


async def render_answer_pdf(ctx: dict, tenant_id: str, job_id: str, user_id: str) -> str:
    pool: asyncpg.Pool = ctx["pool"]
    loop = asyncio.get_running_loop()
    today = date.today()

    async with tenant_tx(pool, tenant_id) as conn:
        job = await conn.fetchrow(
            "select * from conversation_export_jobs where id = $1", UUID(job_id)
        )
        if job is None:
            return "gone"
        await conn.execute(
            "update conversation_export_jobs set status = 'running', updated_at = now()"
            " where id = $1",
            UUID(job_id),
        )

    try:
        async with tenant_tx(pool, tenant_id) as conn:
            message = await conn.fetchrow(
                """
                select m.content, m.citations, c.title as conversation_title
                from messages m join conversations c on c.id = m.conversation_id
                where m.id = $1
                """,
                job["message_id"],
            )
            if message is None:
                raise RuntimeError("message vanished before the export ran")
            tenant = await conn.fetchrow(
                "select name, brand->>'accent' as accent from tenants where id = $1",
                UUID(tenant_id),
            )

        citations = json.loads(message["citations"]) if message["citations"] else []
        html_text = build_html(
            message["content"],
            citations,
            title=answer_title(message["content"], message["conversation_title"]),
            tenant_name=tenant["name"] if tenant else "Flowgrid workspace",
            accent=(tenant["accent"] if tenant else None) or DEFAULT_ACCENT,
            today=today,
        )
        pdf = await loop.run_in_executor(None, render_pdf, html_text)

        file_key = (
            f"{tenant_id}/conversations/{job['conversation_id']}/answers/{job['message_id']}.pdf"
        )
        await loop.run_in_executor(None, upload_bytes, file_key, pdf, PDF_MIME)

        async with tenant_tx(pool, tenant_id) as conn:
            await conn.execute(
                """
                update conversation_export_jobs
                set status = 'succeeded', file_key = $2, updated_at = now()
                where id = $1
                """,
                UUID(job_id),
                file_key,
            )
            await conn.execute(
                """
                insert into audit_log (tenant_id, user_id, action, target_type, target_id, meta)
                values ($1, $2, 'message.pdf_rendered', 'conversation_export_job', $3, '{}')
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
