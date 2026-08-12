"""Reading a document for facts the organisation could assert.

Two things are worth testing here and they are not the prompt: what gets sent
to a model at all (the cost decision), and what survives the parser (the
honesty decision). The DB-touching `save_proposals` runs from the API suite.
"""

import json
from uuid import uuid4

from worker.claims.extract import (
    MIN_CHUNK_SCORE,
    KindSpec,
    ScorableChunk,
    parse_facts,
    rank_chunks,
)

ACCOUNTS = ScorableChunk(
    id=uuid4(),
    content=(
        "Statement of financial activities. Total income for the year was £847,000 "
        "and total expenditure was £792,000. The financial year end is 31 March 2026."
    ),
)

SITE_PLAN = ScorableChunk(
    id=uuid4(),
    content="Drawing 04 rev C. Proposed site layout, plots 1-14, scale 1:200.",
)

MEETING_NOTE = ScorableChunk(
    id=uuid4(),
    # Mentions "income" once, in passing, about somebody else entirely.
    content="Ade reported that the tenants' income levels vary across the estate.",
)

KINDS = [
    KindSpec(
        key="annual_income",
        label="Annual income",
        value_kind="money",
        cardinality="single",
        question_hints=["annual income", "income", "turnover"],
    ),
    KindSpec(
        key="annual_expenditure",
        label="Annual expenditure",
        value_kind="money",
        cardinality="single",
        question_hints=["expenditure", "annual spend"],
    ),
    KindSpec(
        key="accounts_year_end",
        label="Financial year end",
        value_kind="date",
        cardinality="single",
        question_hints=["financial year end", "year end"],
    ),
    KindSpec(
        key="accreditation",
        label="Accreditation",
        value_kind="text",
        cardinality="multi",
        question_hints=["accreditation", "cyber essentials", "iso"],
    ),
]


# -- the cost decision --------------------------------------------------------


def test_a_document_with_nothing_in_it_is_not_worth_a_model_call():
    """Most uploads are site plans, not accounts.

    Running a model over every one of them would put a per-upload charge on the
    whole vault to find facts in a tenth of it, which is the difference between
    a feature and a tax on uploading.
    """
    assert rank_chunks([SITE_PLAN], KINDS) == []


def test_one_passing_mention_is_not_enough():
    """ "Income" appears in a tenancy discussion. A single hint is too loose a
    trigger to spend a call on, and would fill the register with proposals
    about other people's finances."""
    assert MIN_CHUNK_SCORE > 1
    assert rank_chunks([MEETING_NOTE], KINDS) == []


def test_a_page_of_accounts_ranks_by_how_much_it_holds():
    ranked = rank_chunks([SITE_PLAN, ACCOUNTS, MEETING_NOTE], KINDS)
    assert [chunk.id for chunk, _ in ranked] == [ACCOUNTS.id]
    # income, expenditure and year end.
    assert ranked[0][1] == 3


def test_ranking_is_whole_word():
    """Same rule as pre-fill and the CRM, and wrong the same way if it were
    substring."""
    incomers = ScorableChunk(id=uuid4(), content="Newcomers and incomers to the village.")
    assert rank_chunks([incomers], KINDS) == []


# -- the honesty decision -----------------------------------------------------


def _reply(**overrides) -> str:
    entry = {
        "kind": "annual_income",
        "subject": None,
        "value": 847000,
        "period": "2025/26",
        "expires_on": None,
        "chunk_id": str(ACCOUNTS.id),
        "quote": "Total income for the year was £847,000",
        **overrides,
    }
    return json.dumps([entry])


KINDS_BY_KEY = {k.key: k for k in KINDS}
SUPPLIED = {str(ACCOUNTS.id): ACCOUNTS.content}


def test_a_well_formed_fact_survives():
    facts = parse_facts(_reply(), KINDS_BY_KEY, SUPPLIED)
    assert len(facts) == 1
    assert facts[0].kind == "annual_income"
    assert facts[0].value == 847000
    assert facts[0].period == "2025/26"
    assert facts[0].locator == str(ACCOUNTS.id)


def test_a_fact_pinned_to_a_chunk_we_never_sent_is_dropped():
    """A model that invents a chunk id has invented the evidence."""
    assert parse_facts(_reply(chunk_id=str(uuid4())), KINDS_BY_KEY, SUPPLIED) == []


def test_a_quote_that_is_not_in_the_chunk_is_dropped():
    """The check that matters most.

    A plausible figure pinned to a real chunk it did not come from is the
    failure that would be hardest to notice and worst to submit — and the one
    a prompt instruction alone would not stop.
    """
    invented = _reply(value=1_200_000, quote="Total income for the year was £1,200,000")
    assert parse_facts(invented, KINDS_BY_KEY, SUPPLIED) == []


def test_a_reflowed_quote_still_counts():
    """Models rejoin lines from a PDF table. Comparing raw text would reject
    honest quotes and teach us nothing about dishonest ones."""
    reflowed = _reply(quote="Total  income\n for the year\twas £847,000")
    assert len(parse_facts(reflowed, KINDS_BY_KEY, SUPPLIED)) == 1


def test_an_unquotable_fact_is_dropped():
    assert parse_facts(_reply(quote=""), KINDS_BY_KEY, SUPPLIED) == []


def test_a_kind_we_do_not_recognise_is_dropped():
    assert parse_facts(_reply(kind="vibes"), KINDS_BY_KEY, SUPPLIED) == []


def test_a_list_entry_with_nothing_naming_which_one_is_dropped():
    """ "The organisation holds {subject}" with no subject is not a fact."""
    reply = _reply(
        kind="accreditation",
        value="valid to 2027",
        subject=None,
        quote="Total income for the year was £847,000",
    )
    assert parse_facts(reply, KINDS_BY_KEY, SUPPLIED) == []


def test_a_subject_on_a_single_valued_kind_is_discarded_not_stored():
    facts = parse_facts(_reply(subject="Restricted funds"), KINDS_BY_KEY, SUPPLIED)
    assert len(facts) == 1 and facts[0].subject is None


def test_an_empty_array_is_a_perfectly_good_answer():
    """Expected for most documents, and must not read as a failure."""
    assert parse_facts("[]", KINDS_BY_KEY, SUPPLIED) == []


def test_a_fenced_reply_is_still_read():
    fenced = f"```json\n{_reply()}\n```"
    assert len(parse_facts(fenced, KINDS_BY_KEY, SUPPLIED)) == 1


def test_a_reply_that_is_not_json_degrades_to_nothing():
    """No proposals rather than an exception: extraction is best-effort and its
    absence must never fail an upload."""
    assert parse_facts("I could not find any facts, sorry!", KINDS_BY_KEY, SUPPLIED) == []
    assert parse_facts('{"kind": "annual_income"}', KINDS_BY_KEY, SUPPLIED) == []


# -- harvesting a submitted document ------------------------------------------


def _harvest_reply(**overrides) -> str:
    entry = {
        "kind": "accreditation",
        "subject": "Cyber Essentials Plus",
        "value": "held since 2024",
        "period": None,
        "expires_on": None,
        "question_id": "q7",
        "quote": "We have held Cyber Essentials Plus since 2024",
        **overrides,
    }
    return json.dumps([entry])


ANSWERS = {
    "q7": "We have held Cyber Essentials Plus since 2024 and renew it annually.",
    "q3": "The project will run for two years from April.",
}


def test_a_harvested_fact_is_checked_against_the_answer_it_came_from():
    """Same guards, different locator.

    A harvested fact still has to be quotable from an answer that was actually
    sent — the question id is the address instead of a chunk id, and nothing
    else about the honesty check changes.
    """
    facts = parse_facts(_harvest_reply(), KINDS_BY_KEY, ANSWERS, locator_key="question_id")
    assert len(facts) == 1
    assert facts[0].locator == "q7"
    assert facts[0].subject == "Cyber Essentials Plus"


def test_a_harvested_fact_quoting_an_answer_that_was_not_sent_is_dropped():
    reply = _harvest_reply(question_id="q99")
    assert parse_facts(reply, KINDS_BY_KEY, ANSWERS, locator_key="question_id") == []


def test_a_harvested_fact_quoting_the_wrong_answer_is_dropped():
    """The quote is real and the question id is real — they just do not go
    together. Exactly the failure a prompt instruction would not catch."""
    reply = _harvest_reply(question_id="q3")
    assert parse_facts(reply, KINDS_BY_KEY, ANSWERS, locator_key="question_id") == []
