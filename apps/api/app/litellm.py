"""LiteLLM proxy client.

Two surfaces:
- admin (master key): virtual key lifecycle, one key per tenant (spec §4)
- chat (tenant virtual key): streaming completions against aliases

App code never names provider slugs — aliases only. When litellm_base_url is
unset (unit tests, CI), the admin surface is a no-op returning None and the
chat surface raises; chat tests inject a fake client instead.
"""

import json
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from uuid import UUID

import httpx

from app.config import get_settings
from app.errors import ApiError

#: Output ceiling and thinking bound for every chat completion.
#:
#: Chat used to send neither, and it is the single largest source of felt
#: latency on this surface. Every current chat alias is a reasoning model that
#: bills thinking against `completion_tokens` — `drafting/llm.py` measured
#: `drafter` spending 675–709 tokens thinking before it writes a word, and
#: `reasoner` filling an entire 4096-token budget with thought and returning
#: no prose at all. Reasoning tokens arrive as `reasoning_content`, which
#: `stream_chat` does not forward, so the whole thinking phase renders to the
#: user as a spinner on an open connection.
#:
#: `reasoning_effort` is what bounds the wait; `max_tokens` is only the
#: runaway guard behind it (a ceiling alone cannot bound a model that thinks
#: to fill whatever it is given). 4096 is deliberately generous — `report`,
#: `analyse` and `slides` modes produce full-length documents, and the point
#: here is latency, not truncation. A provider that ignores either parameter
#: is no worse off than before.
MAX_OUTPUT_TOKENS = 4096
REASONING_EFFORT = "low"

# $/1M tokens (input, output) per alias — spec §4 table + live OpenRouter
# pricing for longdoc. App-side cost estimate written to messages/usage_events;
# LiteLLM's own spend log is the reconciliation source (must agree within 5%,
# spec §11).
ALIAS_PRICES_PER_MTOK: dict[str, tuple[float, float]] = {
    "workhorse": (0.06, 0.40),
    "drafter": (0.15, 0.60),
    "reasoner": (0.93, 3.00),
    "longdoc": (0.09, 0.18),
    "embedder": (0.01, 0.0),
}


def estimate_cost_usd(alias: str, tokens_in: int, tokens_out: int) -> float:
    p_in, p_out = ALIAS_PRICES_PER_MTOK.get(alias, ALIAS_PRICES_PER_MTOK["workhorse"])
    return (tokens_in * p_in + tokens_out * p_out) / 1_000_000


@dataclass
class StreamResult:
    """Filled in as the stream is consumed; complete once the iterator ends."""

    model: str = ""
    tokens_in: int = 0
    tokens_out: int = 0
    text_parts: list[str] = field(default_factory=list)
    #: Seconds from issuing the request to the first *renderable* delta — the
    #: dead air the user actually sits through. Distinct from total generation
    #: time, and the number that tells us whether bounding the thinking above
    #: worked. None if the stream produced no content.
    ttft_s: float | None = None

    @property
    def text(self) -> str:
        return "".join(self.text_parts)


class LiteLLMClient:
    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None

    @property
    def enabled(self) -> bool:
        return bool(get_settings().litellm_base_url)

    def _http(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=get_settings().litellm_base_url, timeout=httpx.Timeout(120.0)
            )
        return self._client

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    # -- admin (master key) ---------------------------------------------------

    def _admin_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {get_settings().litellm_master_key}"}

    async def create_tenant_key(self, tenant_id: UUID, soft_budget_usd: float) -> str | None:
        """Virtual key per tenant: max_budget = 2x soft cap, 30d window (spec §4).
        Returns the key token (also its id for /key/info and /key/delete)."""
        if not self.enabled:
            return None
        resp = await self._http().post(
            "/key/generate",
            headers=self._admin_headers(),
            json={
                "key_alias": f"tenant-{tenant_id}",
                "max_budget": round(soft_budget_usd * 2, 2),
                "budget_duration": "30d",
                "metadata": {"tenant_id": str(tenant_id)},
            },
        )
        resp.raise_for_status()
        return resp.json()["key"]

    async def delete_key(self, key: str) -> None:
        if not self.enabled or not key:
            return
        resp = await self._http().post(
            "/key/delete", headers=self._admin_headers(), json={"keys": [key]}
        )
        resp.raise_for_status()

    # -- embeddings (tenant virtual key) ---------------------------------------

    async def embed_query(self, virtual_key: str, text: str) -> tuple[list[float], int]:
        """Embed one retrieval query; returns (vector, prompt_tokens)."""
        if not self.enabled:
            raise ApiError(503, "llm_unavailable", "Model gateway is not configured")
        resp = await self._http().post(
            "/v1/embeddings",
            headers={"Authorization": f"Bearer {virtual_key}"},
            json={"model": "embedder", "input": [text]},
        )
        if resp.status_code >= 400:
            raise ApiError(
                502 if resp.status_code >= 500 else 400,
                "llm_error",
                _safe_upstream_message(resp.status_code, resp.content),
            )
        payload = resp.json()
        return payload["data"][0]["embedding"], payload.get("usage", {}).get("prompt_tokens", 0)

    # -- chat (tenant virtual key) --------------------------------------------

    async def stream_chat(
        self,
        virtual_key: str,
        alias: str,
        messages: list[dict],
        result: StreamResult,
    ) -> AsyncIterator[str]:
        """Yield content deltas; fill `result` with model/usage from the final
        chunk (stream_options.include_usage)."""
        if not self.enabled:
            raise ApiError(503, "llm_unavailable", "Model gateway is not configured")
        started = time.perf_counter()
        async with self._http().stream(
            "POST",
            "/v1/chat/completions",
            headers={"Authorization": f"Bearer {virtual_key}"},
            json={
                "model": alias,
                "messages": messages,
                "stream": True,
                "stream_options": {"include_usage": True},
                "max_tokens": MAX_OUTPUT_TOKENS,
                "reasoning_effort": REASONING_EFFORT,
            },
        ) as resp:
            if resp.status_code >= 400:
                body = await resp.aread()
                raise ApiError(
                    502 if resp.status_code >= 500 else 400,
                    "llm_error",
                    _safe_upstream_message(resp.status_code, body),
                )
            async for line in resp.aiter_lines():
                if not line.startswith("data:"):
                    continue
                payload = line[len("data:") :].strip()
                if payload == "[DONE]":
                    break
                chunk = json.loads(payload)
                if chunk.get("model"):
                    result.model = chunk["model"]
                usage = chunk.get("usage")
                if usage:
                    result.tokens_in = usage.get("prompt_tokens", 0)
                    result.tokens_out = usage.get("completion_tokens", 0)
                for choice in chunk.get("choices", []):
                    delta = choice.get("delta", {}).get("content")
                    if delta:
                        if result.ttft_s is None:
                            result.ttft_s = time.perf_counter() - started
                        result.text_parts.append(delta)
                        yield delta


def _safe_upstream_message(status: int, body: bytes) -> str:
    """No provider payloads leaked to clients — ids and counts only (spec §9.5)."""
    if status == 429:
        return "Model provider rate limit hit, please retry shortly"
    if status == 400 and b"budget" in body.lower():
        return "This workspace has reached its usage budget for the period"
    return "The model gateway returned an error"


litellm_client = LiteLLMClient()
