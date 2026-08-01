"""Exa web search for the research task mode.

Deliberately a plain HTTP client, not a LiteLLM route: Exa is a search API,
not a model provider, so the gateway constraint does not apply. Results are
presented to the model as pseudo-vault excerpts — each gets a freshly minted
uuid so the existing citation-resolution pipeline (unique-id markers,
hallucination dropping) works unchanged.
"""

from dataclasses import dataclass
from uuid import UUID, uuid4

import httpx

from app.config import get_settings
from app.errors import ApiError

EXA_SEARCH_URL = "https://api.exa.ai/search"
# Keep each result roughly chunk-sized so a research prompt costs about the
# same context as a vault retrieval.
MAX_CONTENT_CHARS = 2_400
DEFAULT_NUM_RESULTS = 6
TIMEOUT_S = 15.0


@dataclass(frozen=True)
class WebSource:
    chunk_id: UUID  # minted per result; only ever lives inside one message
    title: str
    url: str
    content: str


async def exa_search(
    query: str,
    num_results: int = DEFAULT_NUM_RESULTS,
    *,
    client: httpx.AsyncClient | None = None,
) -> list[WebSource]:
    settings = get_settings()
    if not settings.exa_api_key:
        raise ApiError(503, "search_unavailable", "Web search is not configured")
    payload = {
        "query": query,
        "numResults": num_results,
        "contents": {"text": {"maxCharacters": MAX_CONTENT_CHARS}},
    }
    headers = {"x-api-key": settings.exa_api_key}
    try:
        if client is None:
            async with httpx.AsyncClient(timeout=TIMEOUT_S) as own:
                resp = await own.post(EXA_SEARCH_URL, json=payload, headers=headers)
        else:  # injected in tests (httpx.MockTransport)
            resp = await client.post(EXA_SEARCH_URL, json=payload, headers=headers)
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        raise ApiError(502, "search_failed", "Web search failed — try again") from exc

    sources: list[WebSource] = []
    for result in resp.json().get("results", []):
        url = result.get("url")
        if not url:
            continue
        sources.append(
            WebSource(
                chunk_id=uuid4(),
                title=(result.get("title") or url)[:300],
                url=url,
                content=(result.get("text") or "").strip()[:MAX_CONTENT_CHARS],
            )
        )
    return sources
