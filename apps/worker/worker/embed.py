"""Embeddings via the LiteLLM `embedder` alias, called with the tenant's own
virtual key so spend lands on the tenant's budget. Batches of 64 (spec §5)."""

import httpx

from worker.settings import get_settings

# $/1M input tokens for the embedder alias (spec §4).
EMBED_PRICE_PER_MTOK = 0.01


class EmbedResult:
    def __init__(self) -> None:
        self.vectors: list[list[float]] = []
        self.tokens = 0

    @property
    def cost_usd(self) -> float:
        return self.tokens * EMBED_PRICE_PER_MTOK / 1_000_000


async def embed_texts(virtual_key: str, texts: list[str]) -> EmbedResult:
    settings = get_settings()
    result = EmbedResult()
    async with httpx.AsyncClient(
        base_url=settings.litellm_base_url, timeout=httpx.Timeout(120.0)
    ) as client:
        for start in range(0, len(texts), settings.embed_batch_size):
            batch = texts[start : start + settings.embed_batch_size]
            resp = await client.post(
                "/v1/embeddings",
                headers={"Authorization": f"Bearer {virtual_key}"},
                json={"model": "embedder", "input": batch},
            )
            resp.raise_for_status()
            payload = resp.json()
            # index field keeps order stable regardless of response ordering
            ordered = sorted(payload["data"], key=lambda d: d["index"])
            result.vectors.extend(d["embedding"] for d in ordered)
            result.tokens += payload.get("usage", {}).get("prompt_tokens", 0)
    return result
