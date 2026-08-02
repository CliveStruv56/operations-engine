"""CRM module: feature flag, contact/company CRUD, filters, email dedupe,
project links, and cross-tenant direct-object-reference attacks.

SQL-level RLS for the crm_* tables is covered by test_isolation.py
(TENANT_TABLES); this file exercises the API surface.
"""

from uuid import uuid4

from app.db import db
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
