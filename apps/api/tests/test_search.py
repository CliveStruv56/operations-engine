"""Exa search client: disabled-service 503, result mapping, upstream failure."""

import httpx
import pytest

from app.config import get_settings
from app.errors import ApiError
from app.search import MAX_CONTENT_CHARS, exa_search


async def test_search_disabled_returns_503():
    with pytest.raises(ApiError) as exc:
        await exa_search("anything")
    assert exc.value.status_code == 503
    assert exc.value.code == "search_unavailable"


async def test_search_maps_results(monkeypatch):
    monkeypatch.setattr(get_settings(), "exa_api_key", "test-key")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["x-api-key"] == "test-key"
        return httpx.Response(
            200,
            json={
                "results": [
                    {"url": "https://a.example/x", "title": "A page", "text": "hello " * 1000},
                    {"title": "no url — skipped"},
                    {"url": "https://www.b.example/y", "title": None, "text": None},
                ]
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        sources = await exa_search("community led housing", client=client)

    assert [s.url for s in sources] == ["https://a.example/x", "https://www.b.example/y"]
    assert len(sources[0].content) <= MAX_CONTENT_CHARS
    assert sources[1].title == "https://www.b.example/y"  # falls back to the url
    assert sources[0].chunk_id != sources[1].chunk_id


async def test_search_upstream_failure_returns_502(monkeypatch):
    monkeypatch.setattr(get_settings(), "exa_api_key", "test-key")
    transport = httpx.MockTransport(lambda request: httpx.Response(500))
    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(ApiError) as exc:
            await exa_search("q", client=client)
    assert exc.value.status_code == 502
    assert exc.value.code == "search_failed"
