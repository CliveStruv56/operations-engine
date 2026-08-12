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
from typing import Any
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


class ClaimFacts(BaseModel):
    """One confirmed claim from the register, as a drafting prompt sees it.

    Lives here beside `VaultExcerpt` rather than in `worker/claims/facts.py`
    because the pack must not import from the loader that fills it — the
    shapes belong to the pack, the querying belongs to the module that reads
    the database.

    `chunk_id` is the load-bearing field: set only when the claim came from a
    vault document *and* that document's chunk is still there, and it is what
    decides whether the model is allowed to cite the fact. A register-sourced
    claim has no chunk, because Companies House is not a document in the
    vault, and minting a pseudo-chunk for one would misrepresent the evidence.
    """

    id: UUID
    kind: str
    label: str
    subject: str | None = None
    period: str | None = None
    statement: str
    #: The machine-readable form. What a 20-character "Charity number" box
    #: wants, where the statement is a sentence and will not fit.
    value: Any = None
    value_kind: str = "text"
    unit: str | None = None
    #: Whole-word tokens meaning a funder's question is asking for this fact.
    #: Carried per claim rather than as a separate catalogue on the pack: the
    #: pack is already the model's only fact source, and a second lookup table
    #: beside it is a second thing to keep in step.
    question_hints: list[str] = Field(default_factory=list)
    cardinality: str = "single"
    as_of: date | None = None
    expires_on: date | None = None
    source: str
    source_ref: str | None = None
    chunk_id: UUID | None = None
    last_verified: date | None = None
    next_review: date | None = None
    stale: bool = False
    expired: bool = False


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
    #: What the organisation asserts about itself. On the base rather than on
    #: either module's pack, deliberately: every vertical opens by saying who
    #: the organisation is, and a future module should inherit that for free.
    claims: list[ClaimFacts] = Field(default_factory=list)
    #: Vault chunks behind document-backed claims. The engine merges these
    #: into `excerpts` so the citation index resolves them with no change to
    #: `assemble.py` at all.
    claim_excerpts: list[VaultExcerpt] = Field(default_factory=list)

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

        Claims are excluded for the same reason with a sharper edge: they
        carry per-fact citation instructions that only make sense inside their
        own block, and only the handful of sections about the organisation
        itself need them. Serialised here they would ride into all eleven
        section prompts, telling the model to cite ids in sections whose
        excerpts do not contain them.
        """
        return json.dumps(
            self.model_dump(
                mode="json",
                exclude={"excerpts", "question_set", "claims", "claim_excerpts"},
            ),
            separators=(",", ":"),
        )
