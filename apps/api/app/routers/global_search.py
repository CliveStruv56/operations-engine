"""Workspace search (⌘K palette): title match over the caller's conversations
(own + shared-with-tenant) and the tenant's documents. Runs under the tenant
RLS context; conversations follow the same rule as GET /conversations."""

import asyncpg
from fastapi import APIRouter, Depends, Query

from app.schemas import SearchResultsOut
from app.sqlutil import like_contains
from app.tenant import TenantContext, get_conn, require_role

router = APIRouter(tags=["search"])


@router.get("/search", response_model=SearchResultsOut)
async def workspace_search(
    q: str = Query(min_length=1, max_length=200),
    ctx: TenantContext = Depends(require_role("member")),
    conn: asyncpg.Connection = Depends(get_conn),
):
    pattern = like_contains(q)
    conversations = await conn.fetch(
        """
        select c.id, c.title, c.project_id, c.visibility, c.created_at, c.updated_at,
               c.user_id = $1 as is_mine, m.email as owner_email
        from conversations c
        left join memberships m on m.tenant_id = c.tenant_id and m.user_id = c.user_id
        where (c.user_id = $1 or c.visibility = 'tenant') and c.title ilike $2
        order by c.updated_at desc limit 10
        """,
        ctx.user_id,
        pattern,
    )
    documents = await conn.fetch(
        """
        select id, title, mime, project_id, is_primary, summary, status, error,
               created_by, created_at, updated_at
        from documents
        where title ilike $1
        order by updated_at desc limit 10
        """,
        pattern,
    )
    # Contacts join the palette only when the CRM feature flag is on, mirroring
    # the module gate on /contacts itself.
    contacts: list[asyncpg.Record] = []
    crm_enabled = await conn.fetchval(
        "select features->>'contacts' = 'true' from tenants where id = $1", ctx.tenant_id
    )
    if crm_enabled:
        contacts = await conn.fetch(
            """
            select c.id, c.name, c.job_title, c.email, co.name as company_name
            from crm_contacts c
            left join crm_companies co on co.id = c.company_id
            where c.name ilike $1 or c.email ilike $1 or co.name ilike $1
            order by c.name limit 10
            """,
            pattern,
        )
    return {
        "conversations": [dict(r) for r in conversations],
        "documents": [dict(r) for r in documents],
        "contacts": [dict(r) for r in contacts],
    }
