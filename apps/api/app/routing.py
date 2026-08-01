"""Model routing — pure function per spec §4.

default workhorse · analyse/report/slides/research → drafter ·
financial → reasoner ·
>100K context tokens → longdoc · soft budget cap → pinned to workhorse
(except contexts too large for it, which still need longdoc — which is
also the cheapest chat alias per token).
"""

LONGDOC_THRESHOLD_TOKENS = 100_000

_KIND_ALIASES = {
    "analyse": "drafter",
    "report": "drafter",
    "financial": "reasoner",
    "slides": "drafter",
    "research": "drafter",
}


def select_route(
    task_kind: str | None,
    context_tokens: int,
    *,
    soft_cap_hit: bool = False,
) -> str:
    if context_tokens > LONGDOC_THRESHOLD_TOKENS:
        return "longdoc"
    if soft_cap_hit:
        return "workhorse"
    return _KIND_ALIASES.get(task_kind or "", "workhorse")


def estimate_tokens(text: str) -> int:
    """Cheap upper-bound estimate for routing only (not billing): ~4 chars/token."""
    return len(text) // 4 + 1
