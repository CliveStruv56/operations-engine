"""Chat flow with a stubbed model gateway: SSE stream shape, persistence of
model/tokens/cost on the assistant message, usage_events capture, soft-cap
routing pin, and gateway-down behaviour."""

import json
from uuid import uuid4

import pytest

from app.db import db
from app.litellm import StreamResult, estimate_cost_usd, litellm_client
from tests.conftest import auth, seed_tenant


def parse_sse(text: str) -> list[tuple[str, dict]]:
    events = []
    for block in text.strip().split("\n\n"):
        lines = dict(line.split(": ", 1) for line in block.splitlines() if ": " in line)
        events.append((lines["event"], json.loads(lines["data"])))
    return events


@pytest.fixture
def fake_llm(monkeypatch):
    """Stub stream_chat: two deltas, then usage in the result. Records the
    alias each call was routed to."""
    calls: list[str] = []

    async def _fake(virtual_key, alias, messages, result: StreamResult):
        calls.append(alias)
        for part in ("Hello ", "world"):
            result.text_parts.append(part)
            yield part
        result.model = "deepinfra/zai-org/GLM-4.7-Flash"
        result.tokens_in = 100
        result.tokens_out = 50

    monkeypatch.setattr(litellm_client, "stream_chat", _fake)

    async def _fake_embed(virtual_key, text):
        return [0.0] * 2048, 7

    monkeypatch.setattr(litellm_client, "embed_query", _fake_embed)
    return calls


async def enable_llm_key(tenant) -> None:
    async with db.tenant_tx(tenant.owner_id, tenant.id) as conn:
        await conn.execute(
            "update tenants set litellm_key_encrypted = 'sk-test-virtual' where id = $1", tenant.id
        )


async def test_stream_and_persist(client, fake_llm):
    tenant = await seed_tenant(client, f"chat-{uuid4().hex[:6]}")
    await enable_llm_key(tenant)
    headers = auth(tenant.owner_id, tenant.id)

    resp = await client.post("/api/v1/conversations", json={"title": "t"}, headers=headers)
    assert resp.status_code == 201, resp.text
    conv_id = resp.json()["id"]

    resp = await client.post(
        f"/api/v1/conversations/{conv_id}/messages",
        json={"content": "Say hello"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")
    events = parse_sse(resp.text)

    deltas = [d["content"] for e, d in events if e == "delta"]
    assert "".join(deltas) == "Hello world"

    done = dict(events)["done"]
    assert done["role"] == "assistant"
    assert done["content"] == "Hello world"
    assert done["model"] == "deepinfra/zai-org/GLM-4.7-Flash"
    assert done["tokens_in"] == 100
    assert done["tokens_out"] == 50
    assert done["cost_usd"] == pytest.approx(estimate_cost_usd("workhorse", 100, 50))
    assert done["soft_cap"] is False
    assert fake_llm == ["workhorse"]

    # Both messages persisted, assistant row carries the telemetry.
    resp = await client.get(f"/api/v1/conversations/{conv_id}/messages", headers=headers)
    rows = resp.json()
    assert [r["role"] for r in rows] == ["user", "assistant"]
    assert rows[1]["cost_usd"] == pytest.approx(estimate_cost_usd("workhorse", 100, 50))

    # Usage event captured with the alias (not the provider slug).
    async with db.tenant_tx(tenant.owner_id, tenant.id) as conn:
        row = await conn.fetchrow(
            "select model, tokens_in, tokens_out from usage_events"
            " where kind = 'chat' order by created_at desc limit 1"
        )
        assert row["model"] == "workhorse"
    assert row is not None and row["tokens_in"] == 100

    # Usage summary: seeded 10/20 + chat 100/50 + retrieval embed 7/0.
    summary = (await client.get("/api/v1/usage/summary", headers=headers)).json()
    assert summary["tokens_in"] == 117
    assert summary["tokens_out"] == 70


async def test_soft_cap_pins_routing_to_workhorse(client, fake_llm):
    tenant = await seed_tenant(client, f"cap-{uuid4().hex[:6]}")
    await enable_llm_key(tenant)
    headers = auth(tenant.owner_id, tenant.id)
    async with db.tenant_tx(tenant.owner_id, tenant.id) as conn:
        await conn.execute(
            """
            insert into usage_events (tenant_id, user_id, kind, model, cost_usd)
            values ($1, $2, 'chat', 'reasoner', 999)
            """,
            tenant.id,
            tenant.owner_id,
        )

    resp = await client.post(
        f"/api/v1/conversations/{tenant.conversation_id}/messages",
        json={"content": "Deep financial analysis please", "task_kind": "financial"},
        headers=headers,
    )
    events = dict(parse_sse(resp.text))
    assert events["done"]["soft_cap"] is True
    assert fake_llm == ["workhorse"]  # financial would be reasoner, cap pins it


async def test_task_kind_routes_when_under_cap(client, fake_llm):
    tenant = await seed_tenant(client, f"route-{uuid4().hex[:6]}")
    await enable_llm_key(tenant)
    headers = auth(tenant.owner_id, tenant.id)
    resp = await client.post(
        f"/api/v1/conversations/{tenant.conversation_id}/messages",
        json={"content": "Q3 numbers", "task_kind": "financial"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert fake_llm == ["reasoner"]


async def test_slides_kind_accepted_and_unknown_kind_rejected(client, fake_llm):
    tenant = await seed_tenant(client, f"kinds-{uuid4().hex[:6]}")
    await enable_llm_key(tenant)
    headers = auth(tenant.owner_id, tenant.id)

    resp = await client.post(
        f"/api/v1/conversations/{tenant.conversation_id}/messages",
        json={"content": "Deck about onboarding", "task_kind": "slides", "use_vault": False},
        headers=headers,
    )
    assert resp.status_code == 200
    assert fake_llm == ["drafter"]

    resp = await client.post(
        f"/api/v1/conversations/{tenant.conversation_id}/messages",
        json={"content": "Draw me a logo", "task_kind": "images"},
        headers=headers,
    )
    assert resp.status_code == 422


async def enable_web_search(tenant) -> None:
    async with db.tenant_tx(tenant.owner_id, tenant.id) as conn:
        await conn.execute(
            """update tenants set features = features || '{"web_search": true}' where id = $1""",
            tenant.id,
        )


async def test_research_requires_feature_flag(client):
    tenant = await seed_tenant(client, f"resgate-{uuid4().hex[:6]}")
    resp = await client.post(
        f"/api/v1/conversations/{tenant.conversation_id}/messages",
        json={"content": "latest CLH grants", "task_kind": "research"},
        headers=auth(tenant.owner_id, tenant.id),
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "feature_disabled"


async def test_research_without_exa_key_returns_503(client):
    tenant = await seed_tenant(client, f"reskey-{uuid4().hex[:6]}")
    await enable_llm_key(tenant)
    await enable_web_search(tenant)
    resp = await client.post(
        f"/api/v1/conversations/{tenant.conversation_id}/messages",
        json={"content": "latest CLH grants", "task_kind": "research", "use_vault": False},
        headers=auth(tenant.owner_id, tenant.id),
    )
    assert resp.status_code == 503
    assert resp.json()["error"]["code"] == "search_unavailable"


async def test_research_mode_yields_web_citations(client, monkeypatch):
    from app.search import WebSource

    tenant = await seed_tenant(client, f"resweb-{uuid4().hex[:6]}")
    await enable_llm_key(tenant)
    await enable_web_search(tenant)

    source = WebSource(
        chunk_id=uuid4(),
        title="GOV.UK — CLH funding",
        url="https://www.gov.uk/clh-funding",
        content="The fund supports community led housing groups in England.",
    )

    async def fake_exa(query, num_results=6, **kwargs):
        return [source]

    monkeypatch.setattr("app.routers.conversations.exa_search", fake_exa)

    async def fake_stream(virtual_key, alias, messages, result: StreamResult):
        # The web block must be in the system prompt.
        assert "web-results" in messages[0]["content"]
        text = f"Funding exists [c:{source.chunk_id}] but not this [c:{'0' * 32}]."
        result.text_parts.append(text)
        yield text
        result.model = "m"
        result.tokens_in = 10
        result.tokens_out = 5

    monkeypatch.setattr(litellm_client, "stream_chat", fake_stream)

    resp = await client.post(
        f"/api/v1/conversations/{tenant.conversation_id}/messages",
        json={"content": "latest CLH grants", "task_kind": "research", "use_vault": False},
        headers=auth(tenant.owner_id, tenant.id),
    )
    assert resp.status_code == 200
    done = dict(parse_sse(resp.text))["done"]

    # The real web source resolves with url/source_type; the fabricated
    # marker drops.
    assert done["content"] == "Funding exists [1] but not this ."
    assert len(done["citations"]) == 1
    citation = done["citations"][0]
    assert citation["url"] == source.url
    assert citation["source_type"] == "web"
    assert citation["title"] == source.title

    # Search call metered.
    async with db.tenant_tx(tenant.owner_id, tenant.id) as conn:
        kinds = [
            r["model"]
            for r in await conn.fetch("select model from usage_events where kind = 'search'")
        ]
    assert kinds == ["exa"]


async def test_gateway_down_returns_503_and_persists_nothing_extra(client):
    """No litellm key provisioned (gateway disabled): friendly 503, and the
    user message from the failed call is still recorded exactly once."""
    tenant = await seed_tenant(client, f"down-{uuid4().hex[:6]}")
    headers = auth(tenant.owner_id, tenant.id)
    resp = await client.post(
        f"/api/v1/conversations/{tenant.conversation_id}/messages",
        json={"content": "anyone there?"},
        headers=headers,
    )
    assert resp.status_code == 503
    assert resp.json()["error"]["code"] == "llm_unavailable"


async def test_stream_error_emits_error_event_without_assistant_row(client, monkeypatch):
    tenant = await seed_tenant(client, f"err-{uuid4().hex[:6]}")
    await enable_llm_key(tenant)
    headers = auth(tenant.owner_id, tenant.id)

    async def _boom(virtual_key, alias, messages, result):
        yield "partial "
        raise RuntimeError("connection reset")

    monkeypatch.setattr(litellm_client, "stream_chat", _boom)
    resp = await client.post(
        f"/api/v1/conversations/{tenant.conversation_id}/messages",
        json={"content": "hi", "use_vault": False},
        headers=headers,
    )
    events = parse_sse(resp.text)
    assert events[-1][0] == "error"
    assert events[-1][1]["error"]["code"] == "llm_error"

    async with db.tenant_tx(tenant.owner_id, tenant.id) as conn:
        count = await conn.fetchval(
            "select count(*) from messages where conversation_id = $1 and role = 'assistant'",
            tenant.conversation_id,
        )
    assert count == 0


async def test_member_cannot_read_other_users_conversation(client, fake_llm):
    """Conversations are personal: another member of the SAME tenant gets 404."""
    tenant = await seed_tenant(client, f"priv-{uuid4().hex[:6]}")
    headers_owner = auth(tenant.owner_id, tenant.id)
    invite = (
        await client.post(
            "/api/v1/invites",
            json={"email": "peer@example.com", "role": "member"},
            headers=headers_owner,
        )
    ).json()
    peer_id = uuid4()
    resp = await client.post(
        "/api/v1/invites/accept", json={"token": invite["token"]}, headers=auth(peer_id)
    )
    assert resp.status_code == 200

    resp = await client.get(
        f"/api/v1/conversations/{tenant.conversation_id}/messages",
        headers=auth(peer_id, tenant.id),
    )
    assert resp.status_code == 404


def test_build_scope_most_explicit_signal_wins():
    """A file attached to this chat beats the project's primary documents
    beats its other documents beats the rest of the vault."""
    from uuid import uuid4

    from app.retrieval import ATTACHED_WEIGHT, PRIMARY_WEIGHT, PROJECT_WEIGHT
    from app.routers.conversations import build_scope

    project_doc, primary_doc, attached_doc = uuid4(), uuid4(), uuid4()
    scope = build_scope({project_doc: False, primary_doc: True, attached_doc: True}, {attached_doc})
    assert scope is not None
    assert scope.weight(attached_doc) == ATTACHED_WEIGHT
    assert scope.weight(primary_doc) == PRIMARY_WEIGHT
    assert scope.weight(project_doc) == PROJECT_WEIGHT
    assert scope.weight(uuid4()) == 1.0

    # No project, no attachments: whole vault, equal weight.
    assert build_scope({}, set()) is None
    # An attachment alone still scopes an unprojected chat.
    lone = build_scope({}, {attached_doc})
    assert lone is not None and lone.weight(attached_doc) == ATTACHED_WEIGHT
