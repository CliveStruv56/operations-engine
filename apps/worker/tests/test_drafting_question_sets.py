"""Offline tests for question-set drafting: call planning, answer parsing,
limit-aware prompting and the pre-flight budget guard.

The property worth guarding hardest is that none of this changes how an
existing document is drafted. A skeleton section carries no limit, and a
section with no limit is never batched — so `monthly_report` makes exactly the
calls it always made.
"""

from datetime import date
from uuid import uuid4

import pytest

from tests.test_drafts_context import _pack
from worker.drafting.assemble import assemble_docx
from worker.drafting.llm import MAX_LLM_CALLS, DraftBudgetExceeded
from worker.drafting.pack import VaultExcerpt
from worker.drafting.prompts import batch_prompt, parse_answers, section_prompt
from worker.drafting.questions import QuestionSet, warning_for
from worker.drafting.sections import (
    BATCH_MAX_CHARS,
    Section,
    check_call_budget,
    measure,
    plan_calls,
)
from worker.drafts.prompts import SKELETONS


def _q(key: str, limit: int | None = 500, **kw) -> Section:
    return Section(key=key, title=f"Question {key}?", limit=limit, **kw)


def test_existing_skeletons_are_never_batched():
    """The regression that would be invisible: batching a skeleton would
    change every drafted document's prose without changing a test."""
    for kind, sections in SKELETONS.items():
        batches = plan_calls(list(sections))
        assert [len(b) for b in batches] == [1] * len(sections), (
            f"{kind}: skeleton sections must each get their own call"
        )


def test_short_questions_share_a_call():
    batches = plan_calls([_q("q1", 200), _q("q2", 300), _q("q3", 250)])
    assert len(batches) == 1
    assert [s.key for s in batches[0]] == ["q1", "q2", "q3"]


def test_a_batch_stops_at_the_character_budget():
    # Four 1000-char questions: 3000 fits, the fourth starts a new batch.
    batches = plan_calls([_q(f"q{i}", 1000) for i in range(1, 5)])
    assert [len(b) for b in batches] == [3, 1]
    assert sum(s.limit for s in batches[0]) <= BATCH_MAX_CHARS


@pytest.mark.parametrize(
    "kwargs",
    [
        {"limit": 2000},  # too long to share
        {"limit": 400, "uses_vault": True},  # needs the excerpt block
        {"limit": 400, "table": "budget"},  # renders a data table after it
        {"limit": 400, "alias": "reasoner"},  # different model
        {"limit": None},  # a skeleton section
        {"limit": 400, "limit_kind": "words"},  # budget is in characters
    ],
)
def test_a_section_needing_its_own_call_gets_one(kwargs):
    batches = plan_calls([_q("a", 200), Section(key="b", title="B?", **kwargs), _q("c", 200)])
    assert [len(b) for b in batches] == [1, 1, 1]


def test_batching_preserves_order():
    sections = [_q(f"q{i}", 200) for i in range(1, 8)]
    batches = plan_calls(sections)
    flattened = [s.key for b in batches for s in b]
    assert flattened == [s.key for s in sections]


def test_a_form_too_long_to_draft_is_refused_before_spending_anything():
    sections = [_q(f"q{i}", 2000) for i in range(1, 31)]  # 30 solo calls
    batches = plan_calls(sections)
    with pytest.raises(DraftBudgetExceeded, match="more than one draft can cover"):
        check_call_budget(sections, batches)


def test_a_form_that_fits_is_allowed():
    sections = [_q(f"q{i}", 400) for i in range(1, 21)]  # batches to well under the cap
    batches = plan_calls(sections)
    assert len(batches) + 1 <= MAX_LLM_CALLS
    check_call_budget(sections, batches)  # does not raise


def test_measure_counts_in_the_sections_own_units():
    chars = Section(key="a", title="A?", limit=10)
    words = Section(key="b", title="B?", limit=2, limit_kind="words")
    assert measure("hello there", chars) == (11, 1)
    assert measure("hello there you", words) == (3, 1)
    assert measure("hi", chars) == (2, 0)


def test_measure_reports_no_overage_without_a_limit():
    assert measure("anything at all", Section(key="a", title="A?")) == (15, 0)


@pytest.mark.parametrize(
    "raw",
    [
        '{"q1": "one", "q2": "two"}',
        '```json\n{"q1": "one", "q2": "two"}\n```',
        '  {"q1": "one", "q2": "two"}  ',
    ],
)
def test_parse_answers_accepts_json_and_fences(raw):
    assert parse_answers(raw) == {"q1": "one", "q2": "two"}


@pytest.mark.parametrize("raw", ["not json", "", '["q1", "q2"]', '{"q1": {"nested": 1}}'])
def test_parse_answers_degrades_to_nothing_rather_than_guessing(raw):
    """An unusable reply must look empty to the caller, which retries the
    group and then fails the job. Half-parsing it would put a blank answer on
    a funder's form."""
    assert parse_answers(raw) == {}


def test_a_limited_section_is_told_its_limit_and_aims_under_it():
    _, user = section_prompt(_pack(), _q("q1", 2000), [], "system")
    assert "hard limit of 2000 characters" in user
    assert "about 1800 characters" in user, "the model must aim under the funder's ceiling"


def test_an_unlimited_section_keeps_the_old_instruction():
    _, user = section_prompt(_pack(), Section(key="s", title="Section"), [], "system")
    assert "Write 1-4 paragraphs. Prose only." in user
    assert "hard limit" not in user


def test_the_batch_prompt_carries_every_question_and_asks_for_json():
    batch = [_q("q1", 200), _q("q2", 300)]
    _, user = batch_prompt(_pack(), batch, {"q1": ["a note"]}, "system")
    assert "Question q1?" in user and "Question q2?" in user
    assert '"limit": 200' in user and '"limit": 300' in user
    assert "a note" in user
    assert "JSON object mapping each question key" in user


# -- the warning that rides on the draft's first page ------------------------


def _set(**kw) -> QuestionSet:
    base = dict(
        key="fund_eoi",
        name="Expression of interest",
        funder="A Trust",
        stage="eoi",
        status="open",
        last_verified=date(2026, 5, 1),
        next_review=date(2026, 11, 1),
        questions=[],
        source="platform",
        stale=False,
    )
    return QuestionSet(**{**base, **kw})


def test_a_verified_in_date_form_carries_no_warning():
    assert warning_for(_set()) is None
    assert warning_for(None) is None


def test_an_unverified_but_in_date_form_is_not_called_overdue():
    """Naming the wrong problem is worse than naming none — a consultant sent
    to check a review date that has not passed stops believing the banner."""
    note = warning_for(_set(status="unverified"))
    assert "have not been verified" in note
    assert "past review" not in note


def test_an_overdue_form_says_when_it_was_last_checked():
    note = warning_for(_set(stale=True))
    assert "2026-05-01" in note and "past review" in note


def test_a_form_that_is_both_says_both():
    note = warning_for(_set(status="unverified", stale=True))
    assert "never been verified" in note and "past review" in note


def test_a_tenants_own_copy_says_so_rather_than_claiming_we_checked_it():
    note = warning_for(_set(source="tenant"))
    assert "your own copy" in note


def test_the_warning_matches_the_one_the_ui_shows():
    """The banner on the draft's first page and the one above the answer sheet
    must not disagree about how far this form can be trusted. Mirrored in
    apps/web/lib/questions.ts::staleNote."""
    for kwargs in ({"status": "unverified"}, {"stale": True}, {"source": "tenant"}):
        assert warning_for(_set(**kwargs)), f"{kwargs}: the UI warns here and the draft does not"


# -- the answer sheet --------------------------------------------------------


def _excerpt(title: str = "Housing Need Survey") -> VaultExcerpt:
    return VaultExcerpt(
        chunk_id=uuid4(), document_id=uuid4(), title=title, page_start=4, content="evidence"
    )


def _sheet(sections: list[tuple[Section, str]], excerpts=None) -> list[dict]:
    pack = _pack(excerpts=excerpts or [])
    return assemble_docx(pack, sections, date(2026, 8, 11), answer_sheet=True).answers


def test_an_ordinary_document_gets_no_answer_sheet():
    """A feasibility study is read as a document. Offering per-section copy
    buttons for one would invite pasting a paragraph of it somewhere it does
    not belong."""
    pack = _pack()
    draft = assemble_docx(pack, [(_q("q1", 200), "Some prose.")], date(2026, 8, 11))
    assert draft.answers == []


def test_a_pasteable_answer_carries_no_citation_markers():
    """The load-bearing one. A form field has no References page behind it, so
    a "[1]" pasted into one asserts a source the assessor cannot follow."""
    excerpt = _excerpt()
    section = _q("q1", 2000, uses_vault=True)
    text = f"Local need is severe [c:{excerpt.chunk_id}]. The waiting list is long."
    (answer,) = _sheet([(section, text)], excerpts=[excerpt])

    assert "[c:" not in answer["text"], "raw markers must never reach the answer sheet"
    assert "[1]" not in answer["text"], "endnote numbers belong beside the answer, not in it"
    assert answer["text"] == "Local need is severe. The waiting list is long."
    assert [c["title"] for c in answer["citations"]] == ["Housing Need Survey"]


@pytest.mark.parametrize(
    "marker",
    [
        "[c:s1]",  # the one that actually reached a form, 11 Aug 2026
        "[c:source-1]",
        "[c: s1 ]",
        "【c:s1】",
        "[c:ref]",
        "[c:1]",
    ],
)
def test_a_fabricated_prefixed_citation_never_reaches_a_form_field(marker):
    """Found by the local end-to-end run, not by any unit test.

    The model invented `[c:s1]` on a project with an empty vault. `s` is not a
    hex digit, so the pattern did not match at all — the marker was neither
    resolved nor stripped, and sailed into the pasteable answer. The `c:`
    prefix is the model saying it meant a citation; whatever follows it is a
    citation attempt, and an unresolvable one is a hallucination.
    """
    (answer,) = _sheet([(_q("q1", 2000, uses_vault=True), f"Need is severe {marker}. It is.")])
    assert "c:" not in answer["text"]
    assert answer["text"] == "Need is severe. It is."


def test_prose_that_merely_looks_like_a_marker_survives():
    """The other half of the bargain: stripping a lookalike would silently
    delete the drafted words around it."""
    for prose in ("[c: see the note below]", "[42]", "[dead]", "[TBC]"):
        (answer,) = _sheet([(_q("q1", 2000), f"Section {prose} continues.")])
        assert prose in answer["text"], f"{prose} was eaten"


def test_an_answer_keeps_its_to_confirm_markers():
    """An answer with a hole in it should be uncomfortable to paste."""
    (answer,) = _sheet([(_q("q1", 500), "We served [TO CONFIRM: how many?] people.")])
    assert "[TO CONFIRM: how many?]" in answer["text"]
    assert answer["to_confirm"] == 1


def test_an_over_limit_answer_is_flagged_and_never_trimmed():
    """Cutting to fit would end the answer mid-sentence — the exact failure
    the truncation marker exists to make visible."""
    long_text = "word " * 100  # 500 chars
    (answer,) = _sheet([(_q("q1", 200), long_text)])
    assert answer["length"] > 200
    assert answer["over_by"] == answer["length"] - 200
    assert answer["text"].startswith("word word"), "the answer must survive intact"


def test_an_answer_within_its_limit_reports_no_overage():
    (answer,) = _sheet([(_q("q1", 500), "Short and sufficient.")])
    assert answer["over_by"] == 0
    assert answer["length"] == len("Short and sufficient.")


def test_citation_numbering_agrees_with_the_document():
    """Two answers citing two different sources must not both claim [1]."""
    first, second = _excerpt("Survey"), _excerpt("Local Plan")
    sections = [
        (_q("q1", 900, uses_vault=True), f"Need is high [c:{first.chunk_id}]."),
        (_q("q2", 900, uses_vault=True), f"Policy supports it [c:{second.chunk_id}]."),
    ]
    a, b = _sheet(sections, excerpts=[first, second])
    assert [c["n"] for c in a["citations"]] == [1]
    assert [c["n"] for c in b["citations"]] == [2]


def test_the_sheet_carries_what_the_ui_needs_to_show_a_count():
    (answer,) = _sheet([(_q("q1", 250), "An answer.")])
    assert answer["question_id"] == "q1"
    assert answer["question"] == "Question q1?"
    assert answer["limit"] == 250 and answer["limit_kind"] == "characters"
