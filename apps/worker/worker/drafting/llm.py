"""Budgeted LLM calls for drafting (PRD §5): every call goes through the
ledger, which enforces the cost guard — ≤ 15 calls per job, ≤ 24k tokens of
context per call — and records per-call usage for usage_events rows.

Aliases only (`drafter`/`reasoner`), via the tenant's virtual key against the
LiteLLM gateway; prices are the spec §4 alias rates (worker keeps its own
copy, same as summarize.py)."""

import logging
import time
from dataclasses import dataclass

import httpx

from worker.blocks import estimate_tokens
from worker.settings import get_settings

# Per-call timing. A draft is ~11 calls and has been measured at ~3 min/call
# on `drafter`, which is far too slow to be generation on that provider — the
# suspicion is rate-limit backoff on the Groq free tier (200k tokens/day
# against ~51k per draft). Elapsed time per call settles it: backoff produces
# a bimodal distribution, genuinely slow generation does not. Ids, aliases and
# counts only — never prompt or document content.
logger = logging.getLogger("worker.drafting.latency")

MAX_LLM_CALLS = 15
MAX_CONTEXT_TOKENS_PER_CALL = 24_000

#: Output ceiling per section call.
#:
#: This has to clear *reasoning* tokens, not just prose. Both current drafting
#: aliases are reasoning models, and they bill their thinking against
#: `completion_tokens`: a measured monitoring-report section spent 675–709
#: tokens reasoning before writing a word. At the old ceiling of 1024 every
#: section of a data-heavy document came back `finish_reason=length`, and the
#: ones whose reasoning ran longest came back with **no content at all** —
#: which the pipeline then assembled into a document with missing sections.
#: 4096 leaves roughly 3k for prose after a long think; a section that still
#: does not fit is caught by the guards below rather than silently dropped.
MAX_OUTPUT_TOKENS = 4096

#: Bound how long a model may think before it writes.
#:
#: Raising `MAX_OUTPUT_TOKENS` alone does not fix a reasoning model, because
#: some will think for whatever budget they are given: measured live, the
#: `reasoner` alias spent the **entire** 4096-token budget reasoning on a real
#: section and returned zero prose (`finish_reason=length`, `content=""`).
#: Bounding the effort turned the same call into 541 tokens with 1.5k
#: characters of prose. Both current aliases accept the parameter; a provider
#: that ignores it is no worse off than before, and the empty-content guard in
#: `chat()` remains the backstop either way.
REASONING_EFFORT = "low"

# $/1M tokens (input, output) per alias (spec §4).
ALIAS_PRICES_PER_MTOK = {"drafter": (0.15, 0.60), "reasoner": (0.93, 3.00)}


class DraftBudgetExceeded(RuntimeError):
    """Raised when a job would exceed the cost guard — the message is shown
    to the user as-is, so keep it friendly and actionable."""


class EmptySectionError(RuntimeError):
    """A model call returned no prose.

    Failing the job is deliberate. The alternative — the behaviour this
    replaces — is a document that is quietly missing a section, filed as a
    clean draft with nothing to indicate the gap. A failed job the user
    retries is recoverable; a hollow monitoring return sent to a funder is
    not. The message is shown to the user as-is.
    """


@dataclass
class LlmCall:
    alias: str
    tokens_in: int
    tokens_out: int
    #: The model hit the output ceiling — its prose stops mid-sentence.
    truncated: bool = False
    #: Wall-clock seconds for the call, gateway retries included. Diagnostic
    #: only: it is deliberately outside the cost guard, which meters spend.
    elapsed_s: float = 0.0

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

    @property
    def truncated_calls(self) -> int:
        """Calls whose prose stopped at the ceiling. Surfaced in the audit
        meta so a draft full of clipped sections is visible, not just felt."""
        return sum(1 for c in self.calls if c.truncated)

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
    max_tokens: int = MAX_OUTPUT_TOKENS,
    allow_empty: bool = False,
) -> str:
    """One non-streaming chat completion against a gateway alias, recorded on
    the ledger. The guard runs before the network call, so an over-budget job
    aborts without spending anything further.

    Raises `EmptySectionError` when the model returns no prose — see that
    class for why this fails the job rather than writing a shorter document.
    `allow_empty` is for the outline call, which is an optimisation rather
    than content: it is designed to degrade to an empty outline instead of
    spending budget on retries, so an empty reply there is not a failure.
    """
    ledger.check_next_call(system, user)
    settings = get_settings()
    started = time.perf_counter()
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
                "reasoning_effort": REASONING_EFFORT,
            },
        )
        resp.raise_for_status()
        payload = resp.json()
    elapsed = time.perf_counter() - started
    usage = payload.get("usage", {})
    choice = payload["choices"][0]
    ledger.calls.append(
        LlmCall(
            alias=alias,
            tokens_in=usage.get("prompt_tokens", 0),
            tokens_out=usage.get("completion_tokens", 0),
            truncated=choice.get("finish_reason") == "length",
            elapsed_s=elapsed,
        )
    )
    logger.info(
        "draft call=%d alias=%s elapsed_ms=%d tokens_in=%d tokens_out=%d finish=%s",
        len(ledger.calls),
        alias,
        elapsed * 1000,
        usage.get("prompt_tokens", 0),
        usage.get("completion_tokens", 0),
        choice.get("finish_reason"),
    )
    # `content` is None on some gateways when a reasoning model spends its
    # whole output budget thinking, and "" on others — both mean no prose.
    content = (choice["message"].get("content") or "").strip()
    if not content and not allow_empty:
        raise EmptySectionError(
            "The model returned an empty section, so the draft would have had a "
            "gap in it. Nothing was filed — try again."
        )
    return content
