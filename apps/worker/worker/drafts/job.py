"""The Groundwork `draft_document` arq task.

The pipeline itself is shared (`worker/drafting/engine.py`); everything
below is the Groundwork half of the contract — where its job rows live, how
to gather a project's spine, which questions to ask the vault, and how a
finished draft lands in the project's document registry.
"""

from worker.drafting.engine import DraftModule, run_draft
from worker.drafts.assemble import TABLES
from worker.drafts.context import ContextPack, gather
from worker.drafts.prompts import GROUNDING_PROMPT, SKELETONS
from worker.drafts.register import register_draft
from worker.drafts.retrieval import queries_for as _queries_for
from worker.drafts.retrieval import scope_weights


def _queries(kind: str, pack: ContextPack) -> list[str]:
    """Site-specific arms interpolate the address, falling back to the
    project name when no site has been recorded yet."""
    return _queries_for(kind, pack.project.site_address or pack.project.name)


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
)


async def draft_document(
    ctx: dict, tenant_id: str, project_id: str, job_id: str, user_id: str
) -> str:
    return await run_draft(GROUNDWORK, ctx, tenant_id, project_id, job_id, user_id)
