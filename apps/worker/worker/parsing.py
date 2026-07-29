"""File → Blocks via Docling (plain text handled directly — Docling doesn't
take .txt). Imports Docling lazily so this module can be imported (and the
chunker tested) without the heavy parse extra installed.

Page anchors come from Docling item provenance, heading paths from tracking
section headers while walking the document tree. OCR is off in Phase 1
(digital documents); table structure recovery is on.
"""

from pathlib import Path

from worker.blocks import Block

_converter = None


def _get_converter():
    global _converter
    if _converter is None:
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import PdfPipelineOptions
        from docling.document_converter import DocumentConverter, PdfFormatOption

        pdf_options = PdfPipelineOptions(do_ocr=False, do_table_structure=True)
        _converter = DocumentConverter(
            format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=pdf_options)}
        )
    return _converter


def parse_file(path: str) -> list[Block]:
    if Path(path).suffix.lower() in (".txt", ".md"):
        return _parse_text(Path(path).read_text(encoding="utf-8", errors="replace"))
    return _parse_docling(path)


def _parse_docling(path: str) -> list[Block]:
    from docling_core.types.doc import DocItemLabel

    doc = _get_converter().convert(path).document
    blocks: list[Block] = []
    # heading level -> text; a new header at level N clears deeper levels.
    heading_stack: dict[int, str] = {}

    for item, _level in doc.iterate_items():
        page = item.prov[0].page_no if getattr(item, "prov", None) else None
        label = getattr(item, "label", None)

        if label in (DocItemLabel.SECTION_HEADER, DocItemLabel.TITLE):
            header_level = 0 if label == DocItemLabel.TITLE else getattr(item, "level", 1)
            heading_stack[header_level] = item.text.strip()
            for deeper in [k for k in heading_stack if k > header_level]:
                del heading_stack[deeper]
            continue

        heading_path = [heading_stack[k] for k in sorted(heading_stack)]
        if label == DocItemLabel.TABLE:
            markdown = item.export_to_markdown(doc=doc)
            if markdown.strip():
                blocks.append(Block(markdown, heading_path, page, is_table=True))
        elif label in (
            DocItemLabel.TEXT,
            DocItemLabel.PARAGRAPH,
            DocItemLabel.LIST_ITEM,
            DocItemLabel.CODE,
            DocItemLabel.FORMULA,
            DocItemLabel.CHECKBOX_SELECTED,
            DocItemLabel.CHECKBOX_UNSELECTED,
        ):
            text = getattr(item, "text", "").strip()
            if text:
                blocks.append(Block(text, heading_path, page))
    return blocks


def _parse_text(raw: str) -> list[Block]:
    """Markdown-ish plain text: # headings become the heading path."""
    blocks: list[Block] = []
    heading_stack: dict[int, str] = {}
    for para in raw.split("\n\n"):
        para = para.strip()
        if not para:
            continue
        if para.startswith("#"):
            hashes = len(para) - len(para.lstrip("#"))
            title = para.lstrip("#").strip()
            if title and hashes <= 6:
                heading_stack[hashes] = title
                for deeper in [k for k in heading_stack if k > hashes]:
                    del heading_stack[deeper]
                continue
        heading_path = [heading_stack[k] for k in sorted(heading_stack)]
        is_table = para.lstrip().startswith("|")
        blocks.append(Block(para, heading_path, None, is_table=is_table))
    return blocks
