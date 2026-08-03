"""Tenant activity feed: a curated slice of the audit log for team awareness.

Allowlist, not denylist — only actions verified team-relevant and meta-safe
appear, so future private actions are excluded by default. Private-chat
events (conversation.create/delete, message.*) never surface; sharing a
chat is a deliberate act of publishing, so conversation.share/unshare do.
"""

import json

import asyncpg
from fastapi import APIRouter, Depends

from app.modules import FEED_PATTERNS
from app.schemas import ActivityFeedItem
from app.tenant import TenantContext, get_conn, require_role

router = APIRouter(tags=["activity"])

ALLOWED_ACTIONS = [
    "document.complete",  # fires after the real upload, unlike document.create
    "document.delete",
    "project.create",
    "project.update",
    "project.delete",
    "member.role_change",
    "invite.accept",  # invite.create would leak invitee emails pre-join
    "tenant.update",
    "tenant.features_change",  # a module appearing is team-relevant; meta is flag names
    "tenant.suspend",  # only ever read after a resume — the feed is unreachable while dark
    "tenant.resume",
    "conversation.share",
    "conversation.unshare",
]

# Module namespaces admitted wholesale, from the manifest. A module opts in by
# declaring a feed_prefix, so a new one cannot start broadcasting by accident.


@router.get("/activity", response_model=list[ActivityFeedItem])
async def tenant_activity(
    ctx: TenantContext = Depends(require_role("member")),
    conn: asyncpg.Connection = Depends(get_conn),
):
    rows = await conn.fetch(
        """
        select a.action, a.target_type, a.target_id, a.meta, a.created_at,
               m.email as actor_email, coalesce(d.title, p.name) as target_title
        from audit_log a
        left join memberships m on m.tenant_id = a.tenant_id and m.user_id = a.user_id
        left join documents d on a.target_type = 'document' and d.id::text = a.target_id
        left join projects p on a.target_type = 'project' and p.id::text = a.target_id
        where a.action = any($1::text[]) or a.action like any($2::text[])
        order by a.created_at desc limit 15
        """,
        ALLOWED_ACTIONS,
        list(FEED_PATTERNS),
    )
    out = []
    for r in rows:
        item = dict(r)
        if isinstance(item["meta"], str):  # asyncpg returns jsonb as text by default
            item["meta"] = json.loads(item["meta"])
        out.append(item)
    return out
