"""Slide-deck export: parse a slides-mode chat message (structured markdown,
shape enforced by prompts.TASK_PROMPTS["slides"]) and render it as a native,
editable PPTX in the tenant's branding. Parsing and rendering are
deterministic and sub-second — no LLM call, no job queue.

python-pptx is MIT-licensed (constraint 1). Decks are built on blank 16:9
layouts with explicit text boxes so no bundled template file is needed;
the tenant's accent colour and logo are the theme.
"""

import re
from dataclasses import dataclass
from io import BytesIO

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.util import Inches, Pt

PPTX_MIME = "application/vnd.openxmlformats-officedocument.presentationml.presentation"

DEFAULT_ACCENT = "#1f6d53"
INK = RGBColor(0x1C, 0x1E, 0x21)
MUTED = RGBColor(0x6B, 0x6E, 0x74)

_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")
_H1 = re.compile(r"^#\s+(.+)$")
_H2 = re.compile(r"^##\s+(.+)$")
_BULLET = re.compile(r"^\s*[-*]\s+(.+)$")
_NOTES = re.compile(r"^\**Speaker notes:?\**\s*(.*)$", re.IGNORECASE)
_SLIDE_PREFIX = re.compile(r"^Slide\s*\d+\s*[—–-]\s*", re.IGNORECASE)
# Inline markdown + resolved citation markers ([1]) don't belong on slides.
_MARKUP = re.compile(r"\*\*|\*|`|\[\d+\]")


@dataclass(frozen=True)
class Slide:
    title: str
    bullets: list[str]
    notes: str | None


@dataclass(frozen=True)
class Deck:
    title: str
    slides: list[Slide]


def _clean(text: str) -> str:
    return re.sub(r"\s{2,}", " ", _MARKUP.sub("", text)).strip()


def parse_deck(content: str) -> Deck | None:
    """Deck from slides-mode markdown, or None when the message isn't one.
    Tolerant of drift: any ## heading starts a slide; bullets are - / * lines;
    a "Speaker notes:" paragraph becomes the notes pane."""
    deck_title: str | None = None
    slides: list[Slide] = []
    title: str | None = None
    bullets: list[str] = []
    notes_parts: list[str] = []
    in_notes = False

    def _flush() -> None:
        nonlocal title, bullets, notes_parts, in_notes
        if title is not None:
            slides.append(Slide(title, bullets, " ".join(notes_parts) or None))
        title, bullets, notes_parts, in_notes = None, [], [], False

    for raw in content.splitlines():
        line = raw.strip()
        if not line or line == "---":
            in_notes = False
            continue
        if (m := _H2.match(line)) is not None:
            _flush()
            title = _clean(_SLIDE_PREFIX.sub("", m.group(1)))
            continue
        if (m := _H1.match(line)) is not None:
            if deck_title is None:
                deck_title = _clean(m.group(1))
            continue
        if title is None:
            continue  # prose before the first slide
        if (m := _NOTES.match(line)) is not None:
            in_notes = True
            if m.group(1):
                notes_parts.append(_clean(m.group(1)))
            continue
        if (m := _BULLET.match(raw)) is not None:
            in_notes = False
            bullets.append(_clean(m.group(1)))
            continue
        if in_notes:
            notes_parts.append(_clean(line))

    _flush()
    if not slides:
        return None
    return Deck(deck_title or slides[0].title, slides)


def _accent_color(accent_hex: str | None) -> RGBColor:
    hex_value = accent_hex if accent_hex and _HEX.match(accent_hex) else DEFAULT_ACCENT
    return RGBColor.from_string(hex_value.lstrip("#"))


def _add_rule(slide, accent: RGBColor, left, top, width, height=Inches(0.05)) -> None:
    rule = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, left, top, width, height)
    rule.fill.solid()
    rule.fill.fore_color.rgb = accent
    rule.line.fill.background()
    rule.shadow.inherit = False


def _add_logo(slide, logo: bytes, top) -> None:
    slide.shapes.add_picture(BytesIO(logo), Inches(0.6), top, height=Inches(0.5))


def render_pptx(deck: Deck, accent_hex: str | None = None, logo: bytes | None = None) -> bytes:
    accent = _accent_color(accent_hex)
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    blank = prs.slide_layouts[6]

    # Title slide.
    slide = prs.slides.add_slide(blank)
    if logo:
        _add_logo(slide, logo, Inches(0.5))
    box = slide.shapes.add_textbox(Inches(0.9), Inches(2.7), Inches(11.5), Inches(1.8))
    frame = box.text_frame
    frame.word_wrap = True
    para = frame.paragraphs[0]
    run = para.add_run()
    run.text = deck.title
    run.font.size = Pt(40)
    run.font.bold = True
    run.font.color.rgb = INK
    _add_rule(slide, accent, Inches(0.95), Inches(4.35), Inches(2.5), Inches(0.07))

    # Content slides.
    for item in deck.slides:
        slide = prs.slides.add_slide(blank)
        box = slide.shapes.add_textbox(Inches(0.7), Inches(0.45), Inches(12), Inches(0.9))
        frame = box.text_frame
        frame.word_wrap = True
        run = frame.paragraphs[0].add_run()
        run.text = item.title
        run.font.size = Pt(26)
        run.font.bold = True
        run.font.color.rgb = accent
        _add_rule(slide, accent, Inches(0.75), Inches(1.25), Inches(1.6))

        if item.bullets:
            box = slide.shapes.add_textbox(Inches(0.9), Inches(1.7), Inches(11.5), Inches(5.2))
            frame = box.text_frame
            frame.word_wrap = True
            for i, bullet in enumerate(item.bullets):
                para = frame.paragraphs[0] if i == 0 else frame.add_paragraph()
                para.space_after = Pt(10)
                run = para.add_run()
                run.text = f"•  {bullet}"
                run.font.size = Pt(17)
                run.font.color.rgb = INK

        if item.notes:
            slide.notes_slide.notes_text_frame.text = item.notes

    out = BytesIO()
    prs.save(out)
    return out.getvalue()


def deck_filename(title: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", title).strip("-").lower()[:60]
    return f"{slug or 'slides'}.pptx"
