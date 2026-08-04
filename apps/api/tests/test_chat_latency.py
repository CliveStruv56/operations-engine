"""The latency work of 4 Aug 2026 (docs/performance-review-aug-2026.md).

Two things are pinned here, both of which fail silently if they regress —
which is exactly how the reasoning-model bugs of 3–4 Aug went unnoticed:

- the chat completion carries `max_tokens` and `reasoning_effort`, so an
  unbounded model cannot go back to thinking for free in front of the user;
- the query embedding and the web search overlap rather than running back to
  back, so a research message stops paying for both in series.

`test_chat.py` stubs `stream_chat` wholesale and so can never see the request
body; these drive the real client over a mock transport instead.
"""

import asyncio
import json
from uuid import uuid4

import httpx
import pytest

from app.config import get_settings
from app.errors import ApiError
from app.litellm import (
    CHAT_NUM_RETRIES,
    MAX_OUTPUT_TOKENS,
    REASONING_EFFORT,
    LiteLLMClient,
    StreamResult,
    litellm_client,
)
from tests.conftest import auth, seed_tenant
from tests.test_chat import enable_llm_key, enable_web_search, parse_sse


def sse_body(chunks: list[dict]) -> bytes:
    return ("".join(f"data: {json.dumps(c)}\n\n" for c in chunks) + "data: [DONE]\n\n").encode()


def gateway(monkeypatch, handler) -> LiteLLMClient:
    """A client whose transport is under our control. `_client` is set
    directly so `_http()` finds it already built and never opens a socket."""
    monkeypatch.setattr(get_settings(), "litellm_base_url", "http://gateway.test")
    client = LiteLLMClient()
    monkeypatch.setattr(
        client,
        "_client",
        httpx.AsyncClient(base_url="http://gateway.test", transport=httpx.MockTransport(handler)),
    )
    return client


async def test_chat_bounds_thinking_and_output():
    """Without these two parameters the model may think for as long as the
    provider default allows, emitting nothing the stream can render."""
    captured: dict = {}
    headers: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        headers.update(request.headers)
        return httpx.Response(
            200,
            content=sse_body(
                [
                    {"model": "m", "choices": [{"delta": {"content": "Hi"}}]},
                    {
                        "model": "m",
                        "choices": [{"delta": {"content": " there"}}],
                        "usage": {"prompt_tokens": 11, "completion_tokens": 2},
                    },
                ]
            ),
        )

    with pytest.MonkeyPatch.context() as mp:
        client = gateway(mp, handler)
        result = StreamResult()
        deltas = [
            d
            async for d in client.stream_chat(
                "sk-virtual", "workhorse", [{"role": "user", "content": "hi"}], result
            )
        ]

    assert deltas == ["Hi", " there"]
    assert captured["max_tokens"] == MAX_OUTPUT_TOKENS
    assert captured["reasoning_effort"] == REASONING_EFFORT
    # Still an alias, never a provider slug (hard constraint 3).
    assert captured["model"] == "workhorse"
    assert result.tokens_in == 11
    assert result.tokens_out == 2
    # The gateway default of 2 retries at a 120s timeout belongs to the
    # worker; chat overrides it per request because `drafter` serves both.
    assert headers["x-litellm-num-retries"] == CHAT_NUM_RETRIES


async def test_ttft_measures_first_renderable_delta():
    """TTFT is the dead air the user sits through, so it must be pinned to
    the first *content* delta — not to the response arriving."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=sse_body(
                [
                    # Thinking: billed, streamed, and invisible to the reader.
                    {"model": "m", "choices": [{"delta": {"reasoning_content": "hmm"}}]},
                    {"model": "m", "choices": [{"delta": {"content": "Answer"}}]},
                ]
            ),
        )

    with pytest.MonkeyPatch.context() as mp:
        client = gateway(mp, handler)
        result = StreamResult()
        assert result.ttft_s is None
        deltas = [
            d
            async for d in client.stream_chat(
                "sk-virtual", "workhorse", [{"role": "user", "content": "hi"}], result
            )
        ]

    assert deltas == ["Answer"]  # reasoning_content is not forwarded
    assert result.ttft_s is not None and result.ttft_s >= 0


async def test_ttft_stays_none_when_the_model_only_thinks():
    """The failure this whole change exists to make visible: a reply that
    spends its entire budget reasoning renders nothing and must not be
    recorded as though it arrived promptly."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=sse_body(
                [
                    {"model": "m", "choices": [{"delta": {"reasoning_content": "hmm"}}]},
                    {
                        "model": "m",
                        "choices": [{"delta": {}, "finish_reason": "length"}],
                        "usage": {"prompt_tokens": 9, "completion_tokens": 4096},
                    },
                ]
            ),
        )

    with pytest.MonkeyPatch.context() as mp:
        client = gateway(mp, handler)
        result = StreamResult()
        deltas = [
            d
            async for d in client.stream_chat(
                "sk-virtual", "workhorse", [{"role": "user", "content": "hi"}], result
            )
        ]

    assert deltas == []
    assert result.text == ""
    assert result.ttft_s is None
    assert result.tokens_out == 4096  # paid for in full, showed nothing


async def test_embedding_and_web_search_overlap(client, monkeypatch):
    """Research mode runs both network calls; neither reads the other's
    result, so the second must not wait on the first."""
    events: list[str] = []

    async def fake_embed(virtual_key, text):
        events.append("embed:start")
        await asyncio.sleep(0.05)
        events.append("embed:end")
        return [0.0] * 2048, 7

    async def fake_exa(query, num_results=6, **kwargs):
        events.append("search:start")
        await asyncio.sleep(0.05)
        events.append("search:end")
        return []

    async def fake_stream(virtual_key, alias, messages, result: StreamResult):
        result.text_parts.append("ok")
        yield "ok"
        result.model = "m"
        result.tokens_in = 10
        result.tokens_out = 5

    monkeypatch.setattr(litellm_client, "embed_query", fake_embed)
    monkeypatch.setattr(litellm_client, "stream_chat", fake_stream)
    monkeypatch.setattr("app.routers.conversations.exa_search", fake_exa)

    tenant = await seed_tenant(client, f"lat-{uuid4().hex[:6]}")
    await enable_llm_key(tenant)
    await enable_web_search(tenant)

    resp = await client.post(
        f"/api/v1/conversations/{tenant.conversation_id}/messages",
        json={"content": "clh grants", "task_kind": "research", "use_vault": True},
        headers=auth(tenant.owner_id, tenant.id),
    )
    assert resp.status_code == 200
    assert "done" in dict(parse_sse(resp.text))

    # Ordering, not wall-clock: the search must have started before the
    # embedding finished. Serial execution cannot produce this interleaving,
    # and asserting on elapsed time would be flaky under a loaded CI box.
    assert events.index("search:start") < events.index("embed:end")


async def test_embedding_failure_still_surfaces_first(client, monkeypatch):
    """Both calls now run concurrently, so both can fail. The embedding error
    is the one the user sees, exactly as when these ran in sequence."""

    async def fake_embed(virtual_key, text):
        raise ApiError(502, "llm_error", "The model gateway returned an error")

    async def fake_exa(query, num_results=6, **kwargs):
        raise ApiError(502, "search_failed", "Web search failed — try again")

    monkeypatch.setattr(litellm_client, "embed_query", fake_embed)
    monkeypatch.setattr("app.routers.conversations.exa_search", fake_exa)

    tenant = await seed_tenant(client, f"latf-{uuid4().hex[:6]}")
    await enable_llm_key(tenant)
    await enable_web_search(tenant)

    resp = await client.post(
        f"/api/v1/conversations/{tenant.conversation_id}/messages",
        json={"content": "clh grants", "task_kind": "research", "use_vault": True},
        headers=auth(tenant.owner_id, tenant.id),
    )
    assert resp.status_code == 502
    assert resp.json()["error"]["code"] == "llm_error"
