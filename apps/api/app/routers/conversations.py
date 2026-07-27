"""Chat: conversations CRUD + SSE streaming messages (spec §6).

Streaming shape: the LLM call happens *between* two short tenant transactions —
never inside one — so a slow stream cannot hold a DB connection open.

SSE protocol:
  event: delta   data: {"content": "..."}          (repeated)
  event: done    data: {persisted MessageOut + "soft_cap": bool}
  event: error   data: {"error": {code, message}}  (stream aborts)
"""

import json
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.audit import write_audit
from app.db import db
from app.errors import ApiError
from app.litellm import StreamResult, estimate_cost_usd, litellm_client
from app.ratelimit import rate_limiter
from app.routing import estimate_tokens, select_route
from app.schemas import ConversationCreate, ConversationOut, MessageCreate, MessageOut
from app.tenant import TenantContext, get_conn, require_role

router = APIRouter(tags=["conversations"])

SYSTEM_PROMPT = (
    "You are the assistant for this organisation's operations workspace. "
    "Be concise and factual. If you do not know something, say so."
)


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
    row = await conn.fetchrow(
        """
        insert into conversations (tenant_id, user_id, title)
        values ($1, $2, $3) returning *
        """,
        ctx.tenant_id,
        ctx.user_id,
        body.title,
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
    """A user sees their own conversations; chat history is personal even
    inside a tenant."""
    rows = await conn.fetch(
        "select * from conversations where user_id = $1 order by updated_at desc",
        ctx.user_id,
    )
    return [dict(r) for r in rows]


async def _get_owned_conversation(
    conn: asyncpg.Connection, ctx: TenantContext, conversation_id: UUID
) -> asyncpg.Record:
    row = await conn.fetchrow(
        "select * from conversations where id = $1", conversation_id
    )  # RLS already scopes to tenant
    if row is None:
        raise ApiError(404, "not_found", "Conversation not found")
    if row["user_id"] != ctx.user_id and ctx.role == "member":
        raise ApiError(404, "not_found", "Conversation not found")
    return row


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
    await _get_owned_conversation(conn, ctx, conversation_id)
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

    # Tx 1: validate, persist the user message, gather routing inputs.
    async with db.tenant_tx(ctx.user_id, ctx.tenant_id) as conn:
        await _get_owned_conversation(conn, ctx, conversation_id)
        tenant = await conn.fetchrow(
            "select litellm_key_id, soft_budget_usd from tenants where id = $1",
            ctx.tenant_id,
        )
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

    if not tenant["litellm_key_id"]:
        raise ApiError(503, "llm_unavailable", "No model key is provisioned for this workspace")

    soft_cap_hit = float(month_spend) >= float(tenant["soft_budget_usd"])
    llm_messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    llm_messages += [{"role": r["role"], "content": r["content"]} for r in history]
    llm_messages.append({"role": "user", "content": body.content})
    context_tokens = sum(estimate_tokens(m["content"]) for m in llm_messages)
    alias = select_route(body.task_kind, context_tokens, soft_cap_hit=soft_cap_hit)

    async def stream():
        result = StreamResult()
        try:
            async for delta in litellm_client.stream_chat(
                tenant["litellm_key_id"], alias, llm_messages, result
            ):
                yield _sse("delta", {"content": delta})
        except ApiError as exc:
            yield _sse("error", {"error": {"code": exc.code, "message": exc.message}})
            return
        except Exception:  # network/parse failures: no payloads in the event
            yield _sse("error", {"error": {"code": "llm_error", "message": "Stream failed"}})
            return

        cost = estimate_cost_usd(alias, result.tokens_in, result.tokens_out)
        # Tx 2: persist the assistant message + usage after the stream is done.
        async with db.tenant_tx(ctx.user_id, ctx.tenant_id) as conn:
            row = await conn.fetchrow(
                """
                insert into messages (tenant_id, conversation_id, role, content,
                                      model, tokens_in, tokens_out, cost_usd)
                values ($1, $2, 'assistant', $3, $4, $5, $6, $7) returning *
                """,
                ctx.tenant_id,
                conversation_id,
                result.text,
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
            await conn.execute(
                "update conversations set updated_at = now() where id = $1",
                conversation_id,
            )
        yield _sse("done", {**_json_safe(_message_out(row)), "soft_cap": soft_cap_hit})

    return StreamingResponse(stream(), media_type="text/event-stream")


def _json_safe(message: dict) -> dict:
    return {
        k: (str(v) if isinstance(v, UUID) else v.isoformat() if hasattr(v, "isoformat") else v)
        for k, v in message.items()
    }
