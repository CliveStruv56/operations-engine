"""Grantwork's document skeletons.

Skeletons are fixed product decisions — the outline call annotates them, it
never chooses the sections. Prompt construction, the grounding contract and
the `[TO CONFIRM]` convention are shared (`worker/drafting/prompts.py`); what
belongs here is the sections, the domain sentence, and nothing else.

Every skeleton stays under the cost guard: sections + 1 outline call must not
exceed `MAX_LLM_CALLS` (15), which `test_every_skeleton_fits_the_call_budget`
asserts.
"""

from worker.drafting.prompts import grounding_prompt
from worker.drafting.sections import Section

GROUNDING_PROMPT = grounding_prompt(
    "a UK charity or community organisation applying for and reporting on grant funding"
)

SKELETONS: dict[str, list[Section]] = {
    # The anchor document most applications derive from. Heavily vault-
    # grounded: the need evidence and the beneficiary stories already exist in
    # the organisation's own documents, and citing them is the point.
    "case_for_support": [
        Section("org", "About the organisation", guidance="Purpose, history, governance."),
        Section("need", "The need we address", uses_vault=True),
        Section("beneficiaries", "Who benefits", uses_vault=True),
        Section("approach", "What we do about it", guidance="The work itself, in plain words."),
        Section("evidence", "Evidence that it works", uses_vault=True),
        Section("outcomes", "The difference we set out to make", table="impact"),
        Section("capacity", "Why this organisation", guidance="Track record and capability."),
        Section("support", "Community support", uses_vault=True),
    ],
    # Parameterised by the funder-catalogue row. If that row is unverified or
    # stale the pack's warning block lands on page one (ASSUMPTIONS #24).
    "funding_application": [
        Section("summary", "Summary of the request", guidance="What is asked for, and why."),
        Section("org", "The organisation and its governance"),
        Section("need", "Need and evidence", uses_vault=True),
        Section("project", "What the funding will pay for"),
        Section("outcomes", "Outcomes and how we will measure them", table="impact"),
        Section("delivery", "Delivery plan and timetable"),
        Section(
            "budget",
            "Budget and value for money",
            alias="reasoner",
            guidance="Reason about cost per outcome and full cost recovery from the data only.",
        ),
        Section("sustainability", "Sustainability beyond the grant"),
        Section("risks", "Risks and how they are managed"),
        Section("support", "Community support for the project", uses_vault=True),
    ],
    # The core loop: module data plus the period's recorded outcomes. No vault
    # retrieval at all — a monitoring return is an account of what this grant
    # did, and the facts for that are in the module's own rows.
    "monitoring_report": [
        Section("summary", "Summary of the period", guidance="Overall position in plain words."),
        Section("delivery", "What we delivered", guidance="Activity against the plan."),
        Section("outcomes", "Progress against outcomes", table="impact"),
        Section("beneficiaries", "Who we reached"),
        Section("variance", "Changes and variations", guidance="Anything the funder must know."),
        Section("conditions", "Grant conditions", table="conditions"),
        Section("finance", "Financial position", alias="reasoner"),
        Section("learning", "Learning and adjustments"),
        Section("next", "The period ahead"),
    ],
    # End of grant: aggregates every reporting period.
    "impact_evaluation": [
        Section("summary", "Executive summary"),
        Section("aims", "What the grant set out to achieve"),
        Section("delivered", "What was delivered"),
        Section("outcomes", "Outcomes achieved against targets", table="outcomes_history"),
        Section("beneficiaries", "Who benefited", uses_vault=True),
        Section("stories", "The difference made, in people's words", uses_vault=True),
        Section("learning", "What we learned"),
        Section("sustainability", "What happens now the grant has ended"),
        Section("conclusion", "Conclusion"),
    ],
}
