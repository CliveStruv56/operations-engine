"""Answer-PDF HTML assembly — offline, WeasyPrint never imported."""

from datetime import date

from worker.answer_pdf import answer_title, build_html

TODAY = date(2026, 8, 15)


def _html(content: str, citations: list[dict] | None = None) -> str:
    return build_html(
        content,
        citations or [],
        title=answer_title(content, "Payment terms"),
        tenant_name="Riverside Trust",
        accent="#336699",
        today=TODAY,
    )


def test_markdown_renders_with_brand_and_title():
    md = "## Standard terms\n\n- 30 days [1]\n\n| Item | Days |\n| --- | --- |\n| Net | 30 |"
    html = _html(md)
    assert "<h2>Standard terms</h2>" in html
    assert "<table>" in html
    assert "Riverside Trust" in html
    assert "#336699" in html
    assert "15 August 2026" in html


def test_title_prefers_the_answer_heading():
    assert answer_title("## Payment summary\ntext", "Chat 3") == "Payment summary"
    assert answer_title("no headings here", "Chat 3") == "Chat 3"
    assert answer_title("no headings here", None) == "Chat answer"


def test_citations_become_a_sources_appendix():
    html = _html(
        "Terms are 30 days [1].",
        [
            {"n": 2, "title": "Handbook", "page_start": 3, "page_end": 4},
            {"n": 1, "title": "Terms & conditions", "url": "https://example.org/t"},
        ],
    )
    assert "Sources" in html
    # Ordered by n, escaped, pages and urls carried.
    assert html.index("Terms &amp; conditions") < html.index("Handbook")
    assert "p.3–4" in html
    assert "https://example.org/t" in html


def test_raw_html_and_stale_markers_do_not_reach_the_page():
    html = _html("Hi <script>alert(1)</script> [c:3174bc60-028e-4df2-82c7-d9b3a4eb1b11].")
    assert "<script>" not in html
    assert "3174bc60" not in html
