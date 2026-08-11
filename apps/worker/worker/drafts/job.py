"""The Groundwork `draft_document` arq task.

The pipeline itself is shared (`worker/drafting/engine.py`); everything
below is the Groundwork half of the contract — where its job rows live, how
to gather a project's spine, which questions to ask the vault, and how a
finished draft lands in the project's document registry.
"""

from worker.drafting.engine import DraftModule, run_draft
from worker.drafting.questions import queries_from, sections_from
from worker.drafting.sections import Section
from worker.drafts.assemble import TABLES
from worker.drafts.context import ContextPack, gather
from worker.drafts.prompts import GROUNDING_PROMPT, SKELETONS
from worker.drafts.register import register_draft
from worker.drafts.retrieval import queries_for as _queries_for
from worker.drafts.retrieval import scope_weights


def _subject(pack: ContextPack) -> str:
    return pack.project.site_address or pack.project.name


def _queries(kind: str, pack: ContextPack) -> list[str]:
    """Site-specific arms interpolate the address, falling back to the
    project name when no site has been recorded yet."""
    if kind == "application_form" and pack.question_set is not None:
        return queries_from(pack.question_set, _subject(pack))
    return _queries_for(kind, _subject(pack))


def _sections(kind: str, pack: ContextPack) -> list[Section]:
    if pack.question_set is None:
        raise ValueError(f"{kind}: no question set on the pack")
    return sections_from(pack.question_set)


GROUNDWORK = DraftModule(
    storage_segment="projects",
    job_table="proj_draft_jobs",
    system_prompt=GROUNDING_PROMPT,
    skeletons=SKELETONS,
    tables=TABLES,
    gather=gather,
    queries_for=_queries,
    scope_weights=scope_weights,
    register=register_draft,
    sections_for=_sections,
)


async def draft_document(
    ctx: dict, tenant_id: str, project_id: str, job_id: str, user_id: str
) -> str:
    return await run_draft(GROUNDWORK, ctx, tenant_id, project_id, job_id, user_id)
