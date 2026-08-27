"""Workspace-archive assembly — offline: no SQL, no boto3, no network."""

import json
import zipfile
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from worker.export_data import (
    ArchiveFile,
    assemble_archive,
    build_csvs,
    classify_generated,
    document_filename,
    slug,
)
from worker.workspace_export import build_file_list

TENANT = "11111111-2222-3333-4444-555555555555"
GENERATED_AT = datetime(2026, 8, 27, 18, 0, tzinfo=UTC)


def test_document_filenames_are_readable_and_unique():
    name = document_filename("Annual Accounts 2024/25 (final)", "1a2b3c4d-rest", "t/doc.pdf")
    assert name == "annual-accounts-2024-25-final-1a2b3c4d.pdf"
    assert document_filename("", "deadbeef", "t/x.docx") == "document-deadbeef.docx"
    assert slug("!!!") == "item"


def test_generated_classification_respects_privacy_and_skips_archives():
    shared_conv = str(uuid4())
    private_conv = str(uuid4())
    keys = [
        f"{TENANT}/projects/p1/drafts/j1.docx",
        f"{TENANT}/community/exports/j2.pdf",
        f"{TENANT}/brand/logo.png",
        f"{TENANT}/conversations/{shared_conv}/answers/m1.pdf",
        # Another member's private chat: its PDF must not ride along.
        f"{TENANT}/conversations/{private_conv}/answers/m2.pdf",
        # A previous archive must not nest inside the new one.
        f"{TENANT}/exports/old-job.zip",
        # A vault upload is archived under documents/, not generated/.
        f"{TENANT}/vaultdoc.pdf",
    ]
    files = classify_generated(TENANT, keys, {f"{TENANT}/vaultdoc.pdf"}, {shared_conv})
    arcnames = {f.arcname for f in files}
    assert f"generated/conversations/{shared_conv}/answers/m1.pdf" in arcnames
    assert not any(private_conv in a for a in arcnames)
    # The top-level exports/ prefix (previous archives) is excluded; the
    # community module's own exports/ segment is an artefact and stays.
    assert not any("old-job" in a for a in arcnames)
    assert "generated/community/exports/j2.pdf" in arcnames
    assert not any("vaultdoc" in a for a in arcnames)
    assert "generated/projects/p1/drafts/j1.docx" in arcnames
    assert "generated/brand/logo.png" in arcnames


def test_build_file_list_names_vault_files_from_titles():
    documents = [
        {
            "id": "aaaabbbb-1111",
            "title": "Insurance Certificate",
            "storage_key": f"{TENANT}/d1.pdf",
        },
        {"id": "ccccdddd-2222", "title": "App-created note", "storage_key": None},
    ]
    files = build_file_list(TENANT, documents, [f"{TENANT}/d1.pdf"], set())
    assert [f.arcname for f in files] == ["documents/insurance-certificate-aaaabbbb.pdf"]


def test_csvs_cover_the_promised_registers():
    data = {
        "claims": [
            {
                "kind": "annual_income",
                "subject": None,
                "period": "2024/25",
                "statement": "The organisation's annual income was £412,000.",
                "value": "412000",
                "unit": "GBP",
                "as_of": None,
                "status": "confirmed",
                "source": "register",
                "last_verified": None,
                "next_review": None,
            }
        ],
        "contacts": [
            {
                "name": "Sarah Meadows",
                "company_name": "Brightside",
                "job_title": None,
                "email": "sarah@x.example",
                "phone": None,
                "mobile": None,
                "address": None,
                "tags": ["planner", "consultant"],
                "notes": None,
            }
        ],
        "community": {
            "assets": [
                {
                    "category": "education",
                    "name": "Sanday Community School",
                    "subcategory": None,
                    "status": "open",
                    "settlement": None,
                    "attributes": '{"pupils": 68, "nursery": true}',
                    "contact": None,
                    "url": None,
                    "notes": None,
                }
            ],
            "statistics": [],
        },
        "grants": {"grant_applications": []},
    }
    csvs = build_csvs(data)
    assert set(csvs) == {"claims.csv", "contacts.csv", "community-assets.csv"}
    assert "annual_income,,2024/25" in csvs["claims.csv"]
    assert "planner; consultant" in csvs["contacts.csv"]
    # jsonb attributes decode into a readable cell, booleans included.
    assert "pupils: 68 · nursery: True" in csvs["community-assets.csv"]


def test_archive_assembles_and_records_failures(tmp_path: Path):
    data = {
        "workspace": {"name": "Struvers2", "created_at": GENERATED_AT},
        "claims": [{"kind": "x", "value": Decimal("12.5"), "id": uuid4()}],
        "conversations": [],
    }
    files = [
        ArchiveFile(key=f"{TENANT}/d1.pdf", arcname="documents/insurance-aaaabbbb.pdf"),
        ArchiveFile(key=f"{TENANT}/gone.pdf", arcname="generated/gone.pdf"),
    ]

    def fetch(key: str, dest: str) -> None:
        if "gone" in key:
            raise RuntimeError("NoSuchKey")
        Path(dest).write_bytes(b"%PDF-fake")

    zip_path, manifest = assemble_archive(
        tmp_path, "Struvers2", "clive@example.com", GENERATED_AT, data, files, fetch
    )

    with zipfile.ZipFile(zip_path) as zf:
        names = set(zf.namelist())
        assert {
            "README.md",
            "manifest.json",
            "data/workspace.json",
            "data/claims.json",
            "data/conversations.json",
            "documents/insurance-aaaabbbb.pdf",
        } <= names
        assert "generated/gone.pdf" not in names

        # UUID/Decimal/datetime all serialize; nothing raises.
        claims = json.loads(zf.read("data/claims.json"))
        assert claims[0]["value"] == 12.5

        recorded = json.loads(zf.read("manifest.json"))
        assert recorded["skipped"] == [
            {"arcname": "generated/gone.pdf", "key": f"{TENANT}/gone.pdf", "reason": "NoSuchKey"}
        ]
        assert recorded["counts"]["files"] == 2

        readme = zf.read("README.md").decode()
        assert "Struvers2 — workspace export" in readme
        assert "generated/gone.pdf (NoSuchKey)" in readme
        assert "Private conversations belonging to other members" in readme
