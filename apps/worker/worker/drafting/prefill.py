"""Answering a funder's question from the register, without a model call.

This is where the product's promise gets literal. A form asks "What is your
charity number?" with a twenty-character box; the workspace holds that fact,
confirmed, with a link to the register it came from. Sending that to a model
would be spending money to retype something we already know, and adding a
chance of getting it wrong.

Two tiers, and the line between them is the honest part:

**Tier A — the answer, no model call.** The question matches exactly one
scalar fact and the answer fits the box. The claim is the answer.

**Tier B — a grounded draft, still one call.** The question matches, but it
wants prose: "Who is the applicant organisation, and what is its legal form?"
at 750 characters is a paragraph, not a lookup. The section is marked
`uses_claims` so it drafts *with* the facts rather than from nothing, which is
the phase-2 mechanism doing its job.

We do not pretend tier B is tier A. Synthesising a 750-character narrative from
a database and calling it filled-in would be the kind of promise that gets
found out on a funder's form.

Matching is whole-word against the claim kind's `question_hints`, never
substring. `app/crm/lookup.py` records why in blood: a substring lookup for
"SAM" matched "Samantha Fry" and put her home address in a prompt.
"""

import re

from worker.drafting.pack import ClaimFacts, DraftPackBase
from worker.drafting.sections import Section, measure

#: The largest field we will answer outright. Above this a funder is asking for
#: prose, and the size of the box is the clearest statement of that we have:
#: "Who is the applicant organisation, and what is its legal form?" at 750
#: characters wants the name, the structure, the founding date and the purpose.
#: Handing it a one-line charity number would fit the box, pass every other
#: check, and answer a different question from the one asked — so a large field
#: goes to tier B, where the facts still reach the model.
#:
#: 120 comfortably holds a registered office or a registered name; nothing that
#: wants a paragraph is written into a field this small.
PREFILL_MAX_LIMIT = 120

#: Below this, a form field wants the bare value rather than a sentence. A
#: twenty-character "Charity number" box wants `1234567`; the same fact in a
#: 750-character box wants "The organisation is a registered charity, number
#: 1234567." Sixty is comfortably above the longest identifier and well below
#: any field expecting prose.
BARE_VALUE_LIMIT = 60

#: Value kinds that can stand alone as an answer. A `list` or a `boolean` needs
#: framing to read as English, so those go to tier B even when they match.
SCALAR_KINDS = frozenset({"text", "number", "money", "date"})


def _hint_pattern(hints: list[str]) -> re.Pattern[str] | None:
    """Whole-word alternation over a kind's hints.

    `\\b` on both ends, so "income" does not match "incomer" and — the case
    that matters — a hint never fires on a fragment of an unrelated word.
    """
    usable = [re.escape(h.strip()) for h in hints if h and h.strip()]
    if not usable:
        return None
    return re.compile(r"\b(?:" + "|".join(usable) + r")\b", re.IGNORECASE)


def match_claims(text: str, claims: list[ClaimFacts]) -> list[ClaimFacts]:
    """Every claim whose kind's hints appear in the question.

    Order follows `claims`, which `load_claims` sorts by kind, subject and
    period — so a multi-valued kind's rows arrive together and in a stable
    order, and the same form produces the same answers twice running.
    """
    if not text.strip():
        return []
    return [
        claim
        for claim in claims
        if (pattern := _hint_pattern(claim.question_hints)) is not None and pattern.search(text)
    ]


def _short_value(claim: ClaimFacts) -> str | None:
    """The bare value, for a box too small for a sentence."""
    value = claim.value
    if value is None or isinstance(value, list | dict | bool):
        return None
    if isinstance(value, float) and value.is_integer():
        # A charity's income comes back as 847000.0 through jsonb; nobody
        # writes that on a form.
        return str(int(value))
    text = str(value).strip()
    return text or None


def prefill_answer(section: Section, claims: list[ClaimFacts]) -> tuple[str, ClaimFacts] | None:
    """The tier-A answer for this question, or nothing.

    Deliberately conservative. Every condition here is a way the answer could
    be wrong in a box somebody then submits over their own name, and a blank
    the consultant fills is a far cheaper failure than a confident wrong one.
    """
    # A question wanting vault evidence is asking for an argument, not a fact.
    if section.uses_vault:
        return None
    # No limit means a skeleton section — a whole document section, never a
    # lookup. A big limit means prose. Either way the model writes it, with the
    # facts in hand.
    if section.limit is None or section.limit > PREFILL_MAX_LIMIT:
        return None

    matched = match_claims(f"{section.title} {section.guidance}", claims)
    if len(matched) != 1:
        # Nothing matched, or the question spans several facts ("your income
        # and expenditure"). Either way it is not a lookup — tier B can still
        # draft it with the facts in hand.
        return None

    claim = matched[0]
    if claim.value_kind not in SCALAR_KINDS or claim.cardinality != "single":
        return None
    # Never auto-fill something we know has gone off. The draft would look
    # complete and be wrong, which is the one outcome worse than a gap.
    if claim.expired:
        return None

    short = _short_value(claim)
    if section.limit < BARE_VALUE_LIMIT and short:
        candidates = [short, claim.statement]
    else:
        candidates = [claim.statement, short] if short else [claim.statement]

    for candidate in candidates:
        if candidate and measure(candidate, section)[1] == 0:
            return candidate, claim
    # It matched, but nothing we hold fits the funder's box. Let the model
    # write to the limit instead of handing over something that will be cut.
    return None


def partition_prefilled(
    sections: list[Section], pack: DraftPackBase
) -> tuple[list[tuple[Section, str]], list[Section], dict[str, list[str]]]:
    """Split the form into answers we already have and questions to draft.

    Returns the pre-filled `(section, answer)` pairs in the same shape
    `_draft_batch` produces, the sections still needing a model, and the claim
    ids behind each answered or claim-assisted section.

    Sections that reach tier B are returned in `to_draft` with `uses_claims`
    set, which is what puts the facts in their prompt. Skeleton sections are
    untouched: they carry their own `uses_claims` from the module's skeleton
    and are not questions on somebody's form.
    """
    prefilled: list[tuple[Section, str]] = []
    to_draft: list[Section] = []
    claim_ids: dict[str, list[str]] = {}

    for section in sections:
        answer = prefill_answer(section, pack.claims)
        if answer is not None:
            text, claim = answer
            prefilled.append((section, text))
            claim_ids[section.key] = [str(claim.id)]
            continue

        # Tier B: hand the facts to a question that is clearly about the
        # organisation, unless the skeleton already decided.
        if not section.uses_claims:
            matched = match_claims(f"{section.title} {section.guidance}", pack.claims)
            if matched:
                section = replace_uses_claims(section)
                claim_ids[section.key] = [str(c.id) for c in matched]
        to_draft.append(section)

    return prefilled, to_draft, claim_ids


def replace_uses_claims(section: Section) -> Section:
    """`Section` is frozen, so marking one means making a new one."""
    return Section(
        key=section.key,
        title=section.title,
        alias=section.alias,
        uses_vault=section.uses_vault,
        uses_claims=True,
        table=section.table,
        guidance=section.guidance,
        limit=section.limit,
        limit_kind=section.limit_kind,
    )


def restore_order(
    spec: list[Section], drafted: list[tuple[Section, str]], prefilled: list[tuple[Section, str]]
) -> list[tuple[Section, str]]:
    """Put the answers back in the funder's order.

    The two halves finish separately, and a form whose answers arrive in a
    different order from its questions is unusable — the whole sheet is read
    against the funder's own numbering.
    """
    answers = {section.key: (section, text) for section, text in [*drafted, *prefilled]}
    return [answers[s.key] for s in spec if s.key in answers]
