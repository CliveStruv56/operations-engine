"""The contract a vertical module's context pack fulfils.

The drafting pipeline (gather → outline → sections → assemble → register) is
the same work whatever the document is: select the module's own records into
a typed pack, let the model write narrative over it, and render the numbers
as real tables from the records rather than from model output. Only the pack
differs between verticals.

`DraftPackBase` is that seam. Everything the engine needs from a pack that
is not a plain field is a hook with a sane default, so a new module overrides
the two or three that actually differ. Facts still come from the pack and
only from the pack — the grounding contract in `prompts.py` depends on it.
"""

import json
from datetime import date
from uuid import UUID

from pydantic import BaseModel, Field

from worker.drafting.questions import QuestionSet


class VaultExcerpt(BaseModel):
    """One retrieved vault chunk, in the core's citation format."""

    chunk_id: UUID
    document_id: UUID
    title: str
    page_start: int | None = None
    page_end: int | None = None
    content: str


class DraftPackBase(BaseModel):
    """Shared shape plus the hooks the engine calls.

    Subclasses add their own fact tables as ordinary pydantic fields; those
    are what `prompt_json()` serialises into the model's context.
    """

    kind: str
    generated_on: date
    excerpts: list[VaultExcerpt] = Field(default_factory=list)
    instructions: str | None = None
    #: The funder's form, when this draft is answering one. Set by the
    #: module's `gather`; `sections_for` turns it into the section list.
    question_set: QuestionSet | None = None

    # -- hooks ---------------------------------------------------------------

    def doc_title(self) -> str:
        """Title on the cover page and in every prompt. Instance documents
        (a specific month, a specific funder) qualify it here."""
        raise NotImplementedError

    def subject_lines(self) -> list[str]:
        """Cover-page lines identifying what the document is about — the
        client, the site, the organisation."""
        return []

    def prompt_notes(self) -> list[str]:
        """Lines added to every section prompt: the reporting period, client
        instructions, which funder a bid targets."""
        if self.instructions:
            return [f"Client instructions for this document: {self.instructions}"]
        return []

    def record_counts(self) -> dict[str, int]:
        """Feeds the Data sources appendix — what the draft was assembled
        from, so a reviewer can see the evidence base at a glance."""
        return {}

    def source_notes(self) -> list[str]:
        """Extra Data sources lines, e.g. reference-catalogue rows with their
        `last_verified` dates and a warning when they are stale."""
        return []

    def warning_block(self) -> str | None:
        """Bold first-page warning, e.g. a funding programme that was not open
        when its facts were last checked."""
        return None

    # -- shared --------------------------------------------------------------

    def prompt_json(self) -> str:
        """The pack as the model sees it.

        Excerpts are excluded: they carry their own citation-bearing block and
        would otherwise be duplicated. The question set likewise — every
        section prompt already names the question it is answering, and a form
        with twenty questions would otherwise be repeated in full twenty
        times, against a 24k-token ceiling per call.
        """
        return json.dumps(
            self.model_dump(mode="json", exclude={"excerpts", "question_set"}),
            separators=(",", ":"),
        )
