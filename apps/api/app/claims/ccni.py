"""The Northern Ireland charity register, from an operator-refreshed snapshot.

CCNI publishes no per-charity lookup API — the register is a bulk CSV export.
So this jurisdiction works differently from the other three: the operator
loads the export into `ref_ccni_charities` (owner connection, table replaced
whole), and a tenant's lookup reads the snapshot inside its ordinary tenant
transaction. No platform key, no shared allowance, no rate-limit concern.

Refresh (in-container, like the seeders):

    railway ssh --service api "python -m app.claims.ccni"

The default export URL is CCNI's own; if it drifts, download the CSV from
their charity search yourself and pass a file path (or the new URL) as the
one argument. Review dates on imported claims derive from the snapshot's
loaded date, not the register's — a snapshot cannot promise more freshness
than its last refresh.
"""

import asyncio
import csv
import io
import sys
from dataclasses import dataclass
from datetime import UTC, date, datetime

import asyncpg

from app.claims.registers import (
    ACTIVE_CHARITY_STATUSES,
    EW_FILING_MONTHS,
    RegisterFact,
    RegisterFacts,
    _months_after,
    _parse_date,
)
from app.errors import ApiError

#: CCNI's own bulk export, updated daily on their side. `include=Removed`
#: matters: a removed charity must be present so the dead-record gate can say
#: "removed" rather than "not found".
DEFAULT_EXPORT_URL = (
    "https://www.charitycommissionni.org.uk/umbraco/api/charityApi/"
    "ExportSearchResultsToCsv/?include=Removed&pageNumber=1"
)
CCNI_PUBLIC = "https://www.charitycommissionni.org.uk/charity-details/?regId={n}&subId=0"

#: How long identity facts from a snapshot stay presumed-current. The other
#: registers date reviews from their own filing calendars; a snapshot's only
#: honest anchor is when the operator last refreshed it.
SNAPSHOT_REVIEW_MONTHS = 12


@dataclass(frozen=True)
class CcniRow:
    reg_number: str
    name: str
    status: str
    date_registered: date | None
    address: str | None
    website: str | None
    company_number: str | None
    total_income: float | None
    total_spending: float | None
    financial_year_end: date | None
    charitable_purposes: str | None
    what_it_does: str | None
    who_it_helps: str | None
    trustees: tuple[str, ...]


#: Header candidates, normalised (lowercased, single-spaced). The export's
#: exact wording has drifted before; every field reads by candidates rather
#: than position, and an unrecognised column is ignored.
_FIELDS: dict[str, tuple[str, ...]] = {
    "reg_number": ("reg charity number", "registered charity number", "charity number"),
    "sub_number": ("sub charity number", "subsidiary number"),
    "name": ("charity name", "name"),
    "status": ("status", "charity status"),
    "date_registered": ("date registered", "registration date", "date of registration"),
    "address": ("public address", "address"),
    "website": ("website",),
    "company_number": ("company number", "company registration number"),
    "total_income": ("total income", "gross income", "income"),
    "total_spending": ("total spending", "total expenditure", "expenditure", "spending"),
    "financial_year_end": (
        "date for financial year ending",
        "financial year end",
        "financial period end",
    ),
    "charitable_purposes": ("charitable purposes",),
    "what_it_does": ("what the charity does",),
    "who_it_helps": ("who the charity helps",),
    "trustees": ("charity trustees", "trustees"),
}


def _norm_header(raw: str) -> str:
    # ﻿: DictReader keeps the BOM on the first header of a utf-8 export.
    return " ".join(raw.replace("﻿", "").strip().lower().split())


def _money(raw: str | None) -> float | None:
    if raw is None:
        return None
    text = raw.strip().replace("£", "").replace(",", "")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _names(raw: str | None) -> tuple[str, ...]:
    """Trustee names from one delimited cell.

    CCNI lists names title-first ("Mr John Smith"), so a comma is a separator
    rather than part of a name; a semicolon wins where present.
    """
    if not raw:
        return ()
    sep = ";" if ";" in raw else ","
    return tuple(p.strip() for p in raw.split(sep) if p.strip())


def parse_snapshot_csv(text: str) -> list[CcniRow]:
    """The export, defensively. Sub-charities (non-zero sub number) are the
    same organisation registered again under a parent — one row per charity
    is what a lookup by number needs, so they are skipped."""
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        return []
    by_field: dict[str, str] = {}
    normalised = {_norm_header(h): h for h in reader.fieldnames}
    for field, candidates in _FIELDS.items():
        for candidate in candidates:
            if candidate in normalised:
                by_field[field] = normalised[candidate]
                break

    def pick(row: dict, field: str) -> str | None:
        header = by_field.get(field)
        value = (row.get(header) or "").strip() if header else ""
        return value or None

    rows: list[CcniRow] = []
    for row in reader:
        number = "".join(ch for ch in (pick(row, "reg_number") or "") if ch.isdigit())
        name = pick(row, "name")
        if not number or not name:
            continue
        sub = pick(row, "sub_number")
        if sub and sub.strip("0"):
            continue
        rows.append(
            CcniRow(
                reg_number=number,
                name=name,
                status=pick(row, "status") or "unknown",
                date_registered=_parse_date(pick(row, "date_registered")),
                address=pick(row, "address"),
                website=pick(row, "website"),
                company_number=pick(row, "company_number"),
                total_income=_money(pick(row, "total_income")),
                total_spending=_money(pick(row, "total_spending")),
                financial_year_end=_parse_date(pick(row, "financial_year_end")),
                charitable_purposes=pick(row, "charitable_purposes"),
                what_it_does=pick(row, "what_it_does"),
                who_it_helps=pick(row, "who_it_helps"),
                trustees=_names(pick(row, "trustees")),
            )
        )
    return rows


async def load_snapshot(conn: asyncpg.Connection, rows: list[CcniRow], source: str) -> int:
    """Replace the snapshot whole, atomically. A partial register that looks
    complete is worse than last week's complete one, so an empty parse
    refuses rather than truncating."""
    if not rows:
        raise ValueError("Parsed no charities — is this the register export?")
    async with conn.transaction():
        await conn.execute("delete from ref_ccni_charities")
        await conn.executemany(
            """
            insert into ref_ccni_charities (reg_number, name, status, date_registered,
                address, website, company_number, total_income, total_spending,
                financial_year_end, charitable_purposes, what_it_does, who_it_helps, trustees)
            values ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
            """,
            [
                (
                    r.reg_number,
                    r.name,
                    r.status,
                    r.date_registered,
                    r.address,
                    r.website,
                    r.company_number,
                    r.total_income,
                    r.total_spending,
                    r.financial_year_end,
                    r.charitable_purposes,
                    r.what_it_does,
                    r.who_it_helps,
                    list(r.trustees),
                )
                for r in rows
            ],
        )
        await conn.execute(
            """
            insert into ref_ccni_snapshot (id, loaded_at, source, row_count)
            values (true, $1, $2, $3)
            on conflict (id) do update set
                loaded_at = excluded.loaded_at, source = excluded.source,
                row_count = excluded.row_count
            """,
            datetime.now(UTC),
            source,
            len(rows),
        )
    return len(rows)


async def fetch_ccni(conn: asyncpg.Connection, number: str) -> RegisterFacts:
    """One NI charity from the snapshot, in the same shape as the live
    register clients so the import route treats all four alike."""
    meta = await conn.fetchrow("select loaded_at from ref_ccni_snapshot where id")
    if meta is None:
        raise ApiError(
            503,
            "register_unavailable",
            "The Northern Ireland register snapshot has not been loaded yet",
        )
    row = await conn.fetchrow("select * from ref_ccni_charities where reg_number = $1", number)
    if row is None:
        raise ApiError(
            404,
            "register_not_found",
            "That number is not in the Northern Ireland register snapshot —"
            " it may be newer than the operator's last refresh",
        )

    loaded: date = meta["loaded_at"].date()
    identity_review = _months_after(loaded, SNAPSHOT_REVIEW_MONTHS)
    fye = row["financial_year_end"]
    # The CSV's year end is the last *reported* period, so its own filing
    # deadline (ten months, like England and Wales) is usually already past.
    # The figures are still CCNI's current ones — the honest review date is
    # the next filing deadline after the snapshot, when they should change.
    finance_review = identity_review
    if fye:
        deadline = _months_after(fye, EW_FILING_MONTHS)
        while deadline is not None and deadline <= loaded:
            deadline = _months_after(deadline, 12)
        if deadline is not None and identity_review is not None:
            finance_review = min(deadline, identity_review)

    facts: list[RegisterFact] = []

    def add(kind: str, value, **kw) -> None:
        if value is not None:
            facts.append(RegisterFact(kind=kind, value=value, **kw))

    add("registered_name", row["name"], as_of=loaded, review_on=identity_review)
    # The NIC prefix is how the number is written everywhere it is asked for.
    add("charity_number", f"NIC{number}", as_of=loaded, review_on=identity_review)
    add("registration_status", row["status"], as_of=loaded, review_on=identity_review)
    add("date_registered", row["date_registered"], review_on=identity_review)
    add("registered_office", row["address"], as_of=loaded, review_on=identity_review)
    add("company_number", row["company_number"], as_of=loaded, review_on=identity_review)
    add("charitable_objects", row["charitable_purposes"], as_of=loaded, review_on=identity_review)
    add("activities", row["what_it_does"], as_of=loaded, review_on=identity_review)
    add("beneficiary_groups", row["who_it_helps"], as_of=loaded, review_on=identity_review)
    income = row["total_income"]
    spending = row["total_spending"]
    add(
        "annual_income",
        float(income) if income is not None else None,
        as_of=fye or loaded,
        review_on=finance_review,
    )
    add(
        "annual_expenditure",
        float(spending) if spending is not None else None,
        as_of=fye or loaded,
        review_on=finance_review,
    )
    for name in row["trustees"]:
        facts.append(
            RegisterFact(kind="trustee", subject=name, value={}, review_on=identity_review)
        )

    status = row["status"]
    return RegisterFacts(
        register="ccni",
        source_url=CCNI_PUBLIC.format(n=number),
        registration_status=status,
        active=status.lower() in ACTIVE_CHARITY_STATUSES,
        facts=facts,
    )


async def _main() -> None:
    import httpx

    from app.config import get_settings

    src = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_EXPORT_URL
    if src.startswith("http"):
        print(f"Downloading {src} …")
        async with httpx.AsyncClient(timeout=180.0, follow_redirects=True) as client:
            resp = await client.get(src)
            resp.raise_for_status()
            text = resp.text
    else:
        from pathlib import Path

        text = await asyncio.to_thread(Path(src).read_text, encoding="utf-8-sig")

    rows = parse_snapshot_csv(text)
    conn = await asyncpg.connect(get_settings().database_url)
    try:
        count = await load_snapshot(conn, rows, source=src)
    finally:
        await conn.close()
    print(f"Loaded {count} Northern Ireland charities into the snapshot")


if __name__ == "__main__":
    asyncio.run(_main())
