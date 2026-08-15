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
    render_statement,
)
from worker.drafting.assemble import assemble_docx
from worker.drafting.llm import MAX_CONTEXT_TOKENS_PER_CALL
from worker.drafting.pack import ClaimFacts, VaultExcerpt
from worker.drafting.prefill import (
    match_claims,
    partition_prefilled,
    prefill_answer,
    restore_order,
)
from worker.drafting.prompts import section_prompt
from worker.drafting.sections import Section, plan_calls
from worker.grants.context import ApplicationFacts, GrantPack

TODAY = date(2026, 8, 12)
SYSTEM = "system prompt"


def _claim(**overrides) -> ClaimFacts:
    return ClaimFacts(
        **{
            "id": uuid4(),
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


def test_render_statement_writes_dates_in_words():
    """"due 15 September 2026", never "due 2026-09-15" — matching the API and
    web renderers, per this module's drift warning."""
    tmpl = "The organisation's next confirmation statement is due {value}."
    label = "Confirmation statement due"
    expected = "The organisation's next confirmation statement is due 15 September 2026."
    assert render_statement(tmpl, label, None, date(2026, 9, 15), "date") == expected
    assert render_statement(tmpl, label, None, "2026-09-15", "date") == expected
    # A date-kind value that is not a date must not crash the sentence.
    assert "not recorded" in render_statement(tmpl, label, None, "not recorded", "date")


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


# -- pre-fill: answering from the register with no model call ------------------


def _hinted(**overrides) -> ClaimFacts:
    """A claim carrying its kind's question hints, as `load_claims` builds it."""
    base = {
        "kind": "charity_number",
        "label": "Charity number",
        "statement": "The organisation is a registered charity, number 1234567.",
        "value": "1234567",
        "value_kind": "text",
        "question_hints": [
            "charity number",
            "charity registration",
            "registered charity",
            "applicant organisation",
        ],
    }
    return _claim(**{**base, **overrides})


def test_the_size_of_the_box_decides_what_the_answer_looks_like():
    """A twenty-character "Charity number" field wants 1234567, not a sentence.

    A hundred-character one wants the sentence — a bare number dropped into a
    field that size reads as an unanswered question.
    """
    claims = [_hinted()]
    tiny = prefill_answer(Section("q", "Charity number", limit=20), claims)
    roomy = prefill_answer(Section("q", "Charity number", limit=100), claims)

    assert tiny is not None and tiny[0] == "1234567"
    assert roomy is not None and roomy[0].startswith("The organisation is a registered charity")


def test_a_prose_sized_box_is_never_answered_outright():
    """The failure this rule exists to stop.

    "Who is the applicant organisation, and what is its legal form?" at 750
    characters wants the name, the structure, the founding date and the
    purpose. A one-line charity number fits the box, passes every other check,
    and answers a different question from the one asked — so the size of the
    field is taken as the funder saying they want prose.
    """
    section = Section("q", "Who is the applicant organisation?", limit=750)
    assert prefill_answer(section, [_hinted()]) is None


def test_a_skeleton_section_is_never_answered_outright():
    """No limit at all means a document section, not a form field."""
    assert prefill_answer(Section("org", "Organisation and governance"), [_hinted()]) is None


def test_an_answer_that_would_not_fit_is_left_to_the_model():
    """The limit is the funder's and their portal truncates at it.

    Handing over something that gets cut mid-word is worse than drafting to the
    limit properly.
    """
    long_claim = _hinted(
        statement="The organisation is a registered charity, " + "number " * 40,
        value=None,
    )
    assert prefill_answer(Section("q", "Charity number", limit=30), [long_claim]) is None


def test_matching_is_whole_word_not_substring():
    """`app/crm/lookup.py` records why in blood: a substring lookup for "SAM"
    matched "Samantha Fry" and put her home address in a prompt."""
    claims = [_hinted(question_hints=["income"])]
    assert match_claims("What is your income?", claims)
    assert match_claims("Tell us about incomers to the area", claims) == []


def test_a_question_spanning_two_facts_is_not_auto_filled():
    """ "Your income and expenditure" is not a lookup, and picking one of the
    two would answer a different question from the one asked."""
    claims = [
        _hinted(kind="annual_income", question_hints=["income"], value=847000.0),
        _hinted(kind="annual_expenditure", question_hints=["expenditure"], value=792000.0),
    ]
    assert prefill_answer(Section("q", "Your income and expenditure", limit=40), claims) is None


def test_a_vault_question_is_never_auto_filled():
    """A question asking for evidence wants an argument, not a fact."""
    section = Section("q", "What is your charity number?", limit=750, uses_vault=True)
    assert prefill_answer(section, [_hinted()]) is None


def test_an_expired_fact_is_never_auto_filled():
    """The draft would look complete and be wrong, which is the one outcome
    worse than a gap."""
    lapsed = _hinted(
        kind="insurance_policy",
        question_hints=["insurance"],
        value=5000000.0,
        value_kind="money",
        expires_on=TODAY - timedelta(days=1),
        expired=True,
    )
    assert prefill_answer(Section("q", "Insurance cover", limit=30), [lapsed]) is None


def test_money_does_not_arrive_as_a_float_string():
    """jsonb hands income back as 847000.0, and nobody writes that on a form."""
    claim = _hinted(
        kind="annual_income", question_hints=["income"], value=847000.0, value_kind="money"
    )
    answer = prefill_answer(Section("q", "Annual income", limit=20), [claim])
    assert answer is not None and answer[0] == "847000"


def test_partition_splits_the_form_and_marks_the_rest_for_the_facts():
    """The two tiers, on one form.

    q1 is a lookup and never reaches a model. q2 is prose about the
    organisation, so it drafts *with* the facts rather than from nothing. q3 is
    about the project and is untouched.
    """
    pack = _pack(claims=[_hinted()])
    spec = [
        Section("q1", "Charity number", limit=20),
        Section("q2", "Who is the applicant organisation?", limit=750),
        Section("q3", "What will the funding pay for?", limit=1500),
    ]
    prefilled, to_draft, claim_ids = partition_prefilled(spec, pack)

    assert [s.key for s, _ in prefilled] == ["q1"]
    assert prefilled[0][1] == "1234567"
    assert [s.key for s in to_draft] == ["q2", "q3"]

    by_key = {s.key: s for s in to_draft}
    assert by_key["q2"].uses_claims is True  # tier B: drafts with the facts
    assert by_key["q3"].uses_claims is False  # nothing to do with the organisation
    assert claim_ids["q1"] and claim_ids["q2"]
    assert "q3" not in claim_ids


def test_prefilled_questions_do_not_count_against_the_call_budget():
    """The saving, stated as a test.

    A form the register can half-answer makes half the calls — and a long form
    that previously refused to draft may now fit under MAX_LLM_CALLS.
    """
    pack = _pack(claims=[_hinted()])
    spec = [Section("q1", "Charity number", limit=20)] + [
        Section(f"q{i}", f"Question {i}", limit=1500) for i in range(2, 6)
    ]
    _, to_draft, _ = partition_prefilled(spec, pack)
    assert len(plan_calls(to_draft)) < len(plan_calls(spec))


def test_answers_go_back_into_the_funders_order():
    """The two halves finish separately, and a sheet whose answers do not line
    up with its questions is unusable."""
    spec = [Section(f"q{i}", f"Question {i}") for i in range(1, 5)]
    drafted = [(spec[1], "second"), (spec[3], "fourth")]
    prefilled = [(spec[0], "first"), (spec[2], "third")]
    assert [s.key for s, _ in restore_order(spec, drafted, prefilled)] == ["q1", "q2", "q3", "q4"]


def test_the_answer_sheet_says_where_each_answer_came_from():
    """Three states, and the middle one matters: the register supplied the
    facts but a model wrote the sentences, and calling that "from your
    register" would overclaim."""
    pack = _pack(kind="application_form", claims=[_hinted()])
    spec = [
        Section("q1", "Charity number", limit=20),
        Section("q2", "Who is the applicant organisation?", limit=750),
        Section("q3", "What will the funding pay for?", limit=1500),
    ]
    prefilled, to_draft, claim_ids = partition_prefilled(spec, pack)
    drafted = [(s, "Drafted prose.") for s in to_draft]

    result = assemble_docx(
        pack,
        restore_order(spec, drafted, prefilled),
        TODAY,
        answer_sheet=True,
        prefilled_keys={s.key for s, _ in prefilled},
        claim_ids=claim_ids,
    )
    origins = {a["question_id"]: a["origin"] for a in result.answers}
    assert origins == {"q1": "claim", "q2": "claim_assisted", "q3": "drafted"}

    answered = next(a for a in result.answers if a["question_id"] == "q1")
    assert answered["text"] == "1234567"
    assert answered["claim_ids"] == claim_ids["q1"]
