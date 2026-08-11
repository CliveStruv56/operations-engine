"""DOCX assembly: cover page with a DRAFT header, headings, the module's own
data tables, endnote-style citations and a Data sources appendix.

Citation ids resolve only against the excerpts the pack supplied — fabricated
markers are stripped and counted, never rendered as fake references.
`[TO CONFIRM: …]` markers stay visible in the text and are counted for the
UI's "N items to confirm" panel. Both are product requirements, so they live
here rather than in any one module.
"""

import io
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt

from worker.drafting.pack import DraftPackBase, VaultExcerpt
from worker.drafting.sections import Section

# 4–36 id chars: models routinely truncate long hex ids when echoing them, so
# markers resolve by unique prefix too. Fullwidth 【c:…】 accepted too — CJK-
# bracket echo seen live from the GLM/DeepSeek model family, which also drops
# the `c:` prefix outright (seen live 11 Aug 2026), hence the optional group.
# Keep in step with the api's app/routers/conversations.py.
CITATION_RE = re.compile(r"[\[【]\s*(c:)?\s*([0-9a-fA-F][0-9a-fA-F-]{3,35})\s*[\]】]")
# A prefix-less marker is only believed at full-id length — short bracketed hex
# is ordinary prose far more often than it is a citation.
MIN_UNPREFIXED_ID = 8
# 8-4-4-4-12: a bracketed token of exactly this shape is a marker beyond
# reasonable doubt, prefix or not, so an unresolvable one strips as a
# hallucination rather than surviving into the drafted text.
FULL_ID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\Z")
TO_CONFIRM_RE = re.compile(r"\[TO CONFIRM:[^\]]*\]")

#: A module's table renderer: draw `name`'s rows from the pack's own records.
TableRenderer = Callable[[Document, DraftPackBase], None]


@dataclass
class AssembledDraft:
    data: bytes
    to_confirm_count: int
    citations: list[dict] = field(default_factory=list)
    stripped_citations: int = 0


class CitationIndex:
    """Shared first-appearance numbering across every section."""

    def __init__(self, excerpts: list[VaultExcerpt]) -> None:
        self.by_id = {str(e.chunk_id).lower(): e for e in excerpts}
        self.order: dict[str, int] = {}
        self.stripped = 0

    def resolve(self, text: str) -> str:
        def _sub(match: re.Match) -> str:
            cid = match.group(2).lower()
            # Certain it is a marker: it carries the prefix, or it is a whole
            # uuid. An uncertain one is left verbatim unless it resolves —
            # stripping it would delete drafted prose.
            certain = match.group(1) is not None or FULL_ID_RE.match(cid) is not None
            if not certain and len(cid) < MIN_UNPREFIXED_ID:
                return match.group(0)
            if cid not in self.by_id:
                # Truncated markers resolve only as a unique prefix of one
                # supplied id — fabricated or ambiguous ids still strip.
                matches = [full for full in self.by_id if full.startswith(cid)]
                if len(matches) != 1:
                    if not certain:
                        return match.group(0)
                    self.stripped += 1
                    return ""
                cid = matches[0]
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


def _title_page(doc: Document, pack: DraftPackBase, generated_on: date) -> None:
    for section in doc.sections:
        header = section.header.paragraphs[0]
        header.text = "DRAFT — for review"
        header.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    doc.add_heading(pack.doc_title(), level=0)
    lines = [
        *pack.subject_lines(),
        f"Generated {generated_on.isoformat()} — AI-assisted draft for review",
    ]
    for line in lines:
        paragraph = doc.add_paragraph(line)
        paragraph.runs[0].font.size = Pt(12)


def _warning(doc: Document, pack: DraftPackBase) -> None:
    text = pack.warning_block()
    if not text:
        return
    paragraph = doc.add_paragraph()
    paragraph.add_run(text).bold = True


def _narrative(doc: Document, text: str) -> None:
    for block in text.split("\n\n"):
        block = block.strip()
        if block:
            doc.add_paragraph(block)


def _references(doc: Document, index: CitationIndex) -> None:
    entries = index.references()
    if not entries:
        return
    doc.add_heading("References", level=1)
    for entry in entries:
        pages = f", {entry['pages']}" if entry["pages"] else ""
        doc.add_paragraph(f"[{entry['n']}] {entry['title']}{pages}")


def _data_sources(doc: Document, pack: DraftPackBase, index: CitationIndex) -> None:
    doc.add_heading("Data sources", level=1)
    counts = ", ".join(f"{count} {name}" for name, count in pack.record_counts().items())
    doc.add_paragraph(f"Assembled from module records: {counts}.")
    cited_titles = sorted({e["title"] for e in index.references()})
    if cited_titles:
        doc.add_paragraph("Vault documents cited: " + "; ".join(cited_titles) + ".")
    for note in pack.source_notes():
        doc.add_paragraph(note)


def assemble_docx(
    pack: DraftPackBase,
    sections: list[tuple[Section, str]],
    generated_on: date,
    tables: dict[str, TableRenderer] | None = None,
) -> AssembledDraft:
    index = CitationIndex(pack.excerpts)
    doc = Document()
    renderers = tables or {}

    _title_page(doc, pack, generated_on)
    _warning(doc, pack)
    doc.add_page_break()

    to_confirm = 0
    for number, (section, text) in enumerate(sections, start=1):
        doc.add_heading(f"{number}. {section.title}", level=1)
        resolved = index.resolve(text)
        to_confirm += len(TO_CONFIRM_RE.findall(resolved))
        _narrative(doc, resolved)
        renderer = renderers.get(section.table) if section.table else None
        if renderer is not None:
            renderer(doc, pack)

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
