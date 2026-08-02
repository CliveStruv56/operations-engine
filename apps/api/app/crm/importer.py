"""CSV import for the contact book.

Header names are normalised (case/space/underscore-insensitive) and mapped
to contact fields; unknown columns are ignored so exports from other tools
import without editing. Rows dedupe against the per-tenant unique lowercased
email: a matching email updates that contact's supplied fields instead of
failing the unique index. Companies are matched by name (case-insensitive)
and auto-created.
"""

import csv
import io
import re
from dataclasses import dataclass, field
from uuid import UUID

import asyncpg

from app.crm.schemas import (
    ADDRESS_MAX,
    EMAIL,
    EMAIL_MAX,
    JOB_TITLE_MAX,
    NAME_MAX,
    NOTES_MAX,
    PHONE_MAX,
)

MAX_ROWS = 2_000

_EMAIL_RE = re.compile(EMAIL)

# Per-field caps mirroring app.crm.schemas. An imported row must satisfy the
# same limits ContactPatch enforces — a contact the editor refuses to accept
# back can never be saved from the UI again, so it is better to truncate (or
# reject the row outright, for a malformed email) at import time.
_CAPS = {
    "email": EMAIL_MAX,
    "phone": PHONE_MAX,
    "mobile": PHONE_MAX,
    "job_title": JOB_TITLE_MAX,
    "company": NAME_MAX,
    "address": ADDRESS_MAX,
    "notes": NOTES_MAX,
}

# normalised header -> contact field
_HEADERS = {
    "name": "name",
    "fullname": "name",
    "contactname": "name",
    "email": "email",
    "emailaddress": "email",
    "phone": "phone",
    "telephone": "phone",
    "phonenumber": "phone",
    "mobile": "mobile",
    "mobilenumber": "mobile",
    "jobtitle": "job_title",
    "title": "job_title",
    "role": "job_title",
    "company": "company",
    "companyname": "company",
    "organisation": "company",
    "organization": "company",
    "address": "address",
    "notes": "notes",
    "tags": "tags",
}
_NAME_PARTS = {"firstname": 0, "lastname": 1, "surname": 1}


@dataclass
class ParsedRow:
    line: int  # 1-based CSV line for error reporting
    name: str
    email: str | None = None
    phone: str | None = None
    mobile: str | None = None
    job_title: str | None = None
    company: str | None = None
    address: str | None = None
    notes: str | None = None
    tags: list[str] = field(default_factory=list)


@dataclass
class ImportResult:
    created: int = 0
    updated: int = 0
    skipped: int = 0
    companies_created: int = 0
    errors: list[dict] = field(default_factory=list)

    def skip(self, line: int, reason: str) -> None:
        self.skipped += 1
        if len(self.errors) < 20:
            self.errors.append({"line": line, "reason": reason})


def _norm(header: str) -> str:
    return "".join(ch for ch in header.lower() if ch.isalnum())


def parse_csv(text: str, result: ImportResult) -> list[ParsedRow]:
    reader = csv.reader(io.StringIO(text))
    try:
        headers = next(reader)
    except StopIteration:
        return []
    fields: list[str | None] = []
    name_parts: list[tuple[int, int]] = []  # (column, first/last position)
    for i, h in enumerate(headers):
        norm = _norm(h)
        if norm in _NAME_PARTS:
            name_parts.append((i, _NAME_PARTS[norm]))
            fields.append(None)
        else:
            fields.append(_HEADERS.get(norm))
    name_parts.sort(key=lambda p: p[1])

    rows: list[ParsedRow] = []
    for line_no, cells in enumerate(reader, start=2):
        if not any(cell.strip() for cell in cells):
            continue  # blank line, not an error
        values: dict[str, str] = {}
        for i, cell in enumerate(cells):
            key = fields[i] if i < len(fields) else None
            if key and cell.strip():
                values[key] = cell.strip()
        name = values.pop("name", "") or " ".join(
            cells[i].strip() for i, _ in name_parts if i < len(cells) and cells[i].strip()
        )
        if not name:
            result.skip(line_no, "no name")
            continue
        tags = [t.strip() for t in values.pop("tags", "").replace(";", ",").split(",")]
        email = values.get("email")
        if email is not None and not _EMAIL_RE.match(email):
            # Placeholders like "n/a" are common in exports. Storing one would
            # produce a contact the editor can never save; skipping reports the
            # line so the operator can fix the CSV and re-import (email dedupe
            # makes that safe).
            result.skip(line_no, f"invalid email: {email[:60]}")
            continue
        rows.append(
            ParsedRow(
                line=line_no,
                name=name[:NAME_MAX],
                tags=[t for t in tags if t],
                **{k: v[: _CAPS[k]] for k, v in values.items()},
            )
        )
    return rows


async def apply_rows(
    conn: asyncpg.Connection, tenant_id: UUID, user_id: UUID, rows: list[ParsedRow]
) -> ImportResult:
    result = ImportResult()
    company_ids: dict[str, UUID] = {}  # lowercased name -> id (existing + created)
    for r in await conn.fetch("select id, name from crm_companies"):
        company_ids[r["name"].lower()] = r["id"]

    for row in rows:
        company_id: UUID | None = None
        if row.company:
            company_id = company_ids.get(row.company.lower())
            if company_id is None:
                company_id = await conn.fetchval(
                    """
                    insert into crm_companies (tenant_id, name, created_by)
                    values ($1, $2, $3) returning id
                    """,
                    tenant_id,
                    row.company[:NAME_MAX],
                    user_id,
                )
                company_ids[row.company.lower()] = company_id
                result.companies_created += 1

        existing = None
        if row.email:
            existing = await conn.fetchval(
                "select id from crm_contacts where lower(email) = lower($1)", row.email
            )
        if existing:
            # Update only the fields the row supplies; blanks never erase data.
            await conn.execute(
                """
                update crm_contacts set
                    name = $2,
                    job_title = coalesce($3, job_title),
                    phone = coalesce($4, phone),
                    mobile = coalesce($5, mobile),
                    address = coalesce($6, address),
                    notes = coalesce($7, notes),
                    company_id = coalesce($8, company_id),
                    tags = (select array(select distinct t from unnest(tags || $9::text[]) t)),
                    updated_at = now()
                where id = $1
                """,
                existing,
                row.name,
                row.job_title,
                row.phone,
                row.mobile,
                row.address,
                row.notes,
                company_id,
                row.tags,
            )
            result.updated += 1
        else:
            await conn.execute(
                """
                insert into crm_contacts (tenant_id, company_id, name, job_title, email,
                                          phone, mobile, address, notes, tags, created_by)
                values ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                """,
                tenant_id,
                company_id,
                row.name,
                row.job_title,
                row.email,
                row.phone,
                row.mobile,
                row.address,
                row.notes,
                row.tags,
                user_id,
            )
            result.created += 1
    return result
