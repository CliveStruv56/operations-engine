"""Slice 4 retrieval: RRF fusion + scope hook, hybrid SQL under RLS,
citation resolution, the chat citation contract, and /vault/search."""

import json
from uuid import UUID, uuid4

import pytest

from app.db import db
from app.litellm import litellm_client
from app.retrieval import RetrievedChunk, Scope, fuse, retrieve
from app.routers.conversations import _resolve_citations
from tests.conftest import auth, seed_tenant
from tests.test_chat import enable_llm_key, parse_sse

DIM = 2048


def _vec(hot: int) -> list[float]:
    v = [0.0] * DIM
    v[hot] = 1.0
    return v


def _chunk(doc_id=None, cid=None, content="text", title="Doc") -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=cid or uuid4(),
        document_id=doc_id or uuid4(),
        title=title,
        heading_path=[],
        page_start=1,
        page_end=2,
        content=content,
    )


# -- fusion ------------------------------------------------------------------


def test_fuse_prefers_chunks_in_both_lists():
    both = _chunk()
    vec_only = _chunk()
    txt_only = _chunk()
    fused = fuse([[vec_only, both], [both, txt_only]])
    assert fused[0].chunk_id == both.chunk_id


def test_fuse_weight_hook_reorders():
    a, b = _chunk(), _chunk()
    baseline = fuse([[a, b], [a, b]])
    assert baseline[0].chunk_id == a.chunk_id
    a2, b2 = (
        _chunk(doc_id=a.document_id, cid=a.chunk_id),
        _chunk(doc_id=b.document_id, cid=b.chunk_id),
    )
    boosted = fuse([[a2, b2], [a2, b2]], scope=Scope(weights={b.document_id: 3.0}))
    assert boosted[0].chunk_id == b.chunk_id


def test_fuse_caps_at_top_n():
    chunks = [_chunk() for _ in range(12)]
    assert len(fuse([chunks])) == 8


# -- citation resolution -----------------------------------------------------


def test_resolve_citations_numbers_and_dedupes():
    c1, c2 = _chunk(title="Handbook"), _chunk(title="Prices")
    text = (
        f"Leave is 25 days [c:{c1.chunk_id}]. Also [c:{c2.chunk_id}] and again [c:{c1.chunk_id}]."
    )
    content, citations = _resolve_citations(text, [c1, c2])
    assert content == "Leave is 25 days [1]. Also [2] and again [1]."
    assert [c["n"] for c in citations] == [1, 2]
    assert citations[0]["title"] == "Handbook"
    assert citations[0]["chunk_id"] == str(c1.chunk_id)
    assert citations[0]["snippet"]


def test_resolve_citations_drops_hallucinated_ids():
    real = _chunk()
    text = f"True [c:{real.chunk_id}] but fake [c:{uuid4()}]."
    content, citations = _resolve_citations(text, [real])
    assert content == "True [1] but fake ."
    assert len(citations) == 1


def test_resolve_citations_accepts_unique_truncated_prefix():
    # Models routinely echo only the first UUID segment (seen live in staging).
    c1, c2 = _chunk(title="Handbook"), _chunk()
    short = str(c1.chunk_id)[:8]
    content, citations = _resolve_citations(f"Leave is 25 days [c:{short}].", [c1, c2])
    assert content == "Leave is 25 days [1]."
    assert citations[0]["chunk_id"] == str(c1.chunk_id)


def test_resolve_citations_truncated_prefix_shares_numbering_with_full_id():
    c1 = _chunk()
    text = f"A [c:{c1.chunk_id}] and B [c:{str(c1.chunk_id)[:8]}]."
    content, citations = _resolve_citations(text, [c1])
    assert content == "A [1] and B [1]."
    assert len(citations) == 1


def test_resolve_citations_accepts_fullwidth_brackets():
    # GLM/DeepSeek-family models occasionally echo markers in CJK brackets
    # (seen live 1 Aug 2026: 【c:4c5e01b1-…】 in a research answer).
    c1 = _chunk(title="Handbook")
    content, citations = _resolve_citations(f"Rate is 3.75% 【c:{c1.chunk_id}】.", [c1])
    assert content == "Rate is 3.75% [1]."
    assert citations[0]["chunk_id"] == str(c1.chunk_id)


def test_resolve_citations_drops_ambiguous_and_fabricated_prefixes():
    twin_a = _chunk(cid=UUID("aaaabbbb-0000-4000-8000-000000000001"))
    twin_b = _chunk(cid=UUID("aaaabbbb-0000-4000-8000-000000000002"))
    # Fabricated short id that prefixes nothing supplied.
    content, citations = _resolve_citations("Fake [c:ffff1234].", [twin_a, twin_b])
    assert content == "Fake ."
    assert citations == []
    # Ambiguous: the prefix matches both supplied ids — must not resolve.
    content, citations = _resolve_citations("X [c:aaaabbbb].", [twin_a, twin_b])
    assert content == "X ."
    assert citations == []


def test_resolve_citations_accepts_marker_without_c_prefix():
    # Seen live 11 Aug 2026: the model dropped the `c:` prefix *and* used CJK
    # brackets, so 【3174bc60-…】 reached a user as a bare uuid mid-sentence.
    c1 = _chunk(title="Vendor questions")
    text = f"Tied to the Act's articles【{c1.chunk_id}】."
    content, citations = _resolve_citations(text, [c1])
    assert content == "Tied to the Act's articles[1]."
    assert citations[0]["chunk_id"] == str(c1.chunk_id)


def test_resolve_citations_unprefixed_shares_numbering_with_prefixed():
    c1 = _chunk()
    text = f"A [c:{c1.chunk_id}] and B 【{c1.chunk_id}】."
    content, citations = _resolve_citations(text, [c1])
    assert content == "A [1] and B [1]."
    assert len(citations) == 1


def test_resolve_citations_leaves_unprefixed_non_markers_alone():
    """Bracketed text that isn't ours must survive verbatim — deleting a
    prefixed hallucination is right, deleting the user's prose is not."""
    c1 = _chunk()
    # Too short to be an id; ordinary prose that happens to be hex.
    content, citations = _resolve_citations("See [42] and [dead].", [c1])
    assert content == "See [42] and [dead]."
    assert citations == []
    # 8 hex chars but not a whole uuid and not ours: still a lookalike.
    content, citations = _resolve_citations("Build [deadbeef].", [c1])
    assert content == "Build [deadbeef]."
    assert citations == []


def test_resolve_citations_strips_unresolvable_full_uuid_without_prefix():
    """A whole uuid in brackets is a marker whatever else is missing. Left
    visible, a model that copies ids out of its own earlier replies would keep
    showing them to the user."""
    c1 = _chunk()
    content, citations = _resolve_citations(f"Stale 【{uuid4()}】.", [c1])
    assert content == "Stale ."
    assert citations == []


def test_resolve_citations_accepts_uppercase_prefix():
    # [C:<uuid>] — the prefix case-folded by the model. Without this the
    # marker was left verbatim and the reader saw a raw uuid.
    c1 = _chunk(title="Handbook")
    content, citations = _resolve_citations(f"Leave is 25 days [C:{c1.chunk_id}].", [c1])
    assert content == "Leave is 25 days [1]."
    assert citations[0]["chunk_id"] == str(c1.chunk_id)


def test_resolve_citations_accepts_markdown_escaped_brackets():
    # Report-mode markdown sometimes escapes the brackets: \[c:…\]. The
    # backslash used to be swallowed into the id, fail lookup, and delete
    # the marker — a real citation lost.
    c1 = _chunk()
    content, citations = _resolve_citations(rf"Leave is 25 days \[c:{c1.chunk_id}\].", [c1])
    assert content == "Leave is 25 days [1]."
    assert len(citations) == 1


def test_resolve_citations_survives_punctuation_inside_the_bracket():
    # [c:<uuid>.] — a stop inside the bracket used to break the lookup and
    # delete the marker.
    c1 = _chunk()
    content, citations = _resolve_citations(f"Leave is 25 days [c:{c1.chunk_id}.].", [c1])
    assert content == "Leave is 25 days [1]."
    assert len(citations) == 1


def test_resolve_citations_accepts_wrapped_prefix():
    # "[Ref c:…]" and "[source: c:…]" — the model dressing the marker up.
    c1 = _chunk()
    text = f"A [Ref c:{c1.chunk_id}] and B [source: c:{c1.chunk_id}]."
    content, citations = _resolve_citations(text, [c1])
    assert content == "A [1] and B [1]."
    assert len(citations) == 1


def test_resolve_citations_wrapped_bracket_that_resolves_nothing_stays_prose():
    # A dressed-up bracket resolving to nothing is likelier prose than a
    # hallucination — unlike a plain [c:…], which is dropped by design.
    c1 = _chunk()
    content, citations = _resolve_citations("See [the file c:config].", [c1])
    assert content == "See [the file c:config]."
    assert citations == []


def test_resolve_citations_report_mode_markdown():
    """The originally reported symptom: a report-shaped answer with full-UUID
    markers must come back numbered with a populated citations list."""
    c1, c2 = _chunk(title="Accounts"), _chunk(title="Policy")
    text = (
        f"## Findings\n\n"
        f"- Income rose 12% [c:{c1.chunk_id}]\n"
        f"- Cover renewed [c:{c2.chunk_id}]\n\n"
        f"| Item | Source |\n| --- | --- |\n| Income | [c:{c1.chunk_id}] |\n\n"
        f"**In short**: both hold [c:{c1.chunk_id}, c:{c2.chunk_id}]."
    )
    content, citations = _resolve_citations(text, [c1, c2])
    assert "[c:" not in content
    assert "- Income rose 12% [1]" in content
    assert "- Cover renewed [2]" in content
    assert "| Income | [1] |" in content
    assert "both hold [1][2]." in content
    assert [c["n"] for c in citations] == [1, 2]


# -- hybrid SQL under RLS ----------------------------------------------------


async def _seed_chunk(tenant, content: str, hot: int | None, title="Doc") -> tuple[UUID, UUID]:
    """Insert a ready document with one chunk; hot=None leaves embedding null."""
    async with db.tenant_tx(tenant.owner_id, tenant.id) as conn:
        doc_id = await conn.fetchval(
            """
            insert into documents (tenant_id, title, status, created_by)
            values ($1, $2, 'ready', $3) returning id
            """,
            tenant.id,
            title,
            tenant.owner_id,
        )
        emb = "[" + ",".join(str(x) for x in _vec(hot)) + "]" if hot is not None else None
        chunk_id = await conn.fetchval(
            """
            insert into doc_chunks (tenant_id, document_id, content, page_start,
                                    page_end, embedding)
            values ($1, $2, $3, 1, 1, $4::vector) returning id
            """,
            tenant.id,
            doc_id,
            content,
            emb,
        )
    return doc_id, chunk_id


async def test_hybrid_search_vector_text_and_isolation(client):
    a = await seed_tenant(client, f"ret-a-{uuid4().hex[:6]}")
    b = await seed_tenant(client, f"ret-b-{uuid4().hex[:6]}")

    _, close_id = await _seed_chunk(a, "The warranty covers zebra printers.", hot=0)
    await _seed_chunk(a, "Unrelated onboarding notes.", hot=1)
    _, kw_id = await _seed_chunk(a, "Quarterly kumquat budget review.", hot=None)
    # Same content in tenant B: must never surface under A (RLS).
    await _seed_chunk(b, "The warranty covers zebra printers.", hot=0)

    async with db.tenant_tx(a.owner_id, a.id) as conn:
        by_vector = await retrieve(conn, _vec(0), "no keyword overlap here")
        assert [c.chunk_id for c in by_vector][:1] == [close_id]

        by_text = await retrieve(conn, _vec(3), "kumquat budget")
        assert kw_id in [c.chunk_id for c in by_text]

        all_ids = {c.chunk_id for c in await retrieve(conn, _vec(0), "zebra warranty")}
    async with db.tenant_tx(b.owner_id, b.id) as conn:
        b_ids = {c.chunk_id for c in await retrieve(conn, _vec(0), "zebra warranty")}
    assert not all_ids & b_ids and b_ids  # B finds its copy; sets are disjoint


async def test_scope_restricts_documents(client):
    t = await seed_tenant(client, f"ret-s-{uuid4().hex[:6]}")
    doc1, c1 = await _seed_chunk(t, "Alpha zebra facts.", hot=0)
    _, c2 = await _seed_chunk(t, "Beta zebra facts.", hot=2)

    async with db.tenant_tx(t.owner_id, t.id) as conn:
        hits = await retrieve(conn, _vec(0), "zebra", scope=Scope(restrict_to=frozenset({doc1})))
    ids = [c.chunk_id for c in hits]
    assert c1 in ids and c2 not in ids


# -- chat citation contract --------------------------------------------------


@pytest.fixture
def citing_llm(monkeypatch):
    """Stub model that cites the first excerpt id found in the system prompt;
    captures the prompts it was given."""
    seen: list[list[dict]] = []

    async def _fake(virtual_key, alias, messages, result):
        seen.append(messages)
        import re

        ids = re.findall(r"\[c:([0-9a-f-]{36})\]", messages[0]["content"])
        text = f"Covered in the handbook [c:{ids[0]}]." if ids else "The vault doesn't cover that."
        result.text_parts.append(text)
        yield text
        result.model, result.tokens_in, result.tokens_out = "m", 10, 5

    monkeypatch.setattr(litellm_client, "stream_chat", _fake)

    embed_calls: list[str] = []

    async def _fake_embed(virtual_key, text):
        embed_calls.append(text)
        return _vec(0), 7

    monkeypatch.setattr(litellm_client, "embed_query", _fake_embed)
    return {"prompts": seen, "embeds": embed_calls}


async def _post_message(client, tenant, content: str, **extra) -> list[tuple[str, dict]]:
    headers = auth(tenant.owner_id, tenant.id)
    resp = await client.post(
        f"/api/v1/conversations/{tenant.conversation_id}/messages",
        json={"content": content, **extra},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    return parse_sse(resp.text)


async def test_grounded_answer_carries_citation(client, citing_llm):
    t = await seed_tenant(client, f"cite-{uuid4().hex[:6]}")
    await enable_llm_key(t)
    _, chunk_id = await _seed_chunk(t, "Warranty lasts 24 months.", hot=0, title="Warranty policy")

    done = dict(await _post_message(client, t, "How long is the warranty?"))["done"]
    assert done["content"] == "Covered in the handbook [1]."
    assert len(done["citations"]) == 1
    cite = done["citations"][0]
    assert cite == {
        "n": 1,
        "chunk_id": str(chunk_id),
        "document_id": cite["document_id"],
        "title": "Warranty policy",
        "page_start": 1,
        "page_end": 1,
        "snippet": "Warranty lasts 24 months.",
        "url": None,
        "source_type": "vault",
    }
    # Persisted, not just streamed.
    async with db.tenant_tx(t.owner_id, t.id) as conn:
        stored = await conn.fetchval(
            "select citations from messages where conversation_id = $1"
            " and role = 'assistant' order by created_at desc limit 1",
            t.conversation_id,
        )
    assert json.loads(stored)[0]["chunk_id"] == str(chunk_id)


async def test_empty_retrieval_gets_no_coverage_prompt(client, citing_llm):
    t = await seed_tenant(client, f"nocov-{uuid4().hex[:6]}")
    await enable_llm_key(t)
    # No embedded chunks at all: seed_tenant's chunk has a null embedding and
    # the query shares no keywords with it.
    done = dict(await _post_message(client, t, "What is the kumquat policy?"))["done"]
    assert done["citations"] == []
    system = citing_llm["prompts"][0][0]["content"]
    assert "no relevant excerpts were found" in system
    assert "<vault-excerpts>" not in system


async def test_use_vault_false_skips_retrieval(client, citing_llm):
    t = await seed_tenant(client, f"novault-{uuid4().hex[:6]}")
    await enable_llm_key(t)
    await _seed_chunk(t, "Warranty lasts 24 months.", hot=0)

    done = dict(await _post_message(client, t, "warranty?", use_vault=False))["done"]
    assert done["citations"] == []
    assert citing_llm["embeds"] == []
    system = citing_llm["prompts"][0][0]["content"]
    assert "vault" not in system.lower()


async def test_hallucinated_citation_stripped_in_chat(client, monkeypatch):
    async def _fake(virtual_key, alias, messages, result):
        text = f"Fact [c:{uuid4()}]."
        result.text_parts.append(text)
        yield text
        result.model, result.tokens_in, result.tokens_out = "m", 1, 1

    async def _fake_embed(virtual_key, text):
        return _vec(0), 1

    monkeypatch.setattr(litellm_client, "stream_chat", _fake)
    monkeypatch.setattr(litellm_client, "embed_query", _fake_embed)

    t = await seed_tenant(client, f"halluc-{uuid4().hex[:6]}")
    await enable_llm_key(t)
    await _seed_chunk(t, "Warranty lasts 24 months.", hot=0)
    done = dict(await _post_message(client, t, "warranty?"))["done"]
    assert done["content"] == "Fact ."
    assert done["citations"] == []


# -- /vault/search -----------------------------------------------------------


async def test_vault_search_admin_only(client, citing_llm):
    t = await seed_tenant(client, f"vs-{uuid4().hex[:6]}")
    await enable_llm_key(t)
    _, chunk_id = await _seed_chunk(t, "Zebra printer warranty details.", hot=0)

    resp = await client.post(
        "/api/v1/vault/search",
        json={"query": "zebra warranty"},
        headers=auth(t.owner_id, t.id),
    )
    assert resp.status_code == 200, resp.text
    hits = resp.json()
    assert hits and hits[0]["chunk_id"] == str(chunk_id)
    assert hits[0]["score"] > 0

    # Member (accepted invite) is not allowed on the debug surface.
    member_id = uuid4()
    accept = await client.post(
        "/api/v1/invites/accept",
        json={"token": t.invite_token},
        headers=auth(member_id),
    )
    assert accept.status_code == 200, accept.text
    resp = await client.post(
        "/api/v1/vault/search",
        json={"query": "zebra"},
        headers=auth(member_id, t.id),
    )
    assert resp.status_code == 403


def test_resolve_citations_drops_a_non_hex_prefixed_id():
    """Found by the local end-to-end run on 11 Aug 2026.

    The model invented `[c:s1]` on a project with an empty vault. The pattern
    required a hex-looking id, `s` is not a hex digit, so nothing matched and
    the marker reached the user verbatim. `c:` is the model saying it meant a
    citation — whatever follows is a citation attempt, and one that resolves
    to nothing is a hallucination.
    """
    real = _chunk()
    for fake in ("[c:s1]", "[c:source-1]", "[c:ref]", "【c:s1】"):
        content, citations = _resolve_citations(f"Need is high {fake}.", [real])
        assert content == "Need is high .", fake
        assert citations == []


def test_resolve_citations_leaves_prose_that_only_looks_like_a_marker():
    """The other half: a prefixed pattern with a space inside is prose, and
    eating it would delete the answer's own words."""
    real = _chunk()
    content, _ = _resolve_citations("See [c: the note below] for detail.", [real])
    assert content == "See [c: the note below] for detail."


def test_resolve_citations_handles_several_ids_in_one_bracket():
    """Found by a live AHF draft, 11 Aug 2026. The model writes lists —
    `[c:p1, c:b1]` — and matching a single id left the whole bracket
    unrecognised, so it reached the reader verbatim."""
    c1, c2 = _chunk(title="Survey"), _chunk(title="Local Plan")
    content, citations = _resolve_citations(f"Both [c:{c1.chunk_id}, c:{c2.chunk_id}].", [c1, c2])
    assert content == "Both [1][2]."
    assert [c["n"] for c in citations] == [1, 2]

    # The prefix repeated only on the first id, and fabricated ids in a list.
    content, _ = _resolve_citations(f"A [c:{c1.chunk_id}, {c2.chunk_id}].", [c1, c2])
    assert content == "A [1][2]."
    content, citations = _resolve_citations("Fake [c:p1, c:b1].", [c1])
    assert content == "Fake ."
    assert citations == []
