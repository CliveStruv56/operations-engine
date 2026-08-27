"""Workspace archive assembly: rows and files in, one ZIP out.

Deliberately pure — no SQL, no boto3. The job (`workspace_export.py`)
gathers rows under RLS and hands this module plain dicts plus a
`fetch_object(key, dest)` callable, so every decision about what the
archive contains is testable offline.

Two rules the whole feature leans on:

**No silent truncation.** An object that cannot be fetched is recorded in
`manifest.json` and the README and skipped — a backup that dies at file
400 of 401 helps nobody, and one that quietly omits a file is worse.

**Standard formats.** JSON is the complete machine-readable record; the
registers a person would open in a spreadsheet ship as CSV too, which is
what the security page has promised since launch.
"""

import csv
import io
import json
import re
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID

ZIP_NAME = "archive.zip"


def json_default(value: Any) -> Any:
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return str(value)


def loads_maybe(value: Any) -> Any:
    """asyncpg returns jsonb as str — decode at the edge, tolerate anything."""
    if isinstance(value, str):
        try:
            return json.loads(value)
        except ValueError:
            return value
    return value


def slug(text: str, fallback: str = "item") -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return cleaned[:60] or fallback


def document_filename(title: str, doc_id: str, storage_key: str) -> str:
    """ "annual-accounts-2024-1a2b3c4d.pdf" — readable, unique, extension kept."""
    ext = Path(storage_key).suffix.lstrip(".") or "bin"
    return f"{slug(title, 'document')}-{doc_id[:8]}.{ext}"


@dataclass(frozen=True)
class ArchiveFile:
    key: str  # storage key to fetch
    arcname: str  # path inside the zip


def classify_generated(
    tenant_id: str,
    keys: list[str],
    vault_keys: set[str],
    included_conversation_ids: set[str],
) -> list[ArchiveFile]:
    """Everything under the tenant prefix that belongs in `generated/`.

    Vault uploads are archived separately under readable names; previous
    export archives must not nest; and a conversation artefact (answer PDF)
    is chat content, so it ships only when its conversation does — the
    private-chat rule holds for files exactly as it does for transcripts.
    """
    prefix = f"{tenant_id}/"
    conversations_prefix = f"{tenant_id}/conversations/"
    exports_prefix = f"{tenant_id}/exports/"
    out: list[ArchiveFile] = []
    for key in keys:
        if not key.startswith(prefix) or key in vault_keys or key.startswith(exports_prefix):
            continue
        if key.startswith(conversations_prefix):
            conversation_id = key[len(conversations_prefix) :].split("/", 1)[0]
            if conversation_id not in included_conversation_ids:
                continue
        out.append(ArchiveFile(key=key, arcname=f"generated/{key[len(prefix) :]}"))
    return out


def _cell(value: Any) -> str:
    value = loads_maybe(value)
    if value is None:
        return ""
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, list):
        return "; ".join(str(v) for v in value)
    if isinstance(value, dict):
        return " · ".join(f"{k}: {v}" for k, v in value.items())
    if isinstance(value, datetime | date):
        return value.isoformat()
    return str(value)


def _csv_text(headers: list[str], rows: list[list[Any]]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\r\n")
    writer.writerow(headers)
    for row in rows:
        writer.writerow([_cell(v) for v in row])
    return buffer.getvalue()


def _pick(rows: list[dict], columns: list[str]) -> list[list[Any]]:
    return [[r.get(c) for c in columns] for r in rows]


def build_csvs(data: dict[str, Any]) -> dict[str, str]:
    """The registers a person opens in a spreadsheet, one CSV each."""
    community = data.get("community", {})
    sheets = {
        "claims.csv": (
            [
                "kind",
                "subject",
                "period",
                "statement",
                "value",
                "unit",
                "as_of",
                "status",
                "source",
                "last_verified",
                "next_review",
            ],
            data.get("claims", []),
        ),
        "contacts.csv": (
            [
                "name",
                "company_name",
                "job_title",
                "email",
                "phone",
                "mobile",
                "address",
                "tags",
                "notes",
            ],
            data.get("contacts", []),
        ),
        "companies.csv": (
            [
                "name",
                "website",
                "email",
                "phone",
                "address_line1",
                "address_line2",
                "city",
                "postcode",
                "notes",
            ],
            data.get("companies", []),
        ),
        "community-assets.csv": (
            [
                "category",
                "name",
                "subcategory",
                "status",
                "settlement",
                "attributes",
                "contact",
                "url",
                "notes",
            ],
            community.get("assets", []),
        ),
        "community-figures.csv": (
            ["label", "value", "unit", "period", "as_of", "source", "source_url", "notes"],
            community.get("statistics", []),
        ),
        "projects.csv": (
            ["name", "description", "archived", "created_at"],
            data.get("projects", []),
        ),
        "grant-applications.csv": (
            [
                "title",
                "funder_name",
                "reference",
                "amount_requested",
                "amount_awarded",
                "deadline",
                "start_date",
                "end_date",
            ],
            data.get("grants", {}).get("grant_applications", []),
        ),
    }
    return {
        name: _csv_text(headers, _pick(rows, headers))
        for name, (headers, rows) in sheets.items()
        if rows
    }


def build_readme(
    workspace_name: str,
    exported_by: str,
    generated_at: datetime,
    counts: dict[str, int],
    skipped: list[dict],
) -> str:
    lines = [
        f"# {workspace_name} — workspace export",
        "",
        f"Generated {generated_at.strftime('%d %B %Y %H:%M')} UTC by {exported_by}.",
        "",
        "## What is in this archive",
        "",
        "- `data/` — every record in the workspace as JSON, the complete",
        "  machine-readable copy: documents, conversations, the claims register",
        "  and its history, contacts, projects, grants, the community profile,",
        "  question sets and the audit trail.",
        "- `csv/` — the registers as spreadsheets (claims, contacts, community",
        "  figures and more), for anyone who works in Excel.",
        "- `documents/` — every file in the vault, under readable names.",
        "- `generated/` — everything Flowgrid produced for you: drafted",
        "  documents, health cards, impact cards and exported PDFs.",
        "- `manifest.json` — a machine-readable list of every file here.",
        "",
        "Private conversations belonging to other members are not included —",
        "only shared conversations and the exporter's own. That matches how",
        "the workspace itself behaves.",
        "",
        "## Counts",
        "",
    ]
    lines += [f"- {area}: {n}" for area, n in sorted(counts.items())]
    if skipped:
        lines += [
            "",
            "## Files that could not be fetched",
            "",
            "These objects were listed but did not download; everything else in",
            "the archive is complete. Re-run the export to retry them.",
            "",
        ]
        lines += [f"- {s['arcname']} ({s['reason']})" for s in skipped]
    lines += ["", "Prepared with Flowgrid.", ""]
    return "\n".join(lines)


def _count(value: Any) -> int:
    if isinstance(value, list):
        return len(value)
    if isinstance(value, dict):
        return sum(_count(v) for v in value.values())
    return 1 if value is not None else 0


def assemble_archive(
    dest_dir: Path,
    workspace_name: str,
    exported_by: str,
    generated_at: datetime,
    data: dict[str, Any],
    files: list[ArchiveFile],
    fetch_object: Callable[[str, str], None],
) -> tuple[Path, dict]:
    """Write the ZIP under `dest_dir`; returns (zip_path, manifest)."""
    zip_path = dest_dir / ZIP_NAME
    manifest_files: list[dict] = []
    skipped: list[dict] = []
    counts = {area: _count(value) for area, value in data.items()}
    counts["files"] = len(files)

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:

        def put(arcname: str, text: str) -> None:
            zf.writestr(arcname, text)
            manifest_files.append({"path": arcname, "bytes": len(text.encode())})

        for area, value in data.items():
            put(
                f"data/{area.replace('_', '-')}.json",
                json.dumps(value, indent=2, default=json_default),
            )
        for name, text in build_csvs(data).items():
            put(f"csv/{name}", text)

        scratch = dest_dir / "object.tmp"
        for f in files:
            try:
                fetch_object(f.key, str(scratch))
                zf.write(scratch, f.arcname)
                manifest_files.append({"path": f.arcname, "bytes": scratch.stat().st_size})
            except Exception as exc:  # noqa: BLE001 — one bad object must not sink the archive
                skipped.append({"arcname": f.arcname, "key": f.key, "reason": str(exc)[:200]})
            finally:
                scratch.unlink(missing_ok=True)

        put(
            "manifest.json",
            json.dumps(
                {
                    "workspace": workspace_name,
                    "generated_at": generated_at,
                    "exported_by": exported_by,
                    "counts": counts,
                    "files": manifest_files,
                    "skipped": skipped,
                },
                indent=2,
                default=json_default,
            ),
        )
        put("README.md", build_readme(workspace_name, exported_by, generated_at, counts, skipped))

    return zip_path, {"files": manifest_files, "skipped": skipped, "counts": counts}
