"""Chat-side contact lookup: cheap token match of the user's message against
the contact book, formatted for prompt injection. No embeddings — names are
short and a message mentions them near-verbatim, so ILIKE on message tokens
is enough and keeps the chat path free of extra model calls."""

import re

import asyncpg

# Words that appear in almost every "look up a contact" message and would
# only produce noise matches ("email" matching every address, etc.).
_STOPWORDS = frozenset(
    """the and for you your our who what whats how can get his her their them
    have has does did tell give find need want know with from about please
    contact contacts details number phone mobile email address company
    person people""".split()
)
_WORD_RE = re.compile(r"[A-Za-z0-9@.'-]{3,}")
_LIKE_SPECIALS = str.maketrans({"%": r"\%", "_": r"\_", "\\": "\\\\"})


def _tokens(message: str) -> list[str]:
    seen: list[str] = []
    for raw in _WORD_RE.findall(message):
        # "Sarah's" must match "Sarah"; "O'Brien" keeps its apostrophe.
        word = raw.strip(".'-").lower().removesuffix("'s")
        if len(word) < 3 or word in _STOPWORDS or word in seen:
            continue
        seen.append(word.translate(_LIKE_SPECIALS))
        if len(seen) == 12:
            break
    return seen


async def match_contacts(
    conn: asyncpg.Connection, message: str
) -> tuple[list[asyncpg.Record], list[asyncpg.Record]]:
    """(contacts, companies) whose names/emails appear in the message."""
    tokens = _tokens(message)
    if not tokens:
        return [], []
    contacts = await conn.fetch(
        """
        select c.name, c.job_title, c.email, c.phone, c.mobile, c.address, c.notes,
               c.tags, co.name as company_name
        from crm_contacts c
        left join crm_companies co on co.id = c.company_id
        where exists (
            select 1 from unnest($1::text[]) tok
            where c.name ilike '%' || tok || '%'
               or c.email ilike '%' || tok || '%'
               or co.name ilike '%' || tok || '%'
        )
        order by c.name limit 5
        """,
        tokens,
    )
    companies = await conn.fetch(
        """
        select name, website, email, phone, address_line1, address_line2, city,
               postcode, notes
        from crm_companies
        where exists (
            select 1 from unnest($1::text[]) tok where name ilike '%' || tok || '%'
        )
        order by name limit 3
        """,
        tokens,
    )
    return list(contacts), list(companies)


def contacts_block(contacts: list[asyncpg.Record], companies: list[asyncpg.Record]) -> str:
    parts = []
    for c in contacts:
        who = c["name"]
        role = ", ".join(filter(None, [c["job_title"], c["company_name"]]))
        lines = [f"{who}" + (f" — {role}" if role else "")]
        details = [f"{k}: {c[k]}" for k in ("email", "phone", "mobile", "address") if c[k]]
        if details:
            lines.append("  " + " | ".join(details))
        if c["tags"]:
            lines.append("  tags: " + ", ".join(c["tags"]))
        if c["notes"]:
            lines.append(f"  notes: {c['notes']}")
        parts.append("\n".join(lines))
    for co in companies:
        address = ", ".join(
            filter(None, [co["address_line1"], co["address_line2"], co["city"], co["postcode"]])
        )
        lines = [f"{co['name']} (company)"]
        details = [f"{k}: {co[k]}" for k in ("email", "phone", "website") if co[k]]
        if address:
            details.append(f"address: {address}")
        if details:
            lines.append("  " + " | ".join(details))
        if co["notes"]:
            lines.append(f"  notes: {co['notes']}")
        parts.append("\n".join(lines))
    return "\n\n".join(parts)
