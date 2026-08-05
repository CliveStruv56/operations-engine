"""The per-document summary call against a reasoning model.

`drafter` is gpt-oss-120b (reached via OpenRouter since 4 Aug 2026, which
changes the provider but not the model — ASSUMPTIONS #25). It bills thinking against
`completion_tokens` — 675–709 tokens before it writes a word, measured live on
3 Aug 2026. The summariser was written when the aliases were not reasoning
models and asked for 512 output tokens, so the whole budget went on reasoning
and the call came back with no content. Ingest catches summary failures by
design, so this was silent: documents went to `ready` with no summary, and
"what are the key messages of X?" stopped working for them.
"""

import pytest

from tests.test_drafts_pipeline import _FakeClient
from worker.summarize import MAX_OUTPUT_TOKENS, REASONING_EFFORT, summarize_document


def _payload(content, completion_tokens=300):
    return {
        "choices": [{"message": {"content": content}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 5_000, "completion_tokens": completion_tokens},
    }


def _patch(monkeypatch, payload) -> _FakeClient:
    client = _FakeClient(payload)
    monkeypatch.setattr("worker.summarize.httpx.AsyncClient", lambda **kw: client)
    monkeypatch.setattr(
        "worker.summarize.get_settings",
        lambda: type("S", (), {"litellm_base_url": "http://gateway"})(),
    )
    return client


async def test_the_output_budget_clears_reasoning_tokens(monkeypatch):
    client = _patch(monkeypatch, _payload("A summary of the document."))
    result = await summarize_document("key", "Local Plan", ["chunk one", "chunk two"])

    assert result.text == "A summary of the document."
    assert client.sent["max_tokens"] == MAX_OUTPUT_TOKENS
    assert MAX_OUTPUT_TOKENS >= 1024, "must clear ~700 reasoning tokens plus a 250-word summary"
    assert client.sent["reasoning_effort"] == REASONING_EFFORT


async def test_an_empty_summary_raises_rather_than_storing_a_hollow_chunk(monkeypatch):
    """Ingest treats a missing summary as fine. An empty one is not: it would
    be stored on the document and embedded as a summary chunk saying nothing."""
    _patch(monkeypatch, _payload("", completion_tokens=MAX_OUTPUT_TOKENS))
    with pytest.raises(ValueError, match="empty summary"):
        await summarize_document("key", "Local Plan", ["chunk one"])


async def test_a_null_content_is_treated_as_empty(monkeypatch):
    """Some gateways return null rather than "" when a reasoning model spends
    its whole budget thinking — `None.strip()` used to raise AttributeError
    here, which read as an ordinary summary failure."""
    _patch(monkeypatch, _payload(None))
    with pytest.raises(ValueError, match="empty summary"):
        await summarize_document("key", "Local Plan", ["chunk one"])


async def test_cost_uses_the_drafter_alias_rates(monkeypatch):
    _patch(monkeypatch, _payload("Summary.", completion_tokens=1_000))
    result = await summarize_document("key", "Local Plan", ["chunk"])
    assert result.cost_usd == pytest.approx((5_000 * 0.15 + 1_000 * 0.60) / 1_000_000)
