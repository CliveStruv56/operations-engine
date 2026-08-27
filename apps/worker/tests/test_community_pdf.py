"""Community-profile PDF HTML assembly — offline, WeasyPrint never imported."""

from datetime import date

from worker.community_pdf import build_html

TODAY = date(2026, 8, 27)

PROFILE = {
    "place_name": "Sanday",
    "description": "The largest of Orkney's north isles.",
    "geography_note": "80 minutes by ferry from Kirkwall.",
    "council_area": "Orkney Islands Council",
    "settlements": ["Lady Village", "Kettletoft"],
    "data_sources_note": "Scotland's Census 2022; school roll from the council.",
}

STATS = [
    {
        "label": "Usual residents",
        "value": 494,
        "unit": "people",
        "period": "2022",
        "source": "Scotland's Census 2022",
    },
    {"label": "Households", "value": 240, "unit": None, "period": None, "source": None},
]

ASSETS = [
    {
        "category": "education",
        "subcategory": "primary and secondary",
        "name": "Sanday Community School",
        "status": "open",
        "settlement": "Lady Village",
        "attributes": {"pupils": 68, "nursery": True},
    },
    {
        "category": "transport",
        "subcategory": "flights",
        "name": "Loganair island flights",
        "status": "seasonal",
        "settlement": None,
        "attributes": {},
    },
]


def _html(profile=PROFILE, stats=STATS, assets=ASSETS) -> str:
    return build_html(
        profile,
        stats,
        assets,
        tenant_name="Sanday Development Trust",
        accent="#336699",
        today=TODAY,
    )


def test_header_carries_place_brand_and_date():
    html = _html()
    assert "<h1>Sanday</h1>" in html
    assert "Orkney Islands Council · Community profile · 27 August 2026" in html
    assert "#336699" in html
    assert "Prepared by Sanday Development Trust with Flowgrid" in html


def test_intro_and_settlements_render():
    html = _html()
    assert "The largest of Orkney&#x27;s north isles." in html
    assert "80 minutes by ferry from Kirkwall." in html
    assert "Settlements: Lady Village, Kettletoft" in html


def test_figures_lead_with_value_unit_and_provenance():
    html = _html()
    assert "The place in numbers" in html
    assert '<div class="big">494 people</div>' in html
    assert "2022 — Scotland&#x27;s Census 2022" in html
    # A figure with no unit or provenance renders bare, not with dangling glue.
    assert '<div class="big">240</div>' in html


def test_facilities_group_by_category_with_details():
    html = _html()
    assert "Schools and learning" in html
    assert "Getting here and around" in html
    assert "<b>Sanday Community School</b> — primary and secondary, Lady Village" in html
    assert "pupils: 68 · nursery: yes" in html
    # Non-open status is said; open is the unremarkable default and is not.
    assert "(seasonal)" in html
    assert "(open)" not in html


def test_sources_note_reaches_the_foot():
    html = _html()
    assert "Sources: Scotland&#x27;s Census 2022; school roll from the council." in html


def test_empty_sections_are_omitted():
    html = _html(
        profile={
            "place_name": "Sanday",
            "description": None,
            "geography_note": None,
            "council_area": None,
            "settlements": [],
            "data_sources_note": None,
        },
        stats=[],
        assets=[],
    )
    assert "The place in numbers" not in html
    assert "<h2>" not in html
    assert "Community profile · 27 August 2026" in html


def test_stored_text_is_escaped():
    html = _html(
        profile={**PROFILE, "description": "<script>alert(1)</script>"},
        assets=[
            {
                "category": "other",
                "subcategory": None,
                "name": "<b>Bold</b> shop",
                "status": "open",
                "settlement": None,
                "attributes": {"note": "<i>markup</i>"},
            }
        ],
    )
    assert "<script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "&lt;b&gt;Bold&lt;/b&gt; shop" in html
    assert "&lt;i&gt;markup&lt;/i&gt;" in html
