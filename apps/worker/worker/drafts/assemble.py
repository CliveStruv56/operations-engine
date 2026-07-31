"""DOCX assembly (PRD §5 step 4): title page with a DRAFT header, headings,
real data tables from the context pack, endnote-style citation references
mapped from [c:<id>] markers, and a Data sources appendix.

Citation ids resolve only against the excerpts the pack supplied —
fabricated markers are stripped and counted, never rendered as fake
references (PRD §7.3). [TO CONFIRM: …] markers stay visible in the text and
are counted for the UI's "N items to confirm" panel (PRD §7.2)."""

import io
import re
from dataclasses import dataclass, field
from datetime import date

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt

from worker.drafts.context import ContextPack, VaultExcerpt
from worker.drafts.prompts import DOC_TITLES, Section

CITATION_RE = re.compile(r"\[c:([0-9a-fA-F-]{36})\]")
TO_CONFIRM_RE = re.compile(r"\[TO CONFIRM:[^\]]*\]")


@dataclass
class AssembledDraft:
    data: bytes
    to_confirm_count: int
    citations: list[dict] = field(default_factory=list)
    stripped_citations: int = 0


class _CitationIndex:
    """Shared first-appearance numbering across every section."""

    def __init__(self, excerpts: list[VaultExcerpt]) -> None:
        self.by_id = {str(e.chunk_id).lower(): e for e in excerpts}
        self.order: dict[str, int] = {}
        self.stripped = 0

    def resolve(self, text: str) -> str:
        def _sub(match: re.Match) -> str:
            cid = match.group(1).lower()
            if cid not in self.by_id:
                self.stripped += 1
                return ""
            if cid not in self.order:
                self.order[cid] = len(self.order) + 1
            return f"[{self.order[cid]}]"

        return CITATION_RE.sub(_sub, text)

    def references(self) -> list[dict]:
        entries = []
        for cid, n in sorted(self.order.items(), key=lambda kv: kv[1]):
            excerpt = self.by_id[cid]
            pages = f"p.{excerpt.page_start}–{excerpt.page_end}" if excerpt.page_start else None
            entries.append({"n": n, "title": excerpt.title, "pages": pages})
        return entries


def _doc_title(pack: ContextPack) -> str:
    title = DOC_TITLES[pack.kind]
    if pack.kind == "monthly_report" and pack.report_month:
        title = f"{title} — {pack.report_month}"
    if pack.kind == "funding_bid" and pack.target_funding() is not None:
        title = f"{title} — {pack.target_funding().name}"
    return title


def _title_page(doc: Document, pack: ContextPack, generated_on: date) -> None:
    for section in doc.sections:
        header = section.header.paragraphs[0]
        header.text = "DRAFT — for review"
        header.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    doc.add_heading(_doc_title(pack), level=0)
    lines = [pack.project.name]
    if pack.project.client_org:
        lines.append(f"Prepared for {pack.project.client_org}")
    if pack.project.site_address:
        lines.append(pack.project.site_address)
    lines.append(f"Generated {generated_on.isoformat()} — AI-assisted draft for review")
    for line in lines:
        paragraph = doc.add_paragraph(line)
        paragraph.runs[0].font.size = Pt(12)


def _programme_warning(doc: Document, pack: ContextPack) -> None:
    programme = pack.target_programme()
    if pack.kind != "funding_bid" or programme is None or programme.status == "open":
        return
    paragraph = doc.add_paragraph()
    run = paragraph.add_run(
        f"Programme status was “{programme.status}” when last verified "
        f"{programme.last_verified.isoformat()} — confirm before submitting."
    )
    run.bold = True


def _narrative(doc: Document, text: str) -> None:
    for block in text.split("\n\n"):
        block = block.strip()
        if block:
            doc.add_paragraph(block)


def _budget_table(doc: Document, pack: ContextPack) -> None:
    if not pack.budget_lines:
        return
    table = doc.add_table(rows=1, cols=5)
    table.style = "Light Grid Accent 1"
    for i, head in enumerate(["Category", "Item", "Budget £", "Forecast £", "Actual £"]):
        table.rows[0].cells[i].text = head
    for line in pack.budget_lines:
        cells = table.add_row().cells
        cells[0].text = line.category
        cells[1].text = line.label
        cells[2].text = f"{line.budget:,.0f}"
        cells[3].text = f"{line.forecast:,.0f}"
        cells[4].text = f"{line.actual:,.0f}"
    totals = table.add_row().cells
    totals[0].text = "Total"
    totals[2].text = f"{pack.budget_totals.budget:,.0f}"
    totals[3].text = f"{pack.budget_totals.forecast:,.0f}"
    totals[4].text = f"{pack.budget_totals.actual:,.0f}"
    doc.add_paragraph(f"Forecast variance against budget: £{pack.budget_totals.variance:,.0f}.")


def _funding_table(doc: Document, pack: ContextPack) -> None:
    if not pack.funding:
        return
    table = doc.add_table(rows=1, cols=5)
    table.style = "Light Grid Accent 1"
    for i, head in enumerate(["Source", "Kind", "Status", "Sought £", "Secured £"]):
        table.rows[0].cells[i].text = head
    for source in pack.funding:
        cells = table.add_row().cells
        cells[0].text = source.name
        cells[1].text = source.kind
        cells[2].text = source.status
        cells[3].text = f"{source.amount_sought:,.0f}" if source.amount_sought else "—"
        cells[4].text = f"{source.amount_secured:,.0f}" if source.amount_secured else "—"


def _references(doc: Document, index: _CitationIndex) -> None:
    entries = index.references()
    if not entries:
        return
    doc.add_heading("References", level=1)
    for entry in entries:
        pages = f", {entry['pages']}" if entry["pages"] else ""
        doc.add_paragraph(f"[{entry['n']}] {entry['title']}{pages}")


def _data_sources(doc: Document, pack: ContextPack, index: _CitationIndex) -> None:
    doc.add_heading("Data sources", level=1)
    counts = ", ".join(f"{count} {name}" for name, count in pack.record_counts().items())
    doc.add_paragraph(f"Assembled from module records: {counts}.")
    cited_titles = sorted({e["title"] for e in index.references()})
    if cited_titles:
        doc.add_paragraph("Vault documents cited: " + "; ".join(cited_titles) + ".")
    for programme in pack.programmes:
        note = (
            f"Funding programme “{programme.name}” ({programme.funder}), "
            f"catalogue facts last verified {programme.last_verified.isoformat()}."
        )
        if programme.stale:
            note += " Warning: past its review date — confirm before relying on it."
        doc.add_paragraph(note)


def assemble_docx(
    pack: ContextPack,
    sections: list[tuple[Section, str]],
    generated_on: date,
) -> AssembledDraft:
    index = _CitationIndex(pack.excerpts)
    doc = Document()

    _title_page(doc, pack, generated_on)
    _programme_warning(doc, pack)
    doc.add_page_break()

    to_confirm = 0
    for number, (section, text) in enumerate(sections, start=1):
        doc.add_heading(f"{number}. {section.title}", level=1)
        resolved = index.resolve(text)
        to_confirm += len(TO_CONFIRM_RE.findall(resolved))
        _narrative(doc, resolved)
        if section.table == "budget":
            _budget_table(doc, pack)
        elif section.table == "funding":
            _funding_table(doc, pack)

    _references(doc, index)
    _data_sources(doc, pack, index)

    buffer = io.BytesIO()
    doc.save(buffer)
    return AssembledDraft(
        data=buffer.getvalue(),
        to_confirm_count=to_confirm,
        citations=index.references(),
        stripped_citations=index.stripped,
    )
