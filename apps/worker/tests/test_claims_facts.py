"""The organisation's own facts, on their way into a draft.

Offline: the DB-touching `load_claims` is exercised from the API suite, which
has a migrated database (ASSUMPTIONS #13). What is tested here is everything
that decides what the model is *told* — which is where the damage would be.
"""

from datetime import date, timedelta
from uuid import uuid4

from worker.claims.facts import (
    claim_source_notes,
    claims_block,
    claims_warning,
    merge_excerpts,
)
from worker.drafting.llm import MAX_CONTEXT_TOKENS_PER_CALL
from worker.drafting.pack import ClaimFacts, VaultExcerpt
from worker.drafting.prompts import section_prompt
from worker.drafting.sections import Section, plan_calls
from worker.grants.context import ApplicationFacts, GrantPack

TODAY = date(2026, 8, 12)
SYSTEM = "system prompt"


def _claim(**overrides) -> ClaimFacts:
    return ClaimFacts(
        **{
            "kind": "registered_name",
            "label": "Registered name",
            "statement": "The organisation's registered name is Riverside Community Trust.",
            "source": "register",
            "source_ref": "https://register.example/1234567",
            "last_verified": date(2026, 6, 4),
            "next_review": date(2027, 6, 4),
            **overrides,
        }
    )


def _pack(**overrides) -> GrantPack:
    base = {
        "kind": "case_for_support",
        "generated_on": TODAY,
        "application": ApplicationFacts(
            id=uuid4(),
            title="Community garden project",
            application_type="project_grant",
            stage_current="draft",
            status="drafting",
        ),
    }
    return GrantPack(**{**base, **overrides})


# -- what the model is told about each fact ----------------------------------


def test_a_document_backed_claim_is_citable_and_a_register_one_is_not():
    """The distinction the whole citation story rests on.

    A claim read from an uploaded document names a real `doc_chunks` row, so it
    cites like any vault fact. A register claim has no chunk — Companies House
    is not a document in the vault — and telling the model to cite one would
    either invent evidence or mint a marker that gets stripped.
    """
    chunk_id = uuid4()
    block = claims_block(
        [
            _claim(
                kind="annual_income",
                statement="The organisation's annual income was £847,000.",
                source="document",
                source_ref=None,
                chunk_id=chunk_id,
            ),
            _claim(),
        ]
    )
    assert f"cite as [c:{chunk_id}]" in block
    assert "from the public register — do not cite" in block


def test_a_claim_whose_document_vanished_is_not_citable():
    """`load_claims` clears `chunk_id` when the chunk did not come back.

    A deleted document leaves the fact standing but unevidenced, and telling
    the model to cite an id that is not in the excerpts is exactly how stripped
    citation markers happen.
    """
    block = claims_block([_claim(source="document", source_ref=None, chunk_id=None)])
    assert "cite" in block  # it still says something about citing…
    assert "do not cite" in block  # …and that something is "don't"


def test_an_expired_claim_is_marked_inline_not_only_on_the_first_page():
    """A reader may never see the warning; the model must not assert it either."""
    lapsed = TODAY - timedelta(days=30)
    block = claims_block(
        [
            _claim(
                kind="insurance_policy",
                subject="Public liability",
                statement="The organisation holds Public liability cover of £5,000,000.",
                expires_on=lapsed,
                expired=True,
            )
        ]
    )
    assert f"EXPIRED {lapsed.isoformat()}" in block


def test_a_period_and_an_as_of_date_qualify_the_fact():
    block = claims_block(
        [
            _claim(
                kind="annual_income",
                statement="The organisation's annual income was £210,000.",
                period="2024/25",
                as_of=date(2025, 3, 31),
            )
        ]
    )
    assert "2024/25" in block
    assert "as at 2025-03-31" in block


# -- which sections get them --------------------------------------------------


def test_only_a_claims_section_receives_the_block():
    pack = _pack(claims=[_claim()])
    _, with_claims = section_prompt(
        pack, Section("org", "About the organisation", uses_claims=True), [], SYSTEM
    )
    _, without = section_prompt(pack, Section("need", "The need we address"), [], SYSTEM)

    assert "<organisation-claims>" in with_claims
    assert "Riverside Community Trust" in with_claims
    assert "<organisation-claims>" not in without
    # And the facts must not leak in through the shared data JSON either.
    assert "Riverside Community Trust" not in without


def test_a_claims_section_with_an_empty_register_is_told_to_mark_gaps():
    """The state every workspace is in before it looks a register up.

    It must not become a licence to describe the organisation from general
    knowledge — that is the invention this whole feature exists to stop.
    """
    _, prompt = section_prompt(
        _pack(claims=[]), Section("org", "About the organisation", uses_claims=True), [], SYSTEM
    )
    assert "<organisation-claims>" not in prompt
    assert "TO CONFIRM" in prompt
    assert "Do not invent" in prompt


def test_claims_are_excluded_from_the_shared_project_json():
    """They carry per-fact citation instructions that only make sense in their
    own block, and serialising them would ride them into all eleven section
    prompts against a 24k ceiling."""
    pack = _pack(claims=[_claim()], claim_excerpts=[])
    assert "Riverside Community Trust" not in pack.prompt_json()
    assert "claims" not in pack.prompt_json()


def test_a_claims_section_is_never_batched():
    """The batched prompt carries only the shared project data.

    A short form question marked as needing the register would otherwise be
    grouped with its neighbours and answer "who are you" from nothing.
    """
    sections = [
        Section("q1", "Project in one sentence", limit=200),
        Section("q2", "Who is the applicant organisation?", limit=750, uses_claims=True),
        Section("q3", "What will the funding pay for?", limit=200),
    ]
    batches = plan_calls(sections)
    assert [len(b) for b in batches] == [1, 1, 1]
    assert batches[1][0].key == "q2"


# -- the first-page warning ---------------------------------------------------


def test_no_warning_when_every_fact_is_in_date():
    assert claims_warning([_claim(), _claim(kind="charity_number")]) is None


def test_an_expired_fact_leads_the_warning_and_names_the_date():
    lapsed = TODAY - timedelta(days=30)
    warning = claims_warning(
        [
            _claim(kind="policy", stale=True),
            _claim(
                kind="insurance_policy",
                statement="The organisation holds Public liability cover of £5,000,000.",
                expires_on=lapsed,
                expired=True,
            ),
        ]
    )
    assert warning is not None
    assert lapsed.isoformat() in warning
    assert "Public liability" in warning
    assert warning.endswith("Check before submitting.")


def test_a_stale_fact_warns_with_the_date_it_was_last_checked():
    warning = claims_warning([_claim(stale=True, last_verified=date(2025, 1, 9))])
    assert warning is not None
    assert "2025-01-09" in warning
    assert "past review" in warning


def test_the_warning_counts_only_the_facts_that_are_a_problem():
    """Warning because a workspace holds eighty facts would put a warning on
    every draft, and a warning that is always there is not read."""
    healthy = [_claim(kind=f"kind_{i}") for i in range(40)]
    assert claims_warning(healthy) is None
    assert claims_warning([*healthy, _claim(kind="late", stale=True)]) is not None


def test_the_warning_joins_the_module_warning_rather_than_replacing_it():
    """Two independent problems, one bold paragraph.

    A form that may be out of date and a fact that has lapsed are different
    failures, and dropping either would be worse than a longer warning.
    """
    pack = _pack(
        kind="funding_application",
        claims=[_claim(stale=True)],
        catalogue={
            "key": "example",
            "name": "Example fund",
            "funder": "Example Trust",
            "kind": "trust",
            "eligibility": "Open to charities.",
            "status": "unverified",
            "last_verified": date(2026, 1, 1),
            "next_review": date(2026, 4, 1),
            "stale": True,
        },
    )
    warning = pack.warning_block()
    assert warning is not None
    assert "Example fund" in warning
    assert "past review" in warning


# -- provenance ---------------------------------------------------------------


def test_register_facts_are_attributed_once_per_register():
    """Also the Open Government Licence attribution, which is why it names the
    URL rather than just counting."""
    notes = claim_source_notes(
        [
            _claim(kind="registered_name"),
            _claim(kind="charity_number"),
            _claim(kind="annual_income", source="document", source_ref=None, chunk_id=uuid4()),
        ]
    )
    assert len(notes) == 1
    assert "2 organisational fact(s)" in notes[0]
    assert "https://register.example/1234567" in notes[0]


def test_document_backed_claims_are_not_repeated_in_the_data_sources():
    """Their chunk is in the excerpts, so they already appear by number on the
    References page. Naming them twice would read as two sources."""
    assert claim_source_notes([_claim(source="document", source_ref=None, chunk_id=uuid4())]) == []


# -- merging into the citation index ------------------------------------------


def _excerpt(chunk_id=None) -> VaultExcerpt:
    return VaultExcerpt(
        chunk_id=chunk_id or uuid4(),
        document_id=uuid4(),
        title="Annual accounts 2025-26",
        content="Total income for the year was £847,000.",
    )


def test_claim_evidence_joins_the_excerpts_without_duplicating():
    """A chunk both retrieved for a section and cited by a claim must appear
    once, or the model sees the same id twice with different framing."""
    shared = _excerpt()
    retrieved = [shared, _excerpt()]
    merged = merge_excerpts(retrieved, [shared, _excerpt()])
    assert len(merged) == 3
    assert len({e.chunk_id for e in merged}) == 3


def test_merging_keeps_retrieved_excerpts_first():
    retrieved = [_excerpt()]
    extra = [_excerpt()]
    assert merge_excerpts(retrieved, extra)[0].chunk_id == retrieved[0].chunk_id


# -- the context ceiling ------------------------------------------------------


def test_a_full_register_still_fits_in_one_section_call():
    """Eighty facts is the top of the expected range, and the org section is
    the one that gets all of them plus its evidence."""
    claims = [
        _claim(
            kind=f"kind_{i}",
            subject=f"Subject {i}",
            statement=f"The organisation asserts fact number {i}, which runs to some length.",
        )
        for i in range(80)
    ]
    pack = _pack(claims=claims, excerpts=[_excerpt() for _ in range(8)])
    _, prompt = section_prompt(
        pack,
        Section("org", "About the organisation", uses_claims=True, uses_vault=True),
        ["A note"],
        SYSTEM,
    )
    estimated_tokens = len(prompt) // 4 + 1
    assert estimated_tokens < MAX_CONTEXT_TOKENS_PER_CALL
