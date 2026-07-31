"""Budgeted LLM calls for drafting (PRD §5): every call goes through the
ledger, which enforces the cost guard — ≤ 15 calls per job, ≤ 24k tokens of
context per call — and records per-call usage for usage_events rows.

Aliases only (`drafter`/`reasoner`), via the tenant's virtual key against the
LiteLLM gateway; prices are the spec §4 alias rates (worker keeps its own
copy, same as summarize.py)."""

from dataclasses import dataclass

import httpx

from worker.blocks import estimate_tokens
from worker.settings import get_settings

MAX_LLM_CALLS = 15
MAX_CONTEXT_TOKENS_PER_CALL = 24_000

# $/1M tokens (input, output) per alias (spec §4).
ALIAS_PRICES_PER_MTOK = {"drafter": (0.15, 0.60), "reasoner": (0.93, 3.00)}


class DraftBudgetExceeded(RuntimeError):
    """Raised when a job would exceed the cost guard — the message is shown
    to the user as-is, so keep it friendly and actionable."""


@dataclass
class LlmCall:
    alias: str
    tokens_in: int
    tokens_out: int

    @property
    def cost_usd(self) -> float:
        price_in, price_out = ALIAS_PRICES_PER_MTOK[self.alias]
        return (self.tokens_in * price_in + self.tokens_out * price_out) / 1_000_000


class LlmLedger:
    def __init__(self) -> None:
        self.calls: list[LlmCall] = []
        self.embed_tokens = 0
        self.embed_cost_usd = 0.0

    @property
    def tokens_in(self) -> int:
        return sum(c.tokens_in for c in self.calls)

    @property
    def tokens_out(self) -> int:
        return sum(c.tokens_out for c in self.calls)

    @property
    def cost_usd(self) -> float:
        return sum(c.cost_usd for c in self.calls) + self.embed_cost_usd

    def check_next_call(self, system: str, user: str) -> None:
        if len(self.calls) >= MAX_LLM_CALLS:
            raise DraftBudgetExceeded(
                "This draft reached its model-call budget before finishing. "
                "Try again, or reduce the amount of project data it has to cover."
            )
        context_tokens = estimate_tokens(system) + estimate_tokens(user)
        if context_tokens > MAX_CONTEXT_TOKENS_PER_CALL:
            raise DraftBudgetExceeded(
                "One section of this draft needs more context than a single model "
                "call allows. Trim long notes or reduce the vault scope and try again."
            )


async def chat(
    ledger: LlmLedger,
    virtual_key: str,
    alias: str,
    system: str,
    user: str,
    max_tokens: int = 1024,
) -> str:
    """One non-streaming chat completion against a gateway alias, recorded on
    the ledger. The guard runs before the network call, so an over-budget job
    aborts without spending anything further."""
    ledger.check_next_call(system, user)
    settings = get_settings()
    async with httpx.AsyncClient(
        base_url=settings.litellm_base_url, timeout=httpx.Timeout(180.0)
    ) as client:
        resp = await client.post(
            "/v1/chat/completions",
            headers={"Authorization": f"Bearer {virtual_key}"},
            json={
                "model": alias,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "max_tokens": max_tokens,
                "temperature": 0.2,
            },
        )
        resp.raise_for_status()
        payload = resp.json()
    usage = payload.get("usage", {})
    ledger.calls.append(
        LlmCall(
            alias=alias,
            tokens_in=usage.get("prompt_tokens", 0),
            tokens_out=usage.get("completion_tokens", 0),
        )
    )
    return payload["choices"][0]["message"]["content"].strip()
