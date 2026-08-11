"""The Grantwork `grant_draft_document` arq task.

The pipeline is shared (`worker/drafting/engine.py`); everything here is
Grantwork's half of the `DraftModule` contract — where its job rows live, how
to gather an application's spine, what to ask the vault, and where a finished
draft lands in the bid-pack registry.
"""

from worker.drafting.engine import DraftModule, run_draft
from worker.drafting.questions import sections_from
from worker.drafting.sections import Section
from worker.grants.context import GrantPack, gather
from worker.grants.prompts import GROUNDING_PROMPT, SKELETONS
from worker.grants.register import register_draft
from worker.grants.retrieval import queries_for, scope_weights
from worker.grants.tables import TABLES


def _sections(kind: str, pack: GrantPack) -> list[Section]:
    if pack.question_set is None:
        raise ValueError(f"{kind}: no question set on the pack")
    return sections_from(pack.question_set)


GRANTWORK = DraftModule(
    storage_segment="grants",
    job_table="grant_draft_jobs",
    system_prompt=GROUNDING_PROMPT,
    skeletons=SKELETONS,
    tables=TABLES,
    gather=gather,
    queries_for=queries_for,
    scope_weights=scope_weights,
    register=register_draft,
    sections_for=_sections,
)


async def grant_draft_document(
    ctx: dict, tenant_id: str, application_id: str, job_id: str, user_id: str
) -> str:
    return await run_draft(GRANTWORK, ctx, tenant_id, application_id, job_id, user_id)
