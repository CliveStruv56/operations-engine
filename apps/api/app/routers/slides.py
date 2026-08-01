"""Export a slides-mode chat message as a branded native PPTX.

Synchronous by design: parsing and rendering are deterministic and
sub-second, so the draft-job machinery (queue, polling) would be pure
overhead. Rendering runs in a thread; storage I/O stays outside tenant
transactions like every other network call.
"""

import json
from uuid import UUID

import anyio
from fastapi import APIRouter, Depends

from app.audit import write_audit
from app.db import db
from app.errors import ApiError
from app.routers.conversations import _get_owned_conversation
from app.schemas import SlidesExportOut
from app.slides import PPTX_MIME, deck_filename, parse_deck, render_pptx
from app.storage import storage
from app.tenant import TenantContext, require_role

router = APIRouter(tags=["slides"])


@router.post(
    "/conversations/{conversation_id}/messages/{message_id}/slides",
    response_model=SlidesExportOut,
)
async def export_slides(
    conversation_id: UUID,
    message_id: UUID,
    ctx: TenantContext = Depends(require_role("member")),
):
    if not storage.enabled:
        raise ApiError(503, "storage_unavailable", "File storage is not configured")

    # Tx 1: ownership, message content, brand.
    async with db.tenant_tx(ctx.user_id, ctx.tenant_id) as conn:
        await _get_owned_conversation(conn, ctx, conversation_id)
        message = await conn.fetchrow(
            "select role, content from messages where id = $1 and conversation_id = $2",
            message_id,
            conversation_id,
        )
        if message is None or message["role"] != "assistant":
            raise ApiError(404, "not_found", "Message not found")
        brand = json.loads(
            await conn.fetchval("select brand from tenants where id = $1", ctx.tenant_id)
        )

    deck = parse_deck(message["content"])
    if deck is None:
        raise ApiError(400, "not_a_deck", "This message is not a slide outline")

    logo = None
    if isinstance(brand.get("logo_key"), str):
        logo = await storage.download_bytes(brand["logo_key"])
    accent = brand.get("accent") if isinstance(brand.get("accent"), str) else None

    data = await anyio.to_thread.run_sync(render_pptx, deck, accent, logo)
    key = f"{ctx.tenant_id}/slides/{message_id}.pptx"  # re-export overwrites
    await storage.upload_bytes(key, data, PPTX_MIME)

    async with db.tenant_tx(ctx.user_id, ctx.tenant_id) as conn:
        await write_audit(
            conn,
            ctx.tenant_id,
            ctx.user_id,
            "message.slides_export",
            "message",
            str(message_id),
            meta={"slides": len(deck.slides)},
        )

    return {
        "download_url": storage.presign_get(key),
        "filename": deck_filename(deck.title),
        "slide_count": len(deck.slides),
    }
