"""Document skeletons, and how sections are packed into model calls.

A skeleton is a fixed product decision, not something the model chooses: the
outline call annotates the sections below, it never adds, removes or reorders
them. That is what keeps two drafts of the same kind comparable, and what
stops a model dropping an inconvenient section.

A question set is the same rule with the decision moved into data. The
questions come from a funder's published form, held as reference data; the
model still cannot add, remove or reorder them. `Section.limit` is the funder's
own ceiling on the field behind the question, and it does two jobs — it shapes
the prompt, and it decides how many questions share a model call.
"""

from dataclasses import dataclass

from worker.drafting.llm import MAX_LLM_CALLS, DraftBudgetExceeded

#: A section may share a call only if its own ceiling is this small. Anything
#: wanting more room gets the model's full attention, because the failure mode
#: for a long answer is a thin one.
BATCH_ITEM_MAX_CHARS = 1500

#: Total characters a single batched call may be asked to produce. ~3k chars is
#: roughly 750 output tokens, which leaves the rest of `MAX_OUTPUT_TOKENS` for
#: the reasoning these aliases do before writing a word (see `llm.py`).
BATCH_MAX_CHARS = 3000


@dataclass(frozen=True)
class Section:
    key: str
    title: str
    #: Gateway alias — `reasoner` for financial or viability reasoning.
    alias: str = "drafter"
    #: Retrieve and cite vault excerpts for this section.
    uses_vault: bool = False
    #: Name of a data table the module renders after the narrative. The model
    #: is told to refer to it, never to repeat the numbers.
    table: str | None = None
    guidance: str = ""
    #: Hard ceiling on the answer, when this section is a question on someone
    #: else's form. `None` means prose whose length is a matter of judgement —
    #: every skeleton section, and the reason existing behaviour is unchanged.
    limit: int | None = None
    limit_kind: str = "characters"


def measure(text: str, section: Section) -> tuple[int, int]:
    """(length, overage) for a drafted answer, in the section's own units.

    Overage is reported, never trimmed. Cutting an answer to fit would end it
    mid-sentence, which is the failure `[TO CONFIRM]` exists to make visible
    rather than hide.
    """
    length = len(text.split()) if section.limit_kind == "words" else len(text)
    if section.limit is None:
        return length, 0
    return length, max(0, length - section.limit)


def plan_calls(sections: list[Section]) -> list[list[Section]]:
    """Group sections into model calls, preserving order.

    A section with no limit is always drafted alone — that is every skeleton
    section, so existing documents make exactly the calls they always did. Only
    a question small enough to say so shares a call, and only with its
    neighbours: keeping batches contiguous means a batch's answers appear
    together on the form, which is also how a person would write them.
    """
    batches: list[list[Section]] = []
    current: list[Section] = []
    budget = 0

    for section in sections:
        solo = (
            section.limit is None
            or section.limit > BATCH_ITEM_MAX_CHARS
            or section.limit_kind != "characters"
            or section.uses_vault
            or section.table is not None
            or section.alias != "drafter"
        )
        if solo:
            if current:
                batches.append(current)
                current, budget = [], 0
            batches.append([section])
            continue
        if current and budget + section.limit > BATCH_MAX_CHARS:
            batches.append(current)
            current, budget = [], 0
        current.append(section)
        budget += section.limit

    if current:
        batches.append(current)
    return batches


def check_call_budget(sections: list[Section], batches: list[list[Section]]) -> None:
    """Refuse a form too long to draft, before spending anything on it.

    `LlmLedger.check_next_call` would stop this too, but only part-way
    through — after billing for the answers it did get and leaving a job that
    failed for a reason a consultant cannot act on. Counting the calls first
    turns that into a sentence saying what to do instead.
    """
    if len(batches) + 1 > MAX_LLM_CALLS:  # +1 outline call
        raise DraftBudgetExceeded(
            f"This form has {len(sections)} questions, which is more than one draft "
            "can cover. Split it and draft the parts separately."
        )
