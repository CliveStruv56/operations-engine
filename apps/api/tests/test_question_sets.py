"""Question-set reference data.

The guard that matters here is different from the funder catalogue's. That
one asserts a seeded row cannot *claim* to be verified. This one asserts the
fixture cannot carry a real funder's form at all.

The reason is that a question set's content is exact: the wording of a
question and the character limit on the field behind it. A recalled
eligibility summary is a prompt to go and check; a recalled character limit
is an answer that will not paste, discovered at the portal after the writing
is done. So real funders arrive by transcription with a `source_url`, and the
fixture is structurally incapable of shipping one.
"""

import json
from uuid import UUID, uuid4

import asyncpg
import pytest

from app.db import db
from app.errors import ApiError
from app.groundwork.seeds import seed_reference_data
from app.queue import ingest_queue
from app.refdata.seeds import FIXTURES, QUESTION_SET_FILE, SEED_STATUS, seed_question_sets
from app.refdata.transcribe import build_prompt, limits_in_source, parse_questions
from tests.conftest import APP_URL, OWNER_URL, auth, seed_tenant

VALID_LIMIT_KINDS = {"characters", "words"}
VALID_STAGES = {"eoi", "full", "monitoring"}


def _fixture() -> dict:
    return json.loads((FIXTURES / QUESTION_SET_FILE).read_text())


@pytest.fixture(scope="session")
async def question_set_ref_data(test_database):
    conn = await asyncpg.connect(OWNER_URL)
    try:
        await seed_question_sets(conn)
        # The drafting tests below set a project up first, which needs the
        # Groundwork template seeded. Both loaders upsert by key, so running
        # this alongside test_groundwork's own fixture is safe.
        await seed_reference_data(conn)
        # One curated-looking row so the staleness derivation has both sides.
        # `stale` is computed from next_review, never stored.
        await conn.execute(
            """
            insert into ref_question_sets (key, name, funder, stage, source_url, questions,
                                           status, last_verified, next_review)
            values ('stale_set', 'Stale Fund EOI', 'Test Trust', 'eoi',
                    'https://example.invalid/guidance',
                    '[{"id": "q1", "order": 1, "text": "Why?", "limit": 100}]'::jsonb,
                    'open', current_date - 200, current_date - 10)
            on conflict (key) do nothing
            """
        )
    finally:
        await conn.close()


def test_the_fixture_cannot_ship_a_real_funders_form():
    """The load-bearing guard.

    Nothing stops a future contributor pasting in question wording and limits
    they half-remember from a funder's website — except this. A fixture row
    may only be a template we authored, which means it may not name a real
    funder and may not carry a source_url, because a source_url is the mark
    of a transcription and transcriptions are an operator act against the
    database, not a code change.
    """
    rows = _fixture()["question_sets"]
    assert rows, "the question-set fixture is empty"
    for row in rows:
        assert row["status"] == SEED_STATUS, (
            f"{row['key']}: the fixture may only ship authored templates"
        )
        assert row["funder"] == "Flowgrid template", (
            f"{row['key']}: a fixture row may not name a real funder — "
            "transcribe it into the database with a source_url instead"
        )
        assert row["source_url"] is None, (
            f"{row['key']}: a source_url means this is a transcription, which does not "
            "belong in the fixture"
        )
        assert row["notes"], f"{row['key']}: a seeded row must say what it is"


def test_every_seeded_question_is_structurally_usable():
    """A malformed question breaks drafting at runtime, in the worker, on a
    tenant's job — long after anyone would connect it to this file."""
    for row in _fixture()["question_sets"]:
        assert row["stage"] in VALID_STAGES, f"{row['key']}: unknown stage {row['stage']}"
        questions = row["questions"]
        assert questions, f"{row['key']}: a question set with no questions"

        ids = [q["id"] for q in questions]
        assert len(ids) == len(set(ids)), f"{row['key']}: duplicate question ids"
        orders = [q["order"] for q in questions]
        assert orders == list(range(1, len(questions) + 1)), (
            f"{row['key']}: order must be contiguous from 1 — it drives the answer sheet"
        )
        for q in questions:
            assert q["text"].strip(), f"{row['key']}/{q['id']}: empty question text"
            assert q["limit_kind"] in VALID_LIMIT_KINDS, (
                f"{row['key']}/{q['id']}: unknown limit_kind {q['limit_kind']}"
            )
            assert isinstance(q["limit"], int) and q["limit"] > 0, (
                f"{row['key']}/{q['id']}: a limit must be a positive integer"
            )


async def test_the_catalogue_lists_for_any_workspace(client, question_set_ref_data):
    """Unflagged on purpose: a workspace with `projects` and one with `grants`
    both answer funders' forms."""
    tenant = await seed_tenant(client, "qslist")
    rows = (
        await client.get("/api/v1/question-sets", headers=auth(tenant.owner_id, tenant.id))
    ).json()
    keys = {r["key"] for r in rows}
    assert "generic_eoi_v1" in keys
    generic = next(r for r in rows if r["key"] == "generic_eoi_v1")
    assert generic["source"] == "platform"
    assert len(generic["questions"]) == 8
    assert generic["questions"][0]["limit"] == 200


async def test_a_tenants_own_set_replaces_the_platform_one(client, question_set_ref_data):
    """Two rows with the same key and different questions is a choice nobody
    can make correctly from a dropdown — so the tenant's wins outright."""
    tenant = await seed_tenant(client, "qsshadow")
    async with db.tenant_tx(tenant.owner_id, tenant.id) as conn:
        await conn.execute(
            """
            insert into tenant_question_sets (tenant_id, key, name, funder, stage, questions,
                                              status, last_verified, next_review)
            values ($1, 'generic_eoi_v1', 'Our corrected EOI', 'Real Trust', 'eoi',
                    '[{"id": "q1", "order": 1, "text": "Corrected?", "limit": 50}]'::jsonb,
                    'unverified', current_date, current_date + 90)
            """,
            tenant.id,
        )
    headers = auth(tenant.owner_id, tenant.id)
    rows = (await client.get("/api/v1/question-sets", headers=headers)).json()
    matching = [r for r in rows if r["key"] == "generic_eoi_v1"]
    assert len(matching) == 1, "the platform row must not appear beside the tenant's"
    assert matching[0]["source"] == "tenant"
    assert matching[0]["name"] == "Our corrected EOI"


async def test_an_unknown_set_is_not_found(client, question_set_ref_data):
    tenant = await seed_tenant(client, "qs404")
    resp = await client.get(
        "/api/v1/question-sets/no_such_form", headers=auth(tenant.owner_id, tenant.id)
    )
    assert resp.status_code == 404


async def test_staleness_is_derived_not_stored(client, question_set_ref_data):
    tenant = await seed_tenant(client, "qsstale")
    headers = auth(tenant.owner_id, tenant.id)
    row = (await client.get("/api/v1/question-sets/stale_set", headers=headers)).json()
    assert row["stale"] is True, "a set past its review date must badge"


async def test_the_catalogue_is_readable_in_a_tenant_context_and_not_writable(
    question_set_ref_data,
):
    """`ref_question_sets` follows `proj_ref_programmes`: every tenant reads
    it, no tenant writes it."""
    conn = await asyncpg.connect(APP_URL)
    try:
        count = await conn.fetchval("select count(*) from ref_question_sets")
        assert count > 0, "the runtime role cannot read the question-set catalogue"

        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await conn.execute(
                "insert into ref_question_sets (key, name, funder, questions,"
                " last_verified, next_review)"
                " values ('rogue', 'Rogue', 'Rogue', '[]'::jsonb, current_date, current_date)"
            )
    finally:
        await conn.close()


# -- drafting against a form -------------------------------------------------


@pytest.fixture
def fake_draft_queue(monkeypatch):
    """The route enqueues inside the transaction, so without this a submit
    rolls back and 503s on Redis rather than exercising the validation."""
    jobs = []

    async def enqueue(tenant_id, project_id, job_id, user_id):
        jobs.append((tenant_id, project_id, job_id, user_id))

    monkeypatch.setattr(ingest_queue, "enqueue_draft", enqueue)
    return jobs


async def _project(client, name="Form scheme"):
    tenant = await seed_tenant(client, name.replace(" ", "").lower()[:12])
    async with db.tenant_tx(tenant.owner_id, tenant.id) as conn:
        await conn.execute(
            """update tenants set features = features || '{"projects": true}' where id = $1""",
            tenant.id,
        )
    headers = auth(tenant.owner_id, tenant.id)
    core = await client.post("/api/v1/projects", json={"name": name}, headers=headers)
    assert core.status_code == 201, core.text
    project_id = core.json()["id"]
    setup = await client.post(f"/api/v1/projects/{project_id}/setup", json={}, headers=headers)
    assert setup.status_code == 201, setup.text
    return project_id, headers, tenant


async def test_an_application_form_draft_needs_a_form(client, question_set_ref_data):
    """A mistyped or missing key must fail here, not a minute later inside a
    worker job the user is watching a spinner for."""
    project_id, headers, _ = await _project(client, "Needs form")
    resp = await client.post(
        f"/api/v1/projects/{project_id}/drafts",
        json={"kind": "application_form"},
        headers=headers,
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "question_set_required"


async def test_an_unknown_form_is_refused_at_submit(client, question_set_ref_data):
    project_id, headers, _ = await _project(client, "Unknown form")
    resp = await client.post(
        f"/api/v1/projects/{project_id}/drafts",
        json={"kind": "application_form", "question_set_key": "no_such_form"},
        headers=headers,
    )
    assert resp.status_code == 404


async def test_two_different_forms_can_draft_at_once(
    client, question_set_ref_data, fake_draft_queue
):
    """The in-flight guard stops double clicks, not a consultant's week. Two
    funders asking different questions are two different documents."""
    project_id, headers, _ = await _project(client, "Two forms")
    first = await client.post(
        f"/api/v1/projects/{project_id}/drafts",
        json={"kind": "application_form", "question_set_key": "generic_eoi_v1"},
        headers=headers,
    )
    assert first.status_code == 202, first.text

    same = await client.post(
        f"/api/v1/projects/{project_id}/drafts",
        json={"kind": "application_form", "question_set_key": "generic_eoi_v1"},
        headers=headers,
    )
    assert same.status_code == 409, "the same form twice is a double click"

    other = await client.post(
        f"/api/v1/projects/{project_id}/drafts",
        json={"kind": "application_form", "question_set_key": "stale_set"},
        headers=headers,
    )
    assert other.status_code == 202, other.text


async def test_an_ordinary_draft_has_no_answer_sheet(
    client, question_set_ref_data, fake_draft_queue
):
    """A feasibility study is a document. Asking it for form answers is a 404
    with a sentence saying why, not an empty list."""
    project_id, headers, _ = await _project(client, "No sheet")
    job = await client.post(
        f"/api/v1/projects/{project_id}/drafts",
        json={"kind": "feasibility_study"},
        headers=headers,
    )
    assert job.status_code == 202, job.text
    resp = await client.get(f"/api/v1/projects/drafts/{job.json()['id']}/answers", headers=headers)
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "no_answer_sheet"


async def test_the_answer_sheet_leads_with_what_needs_attention(
    client, question_set_ref_data, fake_draft_queue
):
    """The counts exist so nobody has to scroll a twenty-question form to find
    the two answers that will not paste."""
    project_id, headers, tenant = await _project(client, "Sheet counts")
    job = await client.post(
        f"/api/v1/projects/{project_id}/drafts",
        json={"kind": "application_form", "question_set_key": "generic_eoi_v1"},
        headers=headers,
    )
    job_id = job.json()["id"]
    # Stand in for the worker: the sheet the engine would have written.
    async with db.tenant_tx(tenant.owner_id, tenant.id) as conn:
        await conn.execute(
            """
            update proj_draft_jobs set status = 'succeeded', answers = $2::jsonb where id = $1
            """,
            UUID(job_id),
            json.dumps(
                [
                    {
                        "question_id": "q1",
                        "question": "In one sentence, what is the project?",
                        "text": "A" * 260,
                        "limit": 200,
                        "limit_kind": "characters",
                        "length": 260,
                        "over_by": 60,
                        "to_confirm": 0,
                        "citations": [],
                    },
                    {
                        "question_id": "q2",
                        "question": "Who is the applicant organisation?",
                        "text": "A CLT [TO CONFIRM: registered number]",
                        "limit": 750,
                        "limit_kind": "characters",
                        "length": 37,
                        "over_by": 0,
                        "to_confirm": 1,
                        "citations": [],
                    },
                ]
            ),
        )
    sheet = (await client.get(f"/api/v1/projects/drafts/{job_id}/answers", headers=headers)).json()
    assert sheet["over_limit"] == 1
    assert sheet["to_confirm"] == 1
    assert sheet["question_set_key"] == "generic_eoi_v1"
    assert [a["question_id"] for a in sheet["answers"]] == ["q1", "q2"]


# -- transcription -----------------------------------------------------------


def test_a_limit_the_text_did_not_state_comes_back_null():
    """The rule the whole feature rests on.

    An invented character limit is the worst thing this can produce: it is
    silently wrong at the one moment nobody can check it, and the consultant
    finds out at the portal after the writing is done. A null is visible, and
    the review screen asks for it.
    """
    raw = json.dumps(
        {
            "questions": [
                {"text": "What is the project?", "limit": None},
                {"text": "Who are you?", "limit": "2000"},  # a string, not a number
                {"text": "Why?", "limit": 0},
                {"text": "How?", "limit": -5},
                {"text": "When?", "limit": 1500.5},
                {"text": "Where?", "limit": True},  # bool is an int in Python
            ]
        }
    )
    questions = parse_questions(raw)
    assert [q.limit for q in questions] == [None] * 6, (
        "anything we are not certain about must become a question for the human"
    )


def test_a_stated_limit_survives_with_its_units():
    raw = json.dumps(
        {
            "questions": [
                {"text": "Describe the need.", "limit": 2000, "limit_kind": "characters"},
                {"text": "Summarise.", "limit": 400, "limit_kind": "words"},
                {"text": "Odd units.", "limit": 100, "limit_kind": "furlongs"},
            ]
        }
    )
    questions = parse_questions(raw)
    assert [(q.limit, q.limit_kind) for q in questions] == [
        (2000, "characters"),
        (400, "words"),
        (100, "characters"),  # unknown units fall back rather than propagate
    ]


def test_transcription_numbers_questions_in_the_order_they_arrived():
    raw = json.dumps({"questions": [{"text": "A?"}, {"text": "B?"}, {"text": "C?"}]})
    questions = parse_questions(raw)
    assert [(q.id, q.order) for q in questions] == [("q1", 1), ("q2", 2), ("q3", 3)]


def test_blank_and_malformed_questions_are_dropped_not_guessed_at():
    raw = json.dumps(
        {"questions": [{"text": "Real?"}, {"text": "   "}, "not an object", {"guidance": "x"}]}
    )
    assert [q.text for q in parse_questions(raw)] == ["Real?"]


@pytest.mark.parametrize("raw", ["not json", "{}", '{"questions": "nope"}', ""])
def test_an_unreadable_reply_is_an_error_not_an_empty_set(raw):
    """Returning nothing would look like "this funder asks no questions",
    which a person would save."""
    with pytest.raises(ApiError) as exc:
        parse_questions(raw)
    assert exc.value.code == "transcription_failed"


def test_an_explicitly_empty_reply_is_allowed():
    assert parse_questions('{"questions": []}') == []


def test_the_source_is_scanned_for_limits_as_a_second_opinion():
    source = "Q1 (max 2000 characters). Q2 (250 words). Q3 no limit given."
    assert limits_in_source(source) == 2


def test_the_prompt_forbids_inventing_a_limit():
    """A regression on the wording, because it is the only thing standing
    between a plausible number and a funder's form."""
    system = build_prompt("x")[0]["content"]
    assert "NEVER invent a character or word limit" in system
    assert "return null" in system


# -- the write path ----------------------------------------------------------


def _set_body(**over) -> dict:
    body = {
        "key": "ahf_eoi",
        "name": "Expression of interest",
        "funder": "Architectural Heritage Fund",
        "stage": "eoi",
        "source_url": "https://ahfund.org.uk/grants/",
        "questions": [
            {"id": "q1", "order": 1, "text": "What is the building?", "limit": 500},
            {"id": "q2", "order": 2, "text": "Who owns it?", "limit": None},
        ],
    }
    body.update(over)
    return body


async def test_a_transcribed_set_arrives_unverified_and_says_so(client, question_set_ref_data):
    tenant = await seed_tenant(client, "qswrite")
    h = auth(tenant.owner_id, tenant.id)
    created = await client.post("/api/v1/question-sets", json=_set_body(), headers=h)
    assert created.status_code == 201, created.text
    row = created.json()
    assert row["source"] == "tenant"
    assert row["status"] == "unverified"
    assert row["stale"] is True, "a set nobody has checked is due for review immediately"
    assert [q["limit"] for q in row["questions"]] == [500, None]

    listed = (await client.get("/api/v1/question-sets", headers=h)).json()
    assert any(s["key"] == "ahf_eoi" for s in listed)


async def test_a_set_needs_somewhere_its_questions_came_from(client, question_set_ref_data):
    """A set with no source is one nobody can re-check, which is how a
    catalogue rots."""
    tenant = await seed_tenant(client, "qsnosrc")
    body = _set_body()
    del body["source_url"]
    resp = await client.post(
        "/api/v1/question-sets", json=body, headers=auth(tenant.owner_id, tenant.id)
    )
    assert resp.status_code == 422


async def test_the_same_key_twice_is_refused(client, question_set_ref_data):
    tenant = await seed_tenant(client, "qsdupe")
    h = auth(tenant.owner_id, tenant.id)
    assert (
        await client.post("/api/v1/question-sets", json=_set_body(), headers=h)
    ).status_code == 201
    again = await client.post("/api/v1/question-sets", json=_set_body(), headers=h)
    assert again.status_code == 409


async def test_two_questions_sharing_an_id_are_refused(client, question_set_ref_data):
    """A duplicate id silently loses an answer on the sheet."""
    tenant = await seed_tenant(client, "qsdupid")
    body = _set_body(
        questions=[
            {"id": "q1", "order": 1, "text": "A?", "limit": 100},
            {"id": "q1", "order": 2, "text": "B?", "limit": 100},
        ]
    )
    resp = await client.post(
        "/api/v1/question-sets", json=body, headers=auth(tenant.owner_id, tenant.id)
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "duplicate_question_id"


async def test_editing_renumbers_rather_than_leaving_a_gap(client, question_set_ref_data):
    """A gap in the order misnumbers every question after it on the form."""
    tenant = await seed_tenant(client, "qsrenum")
    h = auth(tenant.owner_id, tenant.id)
    await client.post("/api/v1/question-sets", json=_set_body(), headers=h)
    patched = await client.patch(
        "/api/v1/question-sets/ahf_eoi",
        json={
            "questions": [
                {"id": "q2", "order": 7, "text": "Who owns it?", "limit": 400},
                {"id": "q1", "order": 3, "text": "What is the building?", "limit": 500},
            ]
        },
        headers=h,
    )
    assert patched.status_code == 200, patched.text
    assert [(q["id"], q["order"]) for q in patched.json()["questions"]] == [("q1", 1), ("q2", 2)]


async def test_verifying_is_the_one_thing_that_moves_the_date(client, question_set_ref_data):
    tenant = await seed_tenant(client, "qsverify")
    h = auth(tenant.owner_id, tenant.id)
    await client.post("/api/v1/question-sets", json=_set_body(), headers=h)
    verified = (
        await client.patch("/api/v1/question-sets/ahf_eoi", json={"verified": True}, headers=h)
    ).json()
    assert verified["status"] == "open"
    assert verified["stale"] is False
    assert verified["next_review"] > verified["last_verified"]


async def test_a_tenant_cannot_edit_or_delete_the_platform_catalogue(client, question_set_ref_data):
    """The curated library is the operator's. A workspace that wants it
    different transcribes its own copy."""
    tenant = await seed_tenant(client, "qsplat")
    h = auth(tenant.owner_id, tenant.id)
    assert (
        await client.patch(
            "/api/v1/question-sets/generic_eoi_v1", json={"name": "Mine now"}, headers=h
        )
    ).status_code == 404
    assert (
        await client.delete("/api/v1/question-sets/generic_eoi_v1", headers=h)
    ).status_code == 404
    still = (await client.get("/api/v1/question-sets/generic_eoi_v1", headers=h)).json()
    assert still["name"] == "Expression of interest (generic)"


async def test_deleting_a_transcribed_set(client, question_set_ref_data):
    tenant = await seed_tenant(client, "qsdel")
    h = auth(tenant.owner_id, tenant.id)
    await client.post("/api/v1/question-sets", json=_set_body(), headers=h)
    assert (await client.delete("/api/v1/question-sets/ahf_eoi", headers=h)).status_code == 204
    assert (await client.get("/api/v1/question-sets/ahf_eoi", headers=h)).status_code == 404


# -- publishing to the platform catalogue ------------------------------------


def _operator() -> dict[str, str]:
    from tests.conftest import make_token

    return {"Authorization": f"Bearer {make_token(uuid4(), email='operator@example.com')}"}


async def _transcribed(client, slug: str, **over):
    """A workspace with one transcribed form, verified unless told otherwise."""
    tenant = await seed_tenant(client, slug)
    h = auth(tenant.owner_id, tenant.id)
    body = _set_body(key=f"form_{slug}", **over)
    created = await client.post("/api/v1/question-sets", json=body, headers=h)
    assert created.status_code == 201, created.text
    return tenant, h, body["key"]


#: Every limit recorded — the state a form has to reach before it can be
#: published. `_set_body`'s default deliberately leaves one blank.
COMPLETE = [
    {"id": "q1", "order": 1, "text": "What is the building?", "limit": 500},
    {"id": "q2", "order": 2, "text": "Who owns it?", "limit": 300},
]


async def test_publishing_puts_a_form_in_front_of_every_workspace(client, question_set_ref_data):
    tenant, h, key = await _transcribed(client, "promo1", questions=COMPLETE)
    await client.patch(f"/api/v1/question-sets/{key}", json={"verified": True}, headers=h)

    op = _operator()
    candidates = (await client.get("/api/v1/admin/question-sets/candidates", headers=op)).json()
    mine = next(c for c in candidates if c["key"] == key and c["tenant_id"] == str(tenant.id))
    assert mine["in_catalogue"] is False
    assert mine["tenant_name"]

    published = await client.post(
        "/api/v1/admin/question-sets/promote",
        json={"tenant_id": str(tenant.id), "key": key, "confirmed_against_source": True},
        headers=op,
    )
    assert published.status_code == 201, published.text
    assert published.json()["status"] == "open"
    assert published.json()["stale"] is False

    # A different workspace now sees it, with no "we have not checked" warning.
    other = await seed_tenant(client, "promo1b")
    seen = (
        await client.get(f"/api/v1/question-sets/{key}", headers=auth(other.owner_id, other.id))
    ).json()
    assert seen["source"] == "platform"
    assert seen["stale"] is False


async def test_an_unverified_form_cannot_be_published(client, question_set_ref_data):
    """Publishing one would put question wording and limits nobody has read
    against the funder's own form in front of every workspace — the seed
    fixture's rule arriving by a different door."""
    tenant, _, key = await _transcribed(client, "promo2")
    resp = await client.post(
        "/api/v1/admin/question-sets/promote",
        json={"tenant_id": str(tenant.id), "key": key, "confirmed_against_source": True},
        headers=_operator(),
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "source_unverified"


async def test_a_form_with_a_blank_limit_cannot_be_published(client, question_set_ref_data):
    """Blank is honest in a workspace's own copy, where whoever left it blank
    knows. Published, it is a silent gap in somebody else's draft."""
    tenant, h, key = await _transcribed(client, "promo3")  # q2 has limit null
    await client.patch(f"/api/v1/question-sets/{key}", json={"verified": True}, headers=h)
    resp = await client.post(
        "/api/v1/admin/question-sets/promote",
        json={"tenant_id": str(tenant.id), "key": key, "confirmed_against_source": True},
        headers=_operator(),
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "limits_missing"


async def test_the_operator_must_affirm_they_checked_it_too(client, question_set_ref_data):
    """A workspace verifying a form for itself is not the same act as making
    it everybody's."""
    tenant, h, key = await _transcribed(
        client,
        "promo4",
        questions=COMPLETE,
    )
    await client.patch(f"/api/v1/question-sets/{key}", json={"verified": True}, headers=h)
    resp = await client.post(
        "/api/v1/admin/question-sets/promote",
        json={"tenant_id": str(tenant.id), "key": key, "confirmed_against_source": False},
        headers=_operator(),
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "confirmation_required"


async def test_publishing_over_a_curated_form_needs_saying_so(client, question_set_ref_data):
    tenant, h, key = await _transcribed(
        client,
        "promo5",
        questions=COMPLETE,
    )
    await client.patch(f"/api/v1/question-sets/{key}", json={"verified": True}, headers=h)
    op = _operator()
    body = {"tenant_id": str(tenant.id), "key": key, "confirmed_against_source": True}
    assert (
        await client.post("/api/v1/admin/question-sets/promote", json=body, headers=op)
    ).status_code == 201

    clash = await client.post("/api/v1/admin/question-sets/promote", json=body, headers=op)
    assert clash.status_code == 409
    assert clash.json()["error"]["code"] == "already_published"

    replaced = await client.post(
        "/api/v1/admin/question-sets/promote", json={**body, "replace": True}, headers=op
    )
    assert replaced.status_code == 201


async def test_the_operator_catalogue_never_shows_a_workspaces_private_forms(
    client, question_set_ref_data
):
    """The console runs on the owner connection, where RLS does not bind —
    listing the wrong table there would hand the operator everyone's drafts."""
    tenant, _, key = await _transcribed(client, "promo6")
    catalogue = (await client.get("/api/v1/admin/question-sets", headers=_operator())).json()
    assert all(s["source"] == "platform" for s in catalogue)
    assert key not in {s["key"] for s in catalogue}


async def test_withdrawing_leaves_a_workspaces_own_copy_alone(client, question_set_ref_data):
    tenant, h, key = await _transcribed(
        client,
        "promo7",
        questions=COMPLETE,
    )
    await client.patch(f"/api/v1/question-sets/{key}", json={"verified": True}, headers=h)
    op = _operator()
    await client.post(
        "/api/v1/admin/question-sets/promote",
        json={"tenant_id": str(tenant.id), "key": key, "confirmed_against_source": True},
        headers=op,
    )
    assert (
        await client.delete(f"/api/v1/admin/question-sets/{key}", headers=op)
    ).status_code == 204
    # The workspace that transcribed it still has its own.
    still = (await client.get(f"/api/v1/question-sets/{key}", headers=h)).json()
    assert still["source"] == "tenant"


async def test_the_catalogue_is_operator_only(client, question_set_ref_data):
    tenant = await seed_tenant(client, "promo8")
    h = auth(tenant.owner_id, tenant.id)
    for method, path in (
        ("get", "/api/v1/admin/question-sets"),
        ("get", "/api/v1/admin/question-sets/candidates"),
        ("delete", "/api/v1/admin/question-sets/generic_eoi_v1"),
    ):
        resp = await getattr(client, method)(path, headers=h)
        assert resp.status_code == 403, f"{method} {path}"
    resp = await client.post(
        "/api/v1/admin/question-sets/promote",
        json={"tenant_id": str(tenant.id), "key": "x", "confirmed_against_source": True},
        headers=h,
    )
    assert resp.status_code == 403
