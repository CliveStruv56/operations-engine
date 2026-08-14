"""Email transport + the claims sweep (claims brief §14.1 steps 2–3).

Invites report whether their email actually went out; the signed unsubscribe
link flips exactly its own membership's preference and can flip it back; and
the worker's sweep — imported across the monorepo like the other DB-touching
worker modules (ASSUMPTIONS #13) — finds the right tenants, writes one feed
row per window, and picks the right digest recipients.
"""

import sys
from datetime import date, timedelta
from pathlib import Path
from uuid import uuid4

from app.db import db
from app.email import email_client, unsubscribe_token
from tests.conftest import auth, seed_tenant

sys.path.append(str(Path(__file__).resolve().parents[2] / "worker"))

from worker.claims.sweep import (  # noqa: E402
    digest_recipients,
    due_claims,
    record_review_due,
)


async def _confirm_claim(tenant, kind, statement, *, next_review=None, expires_on=None):
    # Distinct kinds per tenant: confirmed rows carry the partial unique
    # index on (tenant_id, kind, subject, period).
    async with db.tenant_tx(tenant.owner_id, tenant.id) as conn:
        await conn.execute(
            """
            insert into claims (tenant_id, kind, statement, status, source,
                                next_review, expires_on, last_verified)
            values ($1, $2, $3, 'confirmed', 'typed', $4, $5, current_date)
            """,
            tenant.id,
            kind,
            statement,
            next_review,
            expires_on,
        )


# -- invite email -------------------------------------------------------------


async def test_invite_reports_email_sent(client, monkeypatch):
    t = await seed_tenant(client, f"mail-{uuid4().hex[:6]}")
    sent: list[tuple[str, str, str]] = []

    async def fake_send(to, subject, text, *, client=None):
        sent.append((to, subject, text))
        return True

    monkeypatch.setattr(email_client, "send", fake_send)
    resp = await client.post(
        "/api/v1/invites",
        json={"email": "new@example.com", "role": "member"},
        headers=auth(t.owner_id, t.id),
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["email_sent"] is True
    to, _subject, text = sent[0]
    assert to == "new@example.com"
    # The email carries the same accept link the UI offers for hand delivery.
    assert body["token"] in text


async def test_invite_survives_email_failure(client, monkeypatch):
    """The invite exists whether or not its notification landed — a dark
    transport downgrades the response to 'copy the link', never a 5xx."""
    t = await seed_tenant(client, f"dark-{uuid4().hex[:6]}")

    async def fake_send(to, subject, text, *, client=None):
        return False

    monkeypatch.setattr(email_client, "send", fake_send)
    resp = await client.post(
        "/api/v1/invites",
        json={"email": "new@example.com", "role": "member"},
        headers=auth(t.owner_id, t.id),
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["email_sent"] is False


# -- unsubscribe link ---------------------------------------------------------


async def test_unsubscribe_link_flips_and_restores(client):
    t = await seed_tenant(client, f"unsub-{uuid4().hex[:6]}")
    token = unsubscribe_token(t.id, t.membership_id)
    query = f"tenant={t.id}&membership={t.membership_id}&token={token}"

    # GET only confirms — mail scanners prefetch links.
    page = await client.get(f"/api/v1/email/digest?{query}")
    assert page.status_code == 200
    assert "Stop the digest" in page.text

    resp = await client.post(f"/api/v1/email/digest?{query}&action=pause")
    assert resp.status_code == 200, resp.text
    members = (await client.get("/api/v1/members", headers=auth(t.owner_id, t.id))).json()
    assert [m["digest_opt_out"] for m in members] == [True]

    # The same link can switch it back on — an accidental click is not forever.
    resp = await client.post(f"/api/v1/email/digest?{query}&action=resume")
    assert resp.status_code == 200, resp.text
    members = (await client.get("/api/v1/members", headers=auth(t.owner_id, t.id))).json()
    assert [m["digest_opt_out"] for m in members] == [False]


async def test_unsubscribe_token_matches_the_worker_signature(client):
    """The worker signs the link, the API verifies it — the two copies of the
    algorithm must stay byte-for-byte in step or every link 400s."""
    from worker.email import unsubscribe_token as worker_token

    t = await seed_tenant(client, f"parity-{uuid4().hex[:6]}")
    assert unsubscribe_token(t.id, t.membership_id) == worker_token(str(t.id), str(t.membership_id))


async def test_unsubscribe_rejects_a_bad_token(client):
    t = await seed_tenant(client, f"badtok-{uuid4().hex[:6]}")
    query = f"tenant={t.id}&membership={t.membership_id}&token={'0' * 64}"
    assert (await client.get(f"/api/v1/email/digest?{query}")).status_code == 400
    assert (await client.post(f"/api/v1/email/digest?{query}&action=pause")).status_code == 400
    members = (await client.get("/api/v1/members", headers=auth(t.owner_id, t.id))).json()
    assert [m["digest_opt_out"] for m in members] == [False]


# -- the sweep ----------------------------------------------------------------


async def _sweep_ids(conn) -> set:
    rows = await conn.fetch("select out_tenant_id from claims_sweep_tenants($1)", date.today())
    return {r["out_tenant_id"] for r in rows}


async def test_sweep_finds_due_tenants_and_writes_one_feed_row(client):
    a = await seed_tenant(client, f"due-{uuid4().hex[:6]}")
    b = await seed_tenant(client, f"fine-{uuid4().hex[:6]}")
    yesterday = date.today() - timedelta(days=1)
    await _confirm_claim(
        a,
        "insurance_public_liability",
        "The organisation's public liability insurance is in place.",
        expires_on=yesterday,
    )
    await _confirm_claim(
        a, "company_number", "The organisation's registered name is A.", next_review=yesterday
    )
    await _confirm_claim(
        b,
        "company_number",
        "The organisation's registered name is B.",
        next_review=date.today() + timedelta(days=30),
    )

    async with db.tenant_tx(a.owner_id, a.id) as conn:
        ids = await _sweep_ids(conn)
    assert a.id in ids
    assert b.id not in ids  # nothing due there

    async with db.tenant_tx(a.owner_id, a.id) as conn:
        due = await due_claims(conn, date.today())
        # Lapsed (now false) sorts before merely past-review.
        assert [c.lapsed for c in due] == [True, False]
        assert await record_review_due(conn, str(a.id), due) is True
        # Second run inside the window: the standing problem must not drown
        # the feed in identical rows.
        assert await record_review_due(conn, str(a.id), due) is False

    feed = (await client.get("/api/v1/activity", headers=auth(a.owner_id, a.id))).json()
    rows = [i for i in feed if i["action"] == "claims.review_due"]
    assert len(rows) == 1
    assert rows[0]["meta"] == {"needs_attention": 2, "lapsed": 1}
    assert rows[0]["actor_email"] is None  # nobody did this; the platform did


async def test_sweep_skips_suspended_tenants(client):
    t = await seed_tenant(client, f"susp-{uuid4().hex[:6]}")
    await _confirm_claim(
        t,
        "company_number",
        "The organisation's registered name is S.",
        next_review=date.today() - timedelta(days=1),
    )
    async with db.tenant_tx(t.owner_id, t.id) as conn:
        await conn.execute("update tenants set suspended_at = now() where id = $1", t.id)
        ids = await _sweep_ids(conn)
    assert t.id not in ids


async def test_digest_recipients_respect_role_and_opt_out(client):
    t = await seed_tenant(client, f"recip-{uuid4().hex[:6]}")
    member_id = uuid4()
    resp = await client.post(
        "/api/v1/invites/accept", json={"token": t.invite_token}, headers=auth(member_id)
    )
    assert resp.status_code == 200

    async with db.tenant_tx(t.owner_id, t.id) as conn:
        recipients = await digest_recipients(conn, str(t.id))
        # The invitee is role=member: badge only, no email interruption.
        assert [r.membership_id for r in recipients] == [str(t.membership_id)]

        await conn.execute(
            "update memberships set digest_opt_out = true where id = $1", t.membership_id
        )
        assert await digest_recipients(conn, str(t.id)) == []
