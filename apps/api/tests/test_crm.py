"""CRM module: feature flag, contact/company CRUD, filters, email dedupe,
project links, cross-tenant direct-object-reference attacks, and chat
contact-book lookup (prompt injection of matching records).

SQL-level RLS for the crm_* tables is covered by test_isolation.py
(TENANT_TABLES); this file exercises the API surface.
"""

from uuid import uuid4

import pytest

from app.db import db
from app.litellm import StreamResult, litellm_client
from tests.conftest import Tenant, auth, seed_tenant


async def enable_contacts(tenant: Tenant) -> None:
    async with db.tenant_tx(tenant.owner_id, tenant.id) as conn:
        await conn.execute(
            """update tenants set features = features || '{"contacts": true}' where id = $1""",
            tenant.id,
        )


# -- feature flag ------------------------------------------------------------


async def test_flag_off_hides_module(client):
    t = await seed_tenant(client, f"crmoff-{uuid4().hex[:6]}")
    headers = auth(t.owner_id, t.id)
    assert (await client.get("/api/v1/contacts", headers=headers)).status_code == 404
    assert (await client.get("/api/v1/companies", headers=headers)).status_code == 404
    resp = await client.post("/api/v1/contacts", json={"name": "X"}, headers=headers)
    assert resp.status_code == 404


# -- contacts CRUD -----------------------------------------------------------


async def test_contact_crud(client):
    t = await seed_tenant(client, f"crm-{uuid4().hex[:6]}")
    await enable_contacts(t)
    headers = auth(t.owner_id, t.id)

    resp = await client.post(
        "/api/v1/contacts",
        json={
            "name": "Sarah Meadows",
            "email": "sarah@acme.example",
            "phone": "0113 555 0100",
            "mobile": "07700 900123",
            "job_title": "Planning consultant",
            "tags": ["consultant", "planning"],
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    contact = resp.json()
    assert contact["name"] == "Sarah Meadows"
    assert contact["tags"] == ["consultant", "planning"]
    assert contact["company_name"] is None
    assert contact["project_ids"] == []

    cid = contact["id"]
    resp = await client.patch(
        f"/api/v1/contacts/{cid}", json={"job_title": "Director"}, headers=headers
    )
    assert resp.status_code == 200
    assert resp.json()["job_title"] == "Director"

    resp = await client.get(f"/api/v1/contacts/{cid}", headers=headers)
    assert resp.status_code == 200

    # Empty patch is rejected.
    resp = await client.patch(f"/api/v1/contacts/{cid}", json={}, headers=headers)
    assert resp.status_code == 400

    resp = await client.delete(f"/api/v1/contacts/{cid}", headers=headers)
    assert resp.status_code == 204
    resp = await client.get(f"/api/v1/contacts/{cid}", headers=headers)
    assert resp.status_code == 404


async def test_duplicate_email_rejected(client):
    t = await seed_tenant(client, f"crmdup-{uuid4().hex[:6]}")
    await enable_contacts(t)
    headers = auth(t.owner_id, t.id)

    body = {"name": "A", "email": "dup@example.com"}
    assert (await client.post("/api/v1/contacts", json=body, headers=headers)).status_code == 201
    resp = await client.post(
        "/api/v1/contacts", json={"name": "B", "email": "DUP@example.com"}, headers=headers
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "duplicate_email"


# -- companies ---------------------------------------------------------------


async def test_company_crud_and_contact_link(client):
    t = await seed_tenant(client, f"crmco-{uuid4().hex[:6]}")
    await enable_contacts(t)
    headers = auth(t.owner_id, t.id)

    resp = await client.post(
        "/api/v1/companies",
        json={"name": "Acme Homes", "city": "Leeds", "postcode": "LS1 4AB"},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    company = resp.json()
    assert company["contact_count"] == 0

    resp = await client.post(
        "/api/v1/contacts",
        json={"name": "Jo Field", "company_id": company["id"]},
        headers=headers,
    )
    assert resp.status_code == 201
    assert resp.json()["company_name"] == "Acme Homes"

    resp = await client.get(f"/api/v1/companies/{company['id']}", headers=headers)
    assert resp.json()["contact_count"] == 1

    # Deleting the company detaches, not deletes, its contacts.
    contacts = (await client.get("/api/v1/contacts?q=Jo Field", headers=headers)).json()
    contact_id = contacts[0]["id"]
    resp = await client.delete(f"/api/v1/companies/{company['id']}", headers=headers)
    assert resp.status_code == 204
    resp = await client.get(f"/api/v1/contacts/{contact_id}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["company_id"] is None


# -- filters -----------------------------------------------------------------


async def test_list_filters(client):
    t = await seed_tenant(client, f"crmfil-{uuid4().hex[:6]}")
    await enable_contacts(t)
    headers = auth(t.owner_id, t.id)

    co = (
        await client.post("/api/v1/companies", json={"name": "Brightside"}, headers=headers)
    ).json()
    await client.post(
        "/api/v1/contacts",
        json={"name": "Amy Archer", "company_id": co["id"], "tags": ["supplier"]},
        headers=headers,
    )
    await client.post(
        "/api/v1/contacts",
        json={"name": "Ben Brook", "email": "ben@brook.example"},
        headers=headers,
    )

    names = lambda resp: [c["name"] for c in resp.json()]  # noqa: E731

    resp = await client.get("/api/v1/contacts?q=archer", headers=headers)
    assert names(resp) == ["Amy Archer"]
    resp = await client.get("/api/v1/contacts?q=brightside", headers=headers)
    assert names(resp) == ["Amy Archer"]  # matches via company name
    resp = await client.get("/api/v1/contacts?tag=supplier", headers=headers)
    assert names(resp) == ["Amy Archer"]
    resp = await client.get(f"/api/v1/contacts?company_id={co['id']}", headers=headers)
    assert names(resp) == ["Amy Archer"]
    # The conftest-seeded contact is linked to the seeded project.
    resp = await client.get(f"/api/v1/contacts?project_id={t.project_id}", headers=headers)
    assert [c["id"] for c in resp.json()] == [str(t.contact_id)]


async def test_list_limit_is_opt_in(client):
    t = await seed_tenant(client, f"crmlim-{uuid4().hex[:6]}")
    await enable_contacts(t)
    headers = auth(t.owner_id, t.id)
    for name in ("Ann Adams", "Bob Barr", "Cal Crane"):
        await client.post("/api/v1/contacts", json={"name": name}, headers=headers)

    assert len((await client.get("/api/v1/contacts?limit=2", headers=headers)).json()) == 2
    # Unbounded by default: the address book would otherwise hide contacts.
    everyone = (await client.get("/api/v1/contacts", headers=headers)).json()
    assert len(everyone) >= 3
    assert (await client.get("/api/v1/contacts?limit=0", headers=headers)).status_code == 422


async def test_search_treats_like_wildcards_literally(client):
    t = await seed_tenant(client, f"crmwild-{uuid4().hex[:6]}")
    await enable_contacts(t)
    headers = auth(t.owner_id, t.id)

    await client.post("/api/v1/companies", json={"name": "100% Homes"}, headers=headers)
    for name in ("Jo_Field", "JoXField"):
        await client.post("/api/v1/contacts", json={"name": name}, headers=headers)

    # `_` is a single-character wildcard unless escaped.
    resp = await client.get("/api/v1/contacts?q=jo_field", headers=headers)
    assert [c["name"] for c in resp.json()] == ["Jo_Field"]
    # `%` would otherwise match every row in the tenant.
    resp = await client.get("/api/v1/companies?q=%25", headers=headers)
    assert [c["name"] for c in resp.json()] == ["100% Homes"]


# -- project links -----------------------------------------------------------


async def test_project_link_unlink(client):
    t = await seed_tenant(client, f"crmlink-{uuid4().hex[:6]}")
    await enable_contacts(t)
    headers = auth(t.owner_id, t.id)

    c = (await client.post("/api/v1/contacts", json={"name": "Pat Lane"}, headers=headers)).json()

    resp = await client.post(f"/api/v1/contacts/{c['id']}/projects/{t.project_id}", headers=headers)
    assert resp.status_code == 201
    # Idempotent: linking twice is not an error.
    resp = await client.post(f"/api/v1/contacts/{c['id']}/projects/{t.project_id}", headers=headers)
    assert resp.status_code == 201

    resp = await client.get(f"/api/v1/contacts/{c['id']}", headers=headers)
    assert resp.json()["project_ids"] == [str(t.project_id)]

    resp = await client.get(f"/api/v1/contacts?project_id={t.project_id}", headers=headers)
    assert "Pat Lane" in [x["name"] for x in resp.json()]

    resp = await client.delete(
        f"/api/v1/contacts/{c['id']}/projects/{t.project_id}", headers=headers
    )
    assert resp.status_code == 204
    resp = await client.get(f"/api/v1/contacts/{c['id']}", headers=headers)
    assert resp.json()["project_ids"] == []


# -- cross-tenant DOR --------------------------------------------------------


async def test_cross_tenant_object_references_404(client):
    a = await seed_tenant(client, f"crma-{uuid4().hex[:6]}")
    b = await seed_tenant(client, f"crmb-{uuid4().hex[:6]}")
    await enable_contacts(a)
    await enable_contacts(b)
    headers = auth(a.owner_id, a.id)

    # B's ids under A's valid context must 404 on every verb.
    for method, path in [
        ("GET", f"/api/v1/contacts/{b.contact_id}"),
        ("PATCH", f"/api/v1/contacts/{b.contact_id}"),
        ("DELETE", f"/api/v1/contacts/{b.contact_id}"),
        ("GET", f"/api/v1/companies/{b.company_id}"),
        ("DELETE", f"/api/v1/companies/{b.company_id}"),
        ("POST", f"/api/v1/contacts/{b.contact_id}/projects/{a.project_id}"),
    ]:
        resp = await client.request(
            method, path, headers=headers, json={"name": "x"} if method == "PATCH" else None
        )
        assert resp.status_code == 404, f"{method} {path} -> {resp.status_code}"

    # A cannot attach B's company or B's project to A's own contact.
    resp = await client.post(
        "/api/v1/contacts",
        json={"name": "Smuggle", "company_id": str(b.company_id)},
        headers=headers,
    )
    assert resp.status_code == 404
    resp = await client.post(
        f"/api/v1/contacts/{a.contact_id}/projects/{b.project_id}", headers=headers
    )
    assert resp.status_code == 404

    # Listings never include B's rows.
    contacts = (await client.get("/api/v1/contacts", headers=headers)).json()
    assert str(b.contact_id) not in {c["id"] for c in contacts}
    companies = (await client.get("/api/v1/companies", headers=headers)).json()
    assert str(b.company_id) not in {c["id"] for c in companies}


# -- audit -------------------------------------------------------------------


async def test_mutations_are_audited(client):
    t = await seed_tenant(client, f"crmaud-{uuid4().hex[:6]}")
    await enable_contacts(t)
    headers = auth(t.owner_id, t.id)

    c = (await client.post("/api/v1/contacts", json={"name": "Log Me"}, headers=headers)).json()
    await client.patch(f"/api/v1/contacts/{c['id']}", json={"notes": "hi"}, headers=headers)
    await client.delete(f"/api/v1/contacts/{c['id']}", headers=headers)

    async with db.tenant_tx(t.owner_id, t.id) as conn:
        actions = {
            r["action"]
            for r in await conn.fetch("select action from audit_log where target_id = $1", c["id"])
        }
    assert {"crm.contact_create", "crm.contact_update", "crm.contact_delete"} <= actions


# -- chat lookup -------------------------------------------------------------


@pytest.fixture
def capture_llm(monkeypatch):
    """Stub stream_chat, recording the system prompt of each call."""
    prompts: list[str] = []

    async def _fake(virtual_key, alias, messages, result: StreamResult):
        prompts.append(messages[0]["content"])
        result.text_parts.append("ok")
        yield "ok"
        result.tokens_in = 10
        result.tokens_out = 5

    monkeypatch.setattr(litellm_client, "stream_chat", _fake)
    return prompts


async def _chat_ready_tenant(client, name: str, contacts: bool = True) -> Tenant:
    t = await seed_tenant(client, name)
    if contacts:
        await enable_contacts(t)
    async with db.tenant_tx(t.owner_id, t.id) as conn:
        await conn.execute(
            "update tenants set litellm_key_encrypted = 'sk-test-virtual' where id = $1", t.id
        )
    return t


async def _say(client, tenant: Tenant, content: str) -> None:
    headers = auth(tenant.owner_id, tenant.id)
    conv = (await client.post("/api/v1/conversations", json={"title": "t"}, headers=headers)).json()
    resp = await client.post(
        f"/api/v1/conversations/{conv['id']}/messages",
        json={"content": content, "use_vault": False},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text


async def test_chat_injects_matching_contact(client, capture_llm):
    t = await _chat_ready_tenant(client, f"crmchat-{uuid4().hex[:6]}")
    headers = auth(t.owner_id, t.id)
    await client.post(
        "/api/v1/contacts",
        json={"name": "Sarah Meadows", "phone": "0113 555 0100", "job_title": "Planner"},
        headers=headers,
    )

    await _say(client, t, "What is Sarah's phone number?")
    system = capture_llm[-1]
    assert "<contact-records>" in system
    assert "Sarah Meadows" in system
    assert "0113 555 0100" in system

    # No name mentioned → no injection.
    await _say(client, t, "Summarise our leave policy")
    assert "<contact-records>" not in capture_llm[-1]


async def test_chat_injects_matching_company(client, capture_llm):
    t = await _chat_ready_tenant(client, f"crmchatco-{uuid4().hex[:6]}")
    headers = auth(t.owner_id, t.id)
    await client.post(
        "/api/v1/companies",
        json={"name": "Brightside Builders", "phone": "0161 555 0199", "city": "Leeds"},
        headers=headers,
    )

    await _say(client, t, "Do we have an address for Brightside?")
    system = capture_llm[-1]
    assert "Brightside Builders (company)" in system
    assert "0161 555 0199" in system


async def test_chat_lookup_matches_whole_words_only(client, capture_llm):
    """A bystander's private details must not ride along on a substring hit."""
    t = await _chat_ready_tenant(client, f"crmchatsub-{uuid4().hex[:6]}")
    headers = auth(t.owner_id, t.id)
    await client.post(
        "/api/v1/contacts",
        json={"name": "Samantha Fry", "mobile": "07700 900999", "address": "3 Cedar Rise"},
        headers=headers,
    )
    await client.post(
        "/api/v1/contacts",
        json={"name": "Ravi Shah", "email": "ravi@brightside.example"},
        headers=headers,
    )

    await _say(client, t, "can you summarise the SAM report for me?")
    assert "Samantha Fry" not in capture_llm[-1]

    # A domain token must not drag in everyone who shares the domain.
    await _say(client, t, "what does brightside.example cover?")
    assert "Ravi Shah" not in capture_llm[-1]

    # The real mention still matches, by name and by email local part.
    await _say(client, t, "What is Samantha's mobile?")
    assert "07700 900999" in capture_llm[-1]
    await _say(client, t, "Did ravi reply?")
    assert "ravi@brightside.example" in capture_llm[-1]


async def test_chat_lookup_respects_feature_flag(client, capture_llm):
    t = await _chat_ready_tenant(client, f"crmchatoff-{uuid4().hex[:6]}", contacts=False)
    # The seeded contact would match by name, but the flag is off.
    await _say(client, t, "What is the contact's email for our crmchatoff project?")
    assert "<contact-records>" not in capture_llm[-1]


# -- CSV import --------------------------------------------------------------


async def test_csv_import_creates_updates_and_skips(client):
    t = await seed_tenant(client, f"crmimp-{uuid4().hex[:6]}")
    await enable_contacts(t)
    headers = auth(t.owner_id, t.id)

    csv_text = (
        "Name,Email,Phone,Job Title,Company,Tags\n"
        "Sarah Meadows,sarah@acme.example,0113 555 0100,Planner,Acme Homes,planning;consultant\n"
        "Jo Field,jo@acme.example,,Surveyor,Acme Homes,\n"
        ",missing@name.example,,,,\n"
    )
    resp = await client.post("/api/v1/contacts/import", json={"csv": csv_text}, headers=headers)
    assert resp.status_code == 200, resp.text
    out = resp.json()
    assert out["created"] == 2
    assert out["updated"] == 0
    assert out["skipped"] == 1
    assert out["companies_created"] == 1  # Acme Homes reused across both rows
    assert out["errors"] == [{"line": 4, "reason": "no name"}]

    contacts = (await client.get("/api/v1/contacts", headers=headers)).json()
    sarah = next(c for c in contacts if c["name"] == "Sarah Meadows")
    assert sarah["company_name"] == "Acme Homes"
    assert sarah["tags"] == ["planning", "consultant"]

    # Re-import with the same email: updates in place (case-insensitive),
    # blanks never erase, tags merge, existing company matched not duplicated.
    csv_text = (
        "name,email,mobile,company,tags\n"
        "Sarah B Meadows,SARAH@ACME.EXAMPLE,07700 900123,acme homes,vip\n"
    )
    resp = await client.post("/api/v1/contacts/import", json={"csv": csv_text}, headers=headers)
    out = resp.json()
    assert (out["created"], out["updated"], out["companies_created"]) == (0, 1, 0)

    sarah = (await client.get("/api/v1/contacts?q=Meadows", headers=headers)).json()[0]
    assert sarah["name"] == "Sarah B Meadows"
    assert sarah["phone"] == "0113 555 0100"  # untouched
    assert sarah["mobile"] == "07700 900123"
    assert set(sarah["tags"]) == {"planning", "consultant", "vip"}


async def test_csv_import_first_last_name_columns(client):
    t = await seed_tenant(client, f"crmimpfl-{uuid4().hex[:6]}")
    await enable_contacts(t)
    headers = auth(t.owner_id, t.id)

    csv_text = "First Name,Last Name,Email\nPat,Lane,pat@lane.example\n"
    resp = await client.post("/api/v1/contacts/import", json={"csv": csv_text}, headers=headers)
    assert resp.json()["created"] == 1
    contacts = (await client.get("/api/v1/contacts?q=pat", headers=headers)).json()
    assert contacts[0]["name"] == "Pat Lane"


async def test_csv_import_keeps_rows_editable(client):
    """Imported values must satisfy the limits the editor endpoints enforce."""
    t = await seed_tenant(client, f"crmimpval-{uuid4().hex[:6]}")
    await enable_contacts(t)
    headers = auth(t.owner_id, t.id)

    csv_text = (
        "Name,Email,Job Title,Phone\n"
        "Placeholder Pat,n/a,Surveyor,0113 555 0100\n"
        f"Long Title Lou,lou@acme.example,{'x' * 400},{'9' * 80}\n"
    )
    resp = await client.post("/api/v1/contacts/import", json={"csv": csv_text}, headers=headers)
    assert resp.status_code == 200, resp.text
    out = resp.json()
    assert (out["created"], out["skipped"]) == (1, 1)
    assert out["errors"] == [{"line": 2, "reason": "invalid email: n/a"}]

    lou = (await client.get("/api/v1/contacts?q=Lou", headers=headers)).json()[0]
    assert len(lou["job_title"]) == 200
    assert len(lou["phone"]) == 50

    # The round trip the import previously made impossible.
    resp = await client.patch(
        f"/api/v1/contacts/{lou['id']}", json={"notes": "called back"}, headers=headers
    )
    assert resp.status_code == 200, resp.text


@pytest.mark.parametrize(
    ("path", "body"),
    [
        ("contacts", {"name": None}),
        ("contacts", {"tags": None}),
        ("companies", {"name": None}),
    ],
)
async def test_patch_explicit_null_on_not_null_column_is_422(client, path, body):
    t = await seed_tenant(client, f"crmnull-{uuid4().hex[:6]}")
    await enable_contacts(t)
    headers = auth(t.owner_id, t.id)
    created = await client.post(f"/api/v1/{path}", json={"name": "Nullable Nell"}, headers=headers)
    assert created.status_code == 201, created.text

    resp = await client.patch(f"/api/v1/{path}/{created.json()['id']}", json=body, headers=headers)
    assert resp.status_code == 422, resp.text
    assert resp.json()["error"]["code"] == "validation_error"


async def test_csv_import_flag_off_404(client):
    t = await seed_tenant(client, f"crmimpoff-{uuid4().hex[:6]}")
    resp = await client.post(
        "/api/v1/contacts/import", json={"csv": "name\nX\n"}, headers=auth(t.owner_id, t.id)
    )
    assert resp.status_code == 404
