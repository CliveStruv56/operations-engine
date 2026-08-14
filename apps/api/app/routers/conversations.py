"""Chat: conversations CRUD + SSE streaming messages (spec §6).

Streaming shape: the LLM call happens *between* two short tenant transactions —
never inside one — so a slow stream cannot hold a DB connection open.

SSE protocol:
  event: delta   data: {"content": "..."}          (repeated)
  event: done    data: {persisted MessageOut + "soft_cap": bool}
  event: error   data: {"error": {code, message}}  (stream aborts)
"""

import asyncio
import json
import logging
import re
import time
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.audit import write_audit
from app.crm.lookup import contacts_block, match_contacts
from app.db import db
from app.errors import ApiError
from app.litellm import StreamResult, estimate_cost_usd, litellm_client
from app.prompts import (
    CONTACTS_PROMPT,
    NO_COVERAGE_PROMPT,
    SYSTEM_PROMPT,
    TASK_PROMPTS,
    VAULT_PROMPT,
    WEB_PROMPT,
)
from app.ratelimit import rate_limiter
from app.retrieval import (
    ATTACHED_WEIGHT,
    PRIMARY_WEIGHT,
    PROJECT_WEIGHT,
    RetrievedChunk,
    Scope,
    retrieve,
)
from app.routing import estimate_tokens, select_route
from app.schemas import (
    ConversationCreate,
    ConversationOut,
    ConversationPatch,
    MessageCreate,
    MessageOut,
)
from app.search import WebSource, exa_search
from app.secrets import decrypt_llm_key
from app.tenant import TenantContext, get_conn, require_role

router = APIRouter(tags=["conversations"])

# Latency telemetry. Ids and counts only — never message, excerpt or contact
# content (spec §9.5), so this is safe to leave on in production. Chat is the
# busiest surface and had no timing at all; without these numbers any further
# tuning is guesswork.
logger = logging.getLogger("app.chat.latency")

# Citation markers, as the models actually write them rather than as asked.
# Keep in step with worker/drafting/assemble.py.
#
# Two branches, because the `c:` prefix decides how much benefit of the doubt a
# bracket gets. Prefixed, the model is telling us it meant a citation, so
# anything inside is a citation attempt and an unresolvable one is an invention
# to strip. Prefix-less, nothing separates it from prose, so it must still look
# like a truncated hex id (staging saw [c:1a689315] for a full UUID, hence
# resolve-by-unique-prefix below).
#
# Each relaxation here is a failure we watched reach a reader:
#   1 Aug  fullwidth 【c:…】 — CJK bracket echo from the GLM/DeepSeek family
#  11 Aug  the `c:` prefix dropped entirely: 【3174bc60-…】
#  11 Aug  a non-hex id, [c:s1], matched nothing and so was never stripped
#  11 Aug  several ids in one bracket, [c:p1, c:b1], likewise
#
# Tokens are comma-separated and space-free, which is what keeps
# `[c: see the note below]` prose rather than something to eat.
_ID = r"[^\s,\]】]{1,64}"
CITATION_RE = re.compile(
    rf"[\[【]\s*(?:c:\s*(?P<prefixed>{_ID}(?:\s*,\s*(?:c:\s*)?{_ID})*)"
    rf"|(?P<bare>[0-9a-fA-F][0-9a-fA-F-]{{3,35}}))\s*[\]】]"
)
_ID_SPLIT = re.compile(r"\s*,\s*(?:c:\s*)?")
# A prefix-less marker is only believed at full-id length. Short bracketed hex
# is ordinary prose far more often than it is a citation ("[42]", "[dead]"),
# and the truncations we have actually seen ran to 8 chars.
MIN_UNPREFIXED_ID = 8
# 8-4-4-4-12. A bracketed token of exactly this shape is a marker beyond
# reasonable doubt, prefix or not, so an unresolvable one is a hallucination to
# strip rather than prose to protect. Matters because a model that copies ids
# out of its own earlier (unresolved) replies would otherwise keep showing them.
FULL_ID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\Z")
# Evidence-panel excerpt length. Chunks run ~600 tokens (~2,400 chars); 300
# was too little to carry context past a chunk's heading boilerplate.
SNIPPET_CHARS = 800


def _excerpt_block(chunks: list[RetrievedChunk]) -> str:
    parts = []
    for c in chunks:
        pages = f", p.{c.page_start}–{c.page_end}" if c.page_start else ""
        parts.append(f'[c:{c.chunk_id}] (from "{c.title}"{pages})\n{c.content}')
    return "\n\n---\n\n".join(parts)


def _web_block(sources: list[WebSource]) -> str:
    return "\n\n---\n\n".join(
        f'[c:{s.chunk_id}] (from "{s.title}", {s.url})\n{s.content}' for s in sources
    )


def _resolve_citations(
    text: str,
    chunks: list[RetrievedChunk],
    web_sources: list[WebSource] | None = None,
) -> tuple[str, list[dict]]:
    """Replace [c:<id>] markers with [n] in first-appearance order; markers
    pointing outside the retrieved set are hallucinations and are dropped.
    Only ids we ourselves supplied can resolve — a fabricated or cross-tenant
    id can never surface as a citation. Web sources join the pool under
    freshly minted ids and carry url/source_type in the payload."""
    by_id: dict[str, RetrievedChunk | WebSource] = {str(c.chunk_id): c for c in chunks}
    by_id.update({str(w.chunk_id): w for w in web_sources or []})
    order: dict[str, int] = {}
    citations: list[dict] = []

    def _lookup(cid: str) -> tuple[str, RetrievedChunk | WebSource] | None:
        chunk = by_id.get(cid)
        if chunk is not None:
            return cid, chunk
        # A truncated marker resolves only when it prefixes exactly one
        # supplied id — fabricated or ambiguous ids still drop.
        matches = [(full, c) for full, c in by_id.items() if full.startswith(cid)]
        return matches[0] if len(matches) == 1 else None

    def _number(cid_raw: str) -> str:
        """`[n]` for an id that resolves, "" for one that does not."""
        found = _lookup(cid_raw)
        if found is None:
            return ""
        cid, chunk = found
        if cid not in order:
            order[cid] = len(order) + 1
            if isinstance(chunk, WebSource):
                citations.append(
                    {
                        "n": order[cid],
                        "chunk_id": cid,
                        "document_id": cid,  # synthetic — web results have no document
                        "title": chunk.title,
                        "page_start": None,
                        "page_end": None,
                        "snippet": chunk.content[:SNIPPET_CHARS],
                        "url": chunk.url,
                        "source_type": "web",
                    }
                )
            else:
                citations.append(
                    {
                        "n": order[cid],
                        "chunk_id": cid,
                        "document_id": str(chunk.document_id),
                        "title": chunk.title,
                        "page_start": chunk.page_start,
                        "page_end": chunk.page_end,
                        "snippet": chunk.content[:SNIPPET_CHARS],
                        "url": None,
                        "source_type": "vault",
                    }
                )
        return f"[{order[cid]}]"

    def _sub(match: re.Match) -> str:
        prefixed = match.group("prefixed")
        if prefixed is not None:
            # The prefix is the model saying it meant a citation, so every id in
            # the bracket is a citation attempt — resolve each, drop inventions.
            return "".join(_number(cid.lower()) for cid in _ID_SPLIT.split(prefixed.strip()) if cid)
        cid_raw = match.group("bare").lower()
        # Without the prefix, only a whole uuid is a marker beyond doubt.
        # Anything shorter is left exactly as written when it fails to resolve:
        # dropping a marker deletes a hallucinated citation, but dropping a
        # lookalike would silently delete the answer's own text.
        certain = FULL_ID_RE.match(cid_raw) is not None
        if not certain and len(cid_raw) < MIN_UNPREFIXED_ID:
            return match.group(0)
        numbered = _number(cid_raw)
        return numbered if numbered or certain else match.group(0)

    return CITATION_RE.sub(_sub, text), citations


def _message_out(row: asyncpg.Record) -> dict:
    out = dict(row)
    out["citations"] = json.loads(out["citations"])
    if out["cost_usd"] is not None:
        out["cost_usd"] = float(out["cost_usd"])
    return out


@router.post("/conversations", status_code=201, response_model=ConversationOut)
async def create_conversation(
    body: ConversationCreate,
    ctx: TenantContext = Depends(require_role("member")),
    conn: asyncpg.Connection = Depends(get_conn),
):
    if body.project_id is not None:
        exists = await conn.fetchval("select 1 from projects where id = $1", body.project_id)
        if not exists:
            raise ApiError(404, "not_found", "Project not found")
    row = await conn.fetchrow(
        """
        insert into conversations (tenant_id, user_id, title, project_id)
        values ($1, $2, $3, $4) returning *
        """,
        ctx.tenant_id,
        ctx.user_id,
        body.title,
        body.project_id,
    )
    await write_audit(
        conn, ctx.tenant_id, ctx.user_id, "conversation.create", "conversation", str(row["id"])
    )
    return dict(row)


@router.get("/conversations", response_model=list[ConversationOut])
async def list_conversations(
    ctx: TenantContext = Depends(require_role("member")),
    conn: asyncpg.Connection = Depends(get_conn),
):
    """A user sees their own conversations plus ones shared with the tenant;
    private chat history is personal even inside a tenant."""
    rows = await conn.fetch(
        """
        select c.id, c.title, c.project_id, c.visibility, c.created_at, c.updated_at,
               c.user_id = $1 as is_mine, m.email as owner_email
        from conversations c
        left join memberships m on m.tenant_id = c.tenant_id and m.user_id = c.user_id
        where c.user_id = $1 or c.visibility = 'tenant'
        order by c.updated_at desc
        """,
        ctx.user_id,
    )
    return [dict(r) for r in rows]


def build_scope(project_docs: dict, attached_ids: set) -> Scope | None:
    """Retrieval weights for one conversation, most explicit signal winning:
    a file attached to this chat beats the project's primary documents beats
    the project's other documents beats the rest of the vault. Pure, so the
    ordering is testable without the whole chat stack."""
    weights = {
        doc_id: PRIMARY_WEIGHT if primary else PROJECT_WEIGHT
        for doc_id, primary in project_docs.items()
    }
    for doc_id in attached_ids:
        weights[doc_id] = ATTACHED_WEIGHT
    return Scope(weights=weights) if weights else None


async def _get_owned_conversation(
    conn: asyncpg.Connection, ctx: TenantContext, conversation_id: UUID
) -> asyncpg.Record:
    """Owner-only gate for writes (delete, post, share, export). 404 either
    way — existence of someone else's private chat is not revealed, and
    admins/owners get no override: private means private."""
    row = await conn.fetchrow(
        "select * from conversations where id = $1", conversation_id
    )  # RLS already scopes to tenant
    if row is None or row["user_id"] != ctx.user_id:
        raise ApiError(404, "not_found", "Conversation not found")
    return row


async def _get_readable_conversation(
    conn: asyncpg.Connection, ctx: TenantContext, conversation_id: UUID
) -> asyncpg.Record:
    """Read gate: the owner, or any tenant member when shared."""
    row = await conn.fetchrow(
        "select * from conversations where id = $1", conversation_id
    )  # RLS already scopes to tenant
    if row is None or (row["user_id"] != ctx.user_id and row["visibility"] != "tenant"):
        raise ApiError(404, "not_found", "Conversation not found")
    return row


@router.patch("/conversations/{conversation_id}", response_model=ConversationOut)
async def patch_conversation(
    conversation_id: UUID,
    body: ConversationPatch,
    ctx: TenantContext = Depends(require_role("member")),
    conn: asyncpg.Connection = Depends(get_conn),
):
    row = await _get_owned_conversation(conn, ctx, conversation_id)
    if body.visibility != row["visibility"]:
        # No updated_at bump: sharing shouldn't fake recency in the sidebar.
        row = await conn.fetchrow(
            "update conversations set visibility = $2 where id = $1 returning *",
            conversation_id,
            body.visibility,
        )
        shared = body.visibility == "tenant"
        action = "conversation.share" if shared else "conversation.unshare"
        await write_audit(
            conn,
            ctx.tenant_id,
            ctx.user_id,
            action,
            "conversation",
            str(conversation_id),
            # Only publishing makes the title fair game for the tenant-wide
            # feed: /activity returns meta verbatim, so carrying the title on
            # the unshare would broadcast a chat the owner just made private.
            meta={"title": row["title"]} if shared else None,
        )
    return dict(row)


@router.delete("/conversations/{conversation_id}", status_code=204)
async def delete_conversation(
    conversation_id: UUID,
    ctx: TenantContext = Depends(require_role("member")),
    conn: asyncpg.Connection = Depends(get_conn),
):
    await _get_owned_conversation(conn, ctx, conversation_id)
    await conn.execute("delete from conversations where id = $1", conversation_id)
    await write_audit(
        conn,
        ctx.tenant_id,
        ctx.user_id,
        "conversation.delete",
        "conversation",
        str(conversation_id),
    )


@router.get("/conversations/{conversation_id}/messages", response_model=list[MessageOut])
async def list_messages(
    conversation_id: UUID,
    ctx: TenantContext = Depends(require_role("member")),
    conn: asyncpg.Connection = Depends(get_conn),
):
    await _get_readable_conversation(conn, ctx, conversation_id)
    rows = await conn.fetch(
        "select * from messages where conversation_id = $1 order by created_at",
        conversation_id,
    )
    return [_message_out(r) for r in rows]


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


@router.post("/conversations/{conversation_id}/messages")
async def post_message(
    conversation_id: UUID,
    body: MessageCreate,
    ctx: TenantContext = Depends(require_role("member")),
):
    await rate_limiter.check_chat(ctx.tenant_id)
    t_request = time.perf_counter()

    # Tx 1: validate, persist the user message, gather routing inputs.
    async with db.tenant_tx(ctx.user_id, ctx.tenant_id) as conn:
        conversation = await _get_owned_conversation(conn, ctx, conversation_id)
        project_docs: dict = {}
        if conversation["project_id"] is not None:
            project_docs = {
                r["id"]: r["is_primary"]
                for r in await conn.fetch(
                    "select id, is_primary from documents where project_id = $1",
                    conversation["project_id"],
                )
            }
        attached_ids = {
            r["id"]
            for r in await conn.fetch(
                "select id from documents where conversation_id = $1", conversation_id
            )
        }
        tenant = await conn.fetchrow(
            "select litellm_key_encrypted, soft_budget_usd, features from tenants where id = $1",
            ctx.tenant_id,
        )
        features = json.loads(tenant["features"])
        if body.task_kind == "research":
            # Same gate shape as the Groundwork module: research prompts go
            # to a third-party search API, so it is opt-in per tenant.
            if features.get("web_search") is not True:
                raise ApiError(
                    400, "feature_disabled", "Web search is not enabled for this workspace"
                )
        # Contact book lookup (CRM module): name/company mentions in the
        # message pull matching records into the prompt so "what's Sarah's
        # number?" answers from stored data instead of guessing.
        matched_contacts: list = []
        matched_companies: list = []
        if features.get("contacts") is True:
            matched_contacts, matched_companies = await match_contacts(conn, body.content)
        month_spend = await conn.fetchval(
            """
            select coalesce(sum(cost_usd), 0) from usage_events
            where created_at >= date_trunc('month', now())
            """,
        )
        history = await conn.fetch(
            "select role, content from messages where conversation_id = $1 order by created_at",
            conversation_id,
        )
        await conn.execute(
            """
            insert into messages (tenant_id, conversation_id, role, content)
            values ($1, $2, 'user', $3)
            """,
            ctx.tenant_id,
            conversation_id,
            body.content,
        )
        await write_audit(
            conn,
            ctx.tenant_id,
            ctx.user_id,
            "message.create",
            "conversation",
            str(conversation_id),
        )

    tx1_s = time.perf_counter() - t_request
    virtual_key = decrypt_llm_key(tenant["litellm_key_encrypted"])
    if not virtual_key:
        raise ApiError(503, "llm_unavailable", "No model key is provisioned for this workspace")

    # Retrieval (spec §5): embed the query (network — outside any tenant tx),
    # then hybrid-search under a short tenant tx. Scope stays None until
    # projects land (Slice 4.5).
    chunks: list[RetrievedChunk] = []
    embed_tokens = 0
    scope = build_scope(project_docs, attached_ids)

    # The embedding and the web search are independent network calls — the
    # embedding feeds vault retrieval, the search feeds the prompt, and
    # neither reads the other's result. They used to run back to back, so a
    # research message paid both in series before the model saw anything;
    # `exa_search` alone allows up to 15s. Overlapping them takes the shorter
    # of the two off the critical path entirely.
    web_sources: list[WebSource] = []
    embed_task = (
        asyncio.create_task(litellm_client.embed_query(virtual_key, body.content))
        if body.use_vault
        else None
    )
    search_task = (
        asyncio.create_task(exa_search(body.content)) if body.task_kind == "research" else None
    )
    running = [t for t in (embed_task, search_task) if t is not None]
    t_network = time.perf_counter()
    if running:
        # return_exceptions so one failure cannot leave the other task
        # orphaned with an unretrieved exception; `.result()` below re-raises
        # in the original order, so callers still see the embedding error
        # first exactly as they did when these ran in sequence.
        await asyncio.gather(*running, return_exceptions=True)
    network_s = time.perf_counter() - t_network

    retrieval_s = 0.0
    if embed_task is not None:
        embedding, embed_tokens = embed_task.result()
        t_retrieval = time.perf_counter()
        async with db.tenant_tx(ctx.user_id, ctx.tenant_id) as conn:
            chunks = await retrieve(conn, embedding, body.content, scope=scope)
        retrieval_s = time.perf_counter() - t_retrieval
    if search_task is not None:
        web_sources = search_task.result()

    soft_cap_hit = float(month_spend) >= float(tenant["soft_budget_usd"])
    system = SYSTEM_PROMPT
    if body.task_kind in TASK_PROMPTS:
        system += "\n\n" + TASK_PROMPTS[body.task_kind]
    if body.use_vault:
        if chunks:
            system += "\n\n" + VAULT_PROMPT.format(excerpts=_excerpt_block(chunks))
        else:
            system += "\n\n" + NO_COVERAGE_PROMPT
    if web_sources:
        system += "\n\n" + WEB_PROMPT.format(results=_web_block(web_sources))
    if matched_contacts or matched_companies:
        system += "\n\n" + CONTACTS_PROMPT.format(
            records=contacts_block(matched_contacts, matched_companies)
        )
    llm_messages = [{"role": "system", "content": system}]
    llm_messages += [{"role": r["role"], "content": r["content"]} for r in history]
    llm_messages.append({"role": "user", "content": body.content})
    context_tokens = sum(estimate_tokens(m["content"]) for m in llm_messages)
    alias = select_route(body.task_kind, context_tokens, soft_cap_hit=soft_cap_hit)
    # Everything the user waits through before the model is even asked.
    t_stream = time.perf_counter()

    def _log_latency(result: StreamResult, outcome: str) -> None:
        """One line per message: where the wait actually went.

        `ttft` is the number that matters — everything before it is dead air
        the user sits through. Logged on failures too, since a stream that
        errors after twenty seconds is the case most worth seeing.
        """
        ttft = result.ttft_s
        logger.info(
            "chat outcome=%s alias=%s tenant=%s conversation=%s "
            "tx1_ms=%d network_ms=%d retrieval_ms=%d prestream_ms=%d ttft_ms=%s total_ms=%d "
            "context_tokens=%d tokens_in=%d tokens_out=%d vault_chunks=%d web_sources=%d",
            outcome,
            alias,
            ctx.tenant_id,
            conversation_id,
            tx1_s * 1000,
            network_s * 1000,
            retrieval_s * 1000,
            (t_stream - t_request) * 1000,
            round(ttft * 1000) if ttft is not None else "none",
            (time.perf_counter() - t_request) * 1000,
            context_tokens,
            result.tokens_in,
            result.tokens_out,
            len(chunks),
            len(web_sources),
        )

    async def stream():
        result = StreamResult()
        try:
            async for delta in litellm_client.stream_chat(virtual_key, alias, llm_messages, result):
                yield _sse("delta", {"content": delta})
        except ApiError as exc:
            _log_latency(result, exc.code)
            yield _sse("error", {"error": {"code": exc.code, "message": exc.message}})
            return
        except Exception:  # network/parse failures: no payloads in the event
            _log_latency(result, "llm_error")
            yield _sse("error", {"error": {"code": "llm_error", "message": "Stream failed"}})
            return
        _log_latency(result, "ok")

        content, citations = _resolve_citations(result.text, chunks, web_sources)
        cost = estimate_cost_usd(alias, result.tokens_in, result.tokens_out)
        embed_cost = estimate_cost_usd("embedder", embed_tokens, 0)
        # Tx 2: persist the assistant message + usage after the stream is done.
        async with db.tenant_tx(ctx.user_id, ctx.tenant_id) as conn:
            row = await conn.fetchrow(
                """
                insert into messages (tenant_id, conversation_id, role, content,
                                      citations, model, tokens_in, tokens_out, cost_usd)
                values ($1, $2, 'assistant', $3, $4, $5, $6, $7, $8) returning *
                """,
                ctx.tenant_id,
                conversation_id,
                content,
                json.dumps(citations),
                result.model or alias,
                result.tokens_in,
                result.tokens_out,
                cost,
            )
            await conn.execute(
                """
                insert into usage_events (tenant_id, user_id, kind, model,
                                          tokens_in, tokens_out, cost_usd)
                values ($1, $2, 'chat', $3, $4, $5, $6)
                """,
                ctx.tenant_id,
                ctx.user_id,
                alias,
                result.tokens_in,
                result.tokens_out,
                cost,
            )
            if embed_tokens:
                await conn.execute(
                    """
                    insert into usage_events (tenant_id, user_id, kind, model,
                                              tokens_in, cost_usd)
                    values ($1, $2, 'embed', 'embedder', $3, $4)
                    """,
                    ctx.tenant_id,
                    ctx.user_id,
                    embed_tokens,
                    embed_cost,
                )
            if body.task_kind == "research":
                # Per-search metering (no token counts; Exa bills per call).
                await conn.execute(
                    """
                    insert into usage_events (tenant_id, user_id, kind, model)
                    values ($1, $2, 'search', 'exa')
                    """,
                    ctx.tenant_id,
                    ctx.user_id,
                )
            await conn.execute(
                "update conversations set updated_at = now() where id = $1",
                conversation_id,
            )
        # What actually answered: project docs, the wider vault, or no vault.
        scope_used = None
        if body.use_vault:
            cited_docs = {UUID(c["document_id"]) for c in citations}
            scope_used = "project" if project_docs and cited_docs & set(project_docs) else "vault"
        yield _sse(
            "done",
            {
                **_json_safe(_message_out(row)),
                "soft_cap": soft_cap_hit,
                "scope_used": scope_used,
            },
        )

    return StreamingResponse(stream(), media_type="text/event-stream")


def _json_safe(message: dict) -> dict:
    return {
        k: (str(v) if isinstance(v, UUID) else v.isoformat() if hasattr(v, "isoformat") else v)
        for k, v in message.items()
    }
