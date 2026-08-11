"""Question sets: a funder's own form, loaded as reference data.

Shared rather than per-module because nothing here is Groundwork's or
Grantwork's — a funder asks a community-led housing consultancy and a charity
the same kind of question, and both modules draft the answer through the same
engine.

Two tables back this, and the order matters. A tenant's own set wins over the
platform catalogue on the same key: if somebody has sat down and corrected the
questions for the funder they are actually applying to, that correction is
better than ours and must not be silently overridden on the next re-seed.
"""

from datetime import date

import asyncpg
from pydantic import BaseModel, Field

from worker.drafting.sections import Section

#: Vault queries a question set may generate. Retrieval costs an embedding
#: call per query and the existing skeletons ask at most four, so a form with
#: fifteen evidence questions does not get fifteen arms — the top few by order
#: stand in, and every answer sees whatever they retrieved.
MAX_QUESTION_QUERIES = 4

_SELECT = """
    key, name, funder, stage, status, source_url, questions,
    last_verified, next_review, notes
"""


class QuestionFacts(BaseModel):
    id: str
    order: int = 1
    text: str
    guidance: str = ""
    limit_kind: str = "characters"
    limit: int | None = None
    required: bool = True
    uses_vault: bool = False


class QuestionSet(BaseModel):
    """A funder's form. `stale` is derived at load, never stored — same
    contract as the funding-programme and funder catalogues."""

    key: str
    name: str
    funder: str
    stage: str
    status: str
    source_url: str | None = None
    notes: str | None = None
    last_verified: date
    next_review: date
    questions: list[QuestionFacts] = Field(default_factory=list)
    #: Which table it came from. A tenant's own set is not something we have
    #: checked, and the draft must not present the two alike.
    source: str = "platform"
    stale: bool = False

    def ordered(self) -> list[QuestionFacts]:
        return sorted(self.questions, key=lambda q: q.order)


def _build(row: asyncpg.Record, questions: list, source: str, today: date) -> QuestionSet:
    return QuestionSet(
        **{k: row[k] for k in ("key", "name", "funder", "stage", "status", "source_url", "notes")},
        last_verified=row["last_verified"],
        next_review=row["next_review"],
        questions=[QuestionFacts(**q) for q in questions],
        source=source,
        stale=row["next_review"] <= today,
    )


async def load_question_set(
    conn: asyncpg.Connection, key: str, today: date, loads
) -> QuestionSet | None:
    """The tenant's own version of this set, or the platform one.

    `loads` is the module's jsonb decoder — asyncpg hands back `str` with no
    codec registered, and both modules already carry the same one-liner.
    """
    row = await conn.fetchrow(f"select {_SELECT} from tenant_question_sets where key = $1", key)
    if row is not None:
        return _build(row, loads(row["questions"]), "tenant", today)

    row = await conn.fetchrow(f"select {_SELECT} from ref_question_sets where key = $1", key)
    if row is None:
        return None
    return _build(row, loads(row["questions"]), "platform", today)


def sections_from(question_set: QuestionSet) -> list[Section]:
    """One `Section` per question, in the funder's order.

    The model annotates these and writes to them; it cannot add, remove or
    reorder them, exactly as it cannot for a skeleton. The decision has moved
    into data, not to the model.
    """
    return [
        Section(
            key=q.id,
            title=q.text,
            guidance=q.guidance,
            uses_vault=q.uses_vault,
            limit=q.limit,
            limit_kind=q.limit_kind,
        )
        for q in question_set.ordered()
    ]


def queries_from(question_set: QuestionSet, subject: str) -> list[str]:
    """Vault queries for the questions that asked for evidence."""
    wanted = [q for q in question_set.ordered() if q.uses_vault][:MAX_QUESTION_QUERIES]
    return [f"{q.text} {subject}".strip() for q in wanted]


def warning_for(question_set: QuestionSet | None) -> str | None:
    """First-page warning when the form we are answering may not be the form
    the funder is asking.

    A question set is only as good as its last check, and the cost of it being
    wrong is specific: an answer written to a limit the funder has since
    changed does not paste. So the warning names the limit problem rather than
    saying something vague about staleness.
    """
    if question_set is None:
        return None
    if question_set.source == "tenant":
        return (
            f"These questions and limits come from your own copy of “{question_set.name}”, "
            "which has not been checked against the funder's current form."
        )
    if question_set.status != "open" or question_set.stale:
        return (
            f"The questions and character limits for “{question_set.name}” were last verified "
            f"{question_set.last_verified.isoformat()} and are past review — check them against "
            "the funder's current form before writing to them."
        )
    return None


def source_note_for(question_set: QuestionSet | None) -> list[str]:
    if question_set is None:
        return []
    origin = "your workspace's own copy" if question_set.source == "tenant" else "the catalogue"
    note = (
        f"Question set “{question_set.name}” ({question_set.funder}), from {origin}, "
        f"last verified {question_set.last_verified.isoformat()}."
    )
    if question_set.stale:
        note += " Warning: past its review date — confirm before relying on it."
    if question_set.source_url:
        note += f" Source: {question_set.source_url}"
    return [note]
