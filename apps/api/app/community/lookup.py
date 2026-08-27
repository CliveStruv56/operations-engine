"""Chat-side community lookup: cheap token match of the user's message against
the community profile, formatted for prompt injection. Same design as the CRM
lookup (`app/crm/lookup.py`) and for the same reason — the names are short,
the message mentions them near-verbatim, and matching in SQL keeps the chat
path free of extra model calls.

Tokens match whole words only, following the CRM's "SAM" → "Samantha" lesson.
The extra wrinkle here is that people ask about a *kind* of thing ("is there a
shop?", "how do the buses run?") as often as a named one, so category synonyms
map question words onto asset categories, and a statistic also matches through
its claim kind's question hints ("how many households" → Households)."""

import json
import re
from typing import Any

import asyncpg

# The CRM's stopwords plus question words, and — because tokens here may be
# two letters ("do the buses…") — the short function words that would
# otherwise match everything.
_STOPWORDS = frozenset(
    """the and for you your our who what whats when where how why can could
    get his her their them have has does did tell give find need want know
    with from about please there here this that they are was were will would
    much many any all some more most other of on in at to by is it as an or
    be if my we do no not so up us am he she its out off per via""".split()
)
_WORD_RE = re.compile(r"[A-Za-z0-9'-]{2,}")

#: Question words that mean a whole category, not one named thing.
CATEGORY_SYNONYMS: dict[str, frozenset[str]] = {
    "transport": frozenset(
        "bus buses ferry ferries flight flights plane planes airfield transport travel".split()
    ),
    "education": frozenset("school schools nursery education pupils childcare".split()),
    "health": frozenset("doctor doctors gp surgery health nurse care wellbeing dentist".split()),
    "housing": frozenset("housing house houses home homes rent rented dwellings".split()),
    "retail_services": frozenset(
        "shop shops store stores post fuel petrol diesel broadband bank groceries".split()
    ),
    "community_spaces": frozenset("hall halls venue venues club clubs playground".split()),
    "energy": frozenset("energy turbine turbines wind solar electricity power heating".split()),
    "employment": frozenset("job jobs work employer employers employment business".split()),
}


def _tokens(message: str) -> list[str]:
    seen: list[str] = []
    for raw in _WORD_RE.findall(message):
        word = raw.strip("'-").lower().removesuffix("'s")
        if len(word) < 2 or word in _STOPWORDS or word in seen:
            continue
        seen.append(word)
        if len(seen) == 12:
            break
    return seen


def _sql_pattern(tokens: list[str]) -> str:
    """POSIX regex matching any token as a whole word (\\m/\\M boundaries)."""
    return r"\m(" + "|".join(re.escape(t) for t in tokens) + r")\M"


def _py_pattern(tokens: list[str]) -> re.Pattern[str]:
    return re.compile(r"\b(" + "|".join(re.escape(t) for t in tokens) + r")\b", re.IGNORECASE)


async def match_community(
    conn: asyncpg.Connection, message: str
) -> tuple[asyncpg.Record | None, list[asyncpg.Record], list[asyncpg.Record]]:
    """(profile, statistics, assets) the message is asking about.

    The profile row rides along whenever anything matched — a figure without
    the place it describes reads as the organisation's own — and also when
    the place itself is named, so "tell me about Sanday" gets the profile
    even with no figure or facility in the question.
    """
    tokens = _tokens(message)
    if not tokens:
        return None, [], []
    pattern = _sql_pattern(tokens)
    categories = [c for c, syns in CATEGORY_SYNONYMS.items() if syns & set(tokens)]

    stats = await conn.fetch(
        """
        select s.label, s.value, s.unit, s.period, s.source, s.source_url
        from community_statistics s
        where s.label ~* $1
           or exists (select 1 from ref_claim_kinds k
                      where k.key = s.claim_kind
                        and exists (select 1 from unnest(k.question_hints) h
                                    where h ~* $1))
        order by s.label limit 5
        """,
        pattern,
    )
    assets = await conn.fetch(
        """
        select name, category, subcategory, status, settlement, description,
               attributes, contact, url
        from community_assets
        where name ~* $1 or subcategory ~* $1 or category = any($2::text[])
        order by category, name limit 6
        """,
        pattern,
        categories,
    )
    profile = await conn.fetchrow(
        """
        select place_name, council_area, geography_note, settlements, description
        from community_profile
        """
    )

    place_named = False
    if profile is not None:
        haystack = " ".join([profile["place_name"], *profile["settlements"]])
        place_named = _py_pattern(tokens).search(haystack) is not None

    if not stats and not assets and not place_named:
        return None, [], []
    return profile, list(stats), list(assets)


def _fmt_value(value: Any) -> str:
    n = float(value)
    return str(int(n)) if n.is_integer() else str(n)


def community_block(
    profile: asyncpg.Record | None,
    stats: list[asyncpg.Record],
    assets: list[asyncpg.Record],
) -> str:
    parts: list[str] = []
    if profile is not None:
        line = profile["place_name"]
        if profile["council_area"]:
            line += f" ({profile['council_area']})"
        for extra in (profile["description"], profile["geography_note"]):
            if extra:
                line += f". {extra}"
        if profile["settlements"]:
            line += f"\n  settlements: {', '.join(profile['settlements'])}"
        parts.append(line)
    if stats:
        lines = ["Figures:"]
        for s in stats:
            row = f"- {s['label']}: {_fmt_value(s['value'])}"
            if s["unit"]:
                row += f" {s['unit']}"
            provenance = " — ".join(filter(None, [s["period"], s["source"]]))
            if provenance:
                row += f" ({provenance})"
            lines.append(row)
        parts.append("\n".join(lines))
    if assets:
        lines = ["Facilities and services:"]
        for a in assets:
            what = ", ".join(filter(None, [a["subcategory"] or a["category"], a["settlement"]]))
            row = f"- {a['name']}" + (f" ({what})" if what else "")
            if a["status"] != "open":
                row += f" — {a['status']}"
            attributes = a["attributes"]
            if isinstance(attributes, str):
                attributes = json.loads(attributes)
            details = " | ".join(
                f"{k.replace('_', ' ')}: {'yes' if v is True else 'no' if v is False else v}"
                for k, v in attributes.items()
            )
            if details:
                row += f"\n  {details}"
            if a["description"]:
                row += f"\n  {a['description']}"
            extras = " | ".join(f"{k}: {a[k]}" for k in ("contact", "url") if a[k])
            if extras:
                row += f"\n  {extras}"
            lines.append(row)
        parts.append("\n".join(lines))
    return "\n\n".join(parts)
