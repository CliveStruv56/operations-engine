"""Groundwork's document skeletons.

The skeletons are fixed product decisions — the outline call annotates them,
it never chooses the sections. Budget and funding figures render as real
tables at assembly; the LLM writes narrative connective tissue only.

Prompt construction, the grounding contract and the `[TO CONFIRM]` convention
are shared (`worker/drafting/prompts.py`); this module supplies the sections,
the domain sentence, and the thin wrappers that bind them together.
"""

from worker.drafting.pack import VaultExcerpt
from worker.drafting.prompts import excerpt_block, grounding_prompt, parse_outline
from worker.drafting.prompts import outline_prompt as _outline_prompt
from worker.drafting.prompts import section_prompt as _section_prompt
from worker.drafting.sections import Section
from worker.drafts.context import DOC_TITLES, ContextPack

__all__ = [
    "DOC_TITLES",
    "GROUNDING_PROMPT",
    "SKELETONS",
    "Section",
    "VaultExcerpt",
    "context_json",
    "excerpt_block",
    "outline_prompt",
    "parse_outline",
    "section_prompt",
]

GROUNDING_PROMPT = grounding_prompt("a community-led housing project in the UK")

SKELETONS: dict[str, list[Section]] = {
    "monthly_report": [
        Section("exec", "Executive summary and RAG", guidance="Overall position in plain words."),
        Section("programme", "Programme", guidance="Milestones done and at risk against dates."),
        Section("cost", "Cost report", table="budget", guidance="Comment on variances only."),
        Section("risks", "Risk summary", guidance="Top risks and what changed this period."),
        Section("planning", "Planning update", guidance="Applications and conditions status."),
        Section("contract", "Procurement and contract", guidance="From contract facts and tasks."),
        Section("funding", "Funding and drawdowns", table="funding"),
        Section("statutory", "Statutory compliance", guidance="Statutory-tagged task status."),
        Section(
            "decisions",
            "Decisions required",
            guidance="Open [TO CONFIRM] items and overdue milestones needing the client.",
        ),
        Section("next", "Next period", guidance="What happens next month."),
    ],
    "feasibility_study": [
        Section("intro", "Introduction and brief"),
        Section("site", "Site and context", uses_vault=True),
        Section("need", "Need and demand", uses_vault=True),
        Section("planning", "Planning context", uses_vault=True),
        Section("design", "Design and capacity assumptions"),
        Section("viability", "Cost and viability summary", alias="reasoner", table="budget"),
        Section("funding", "Funding strategy", table="funding"),
        Section("risks", "Risks"),
        Section("delivery", "Delivery route and programme"),
        Section("recommendations", "Recommendations and next steps"),
    ],
    "funding_bid": [
        Section("org", "Organisation and governance"),
        Section("project", "The project"),
        Section("need", "Need and community support", uses_vault=True),
        Section("use", "What the funding will pay for", table="budget"),
        Section("stack", "Full funding stack and match", table="funding"),
        Section("delivery", "Delivery plan and milestones"),
        Section("risks", "Risks and management"),
        Section("outcomes", "Outcomes and monitoring commitment"),
    ],
}


def context_json(pack: ContextPack) -> str:
    return pack.prompt_json()


def outline_prompt(pack: ContextPack) -> tuple[str, str]:
    return _outline_prompt(pack, SKELETONS[pack.kind], GROUNDING_PROMPT)


def section_prompt(pack: ContextPack, section: Section, notes: list[str]) -> tuple[str, str]:
    return _section_prompt(pack, section, notes, GROUNDING_PROMPT)
