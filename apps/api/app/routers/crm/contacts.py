"""Tenant-wide contact book: filtered list, CRUD, project links.

FK checks bypass RLS, so company_id and project_id are verified with an
RLS-scoped select before use — a cross-tenant id must 404, never link.
"""

from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends

from app.audit import write_audit
from app.crm.schemas import ContactIn, ContactOut, ContactPatch
from app.errors import ApiError
from app.routers.crm.common import require_contacts
from app.sqlutil import patch_sets
from app.tenant import TenantContext, get_conn

router = APIRouter()

_SELECT = """
select c.*, co.name as company_name,
       coalesce((select array_agg(cp.project_id order by cp.created_at)
                 from crm_contact_projects cp where cp.contact_id = c.id), '{}')
       as project_ids
from crm_contacts c
left join crm_companies co on co.id = c.company_id
"""


@router.get("/contacts", response_model=list[ContactOut])
async def list_contacts(
    q: str | None = None,
    tag: str | None = None,
    company_id: UUID | None = None,
    project_id: UUID | None = None,
    ctx: TenantContext = Depends(require_contacts),
    conn: asyncpg.Connection = Depends(get_conn),
):
    clauses: list[str] = []
    params: list[object] = []
    if q:
        params.append(q)
        n = len(params)
        clauses.append(
            f"(c.name ilike '%' || ${n} || '%' or c.email ilike '%' || ${n} || '%'"
            f" or c.job_title ilike '%' || ${n} || '%' or co.name ilike '%' || ${n} || '%')"
        )
    if tag:
        params.append(tag)
        clauses.append(f"${len(params)} = any(c.tags)")
    if company_id:
        params.append(company_id)
        clauses.append(f"c.company_id = ${len(params)}")
    if project_id:
        params.append(project_id)
        clauses.append(
            f"exists (select 1 from crm_contact_projects cp"
            f" where cp.contact_id = c.id and cp.project_id = ${len(params)})"
        )
    where = f"where {' and '.join(clauses)}" if clauses else ""
    rows = await conn.fetch(f"{_SELECT} {where} order by c.name", *params)
    return [dict(r) for r in rows]


@router.post("/contacts", status_code=201, response_model=ContactOut)
async def create_contact(
    body: ContactIn,
    ctx: TenantContext = Depends(require_contacts),
    conn: asyncpg.Connection = Depends(get_conn),
):
    if body.company_id is not None:
        await _visible_company(conn, body.company_id)
    try:
        row = await conn.fetchrow(
            """
            insert into crm_contacts (tenant_id, company_id, name, job_title, email, phone,
                                      mobile, address, notes, tags, created_by)
            values ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11) returning id
            """,
            ctx.tenant_id,
            body.company_id,
            body.name,
            body.job_title,
            body.email,
            body.phone,
            body.mobile,
            body.address,
            body.notes,
            body.tags,
            ctx.user_id,
        )
    except asyncpg.UniqueViolationError:
        raise ApiError(409, "duplicate_email", "A contact with this email already exists") from None
    await write_audit(
        conn, ctx.tenant_id, ctx.user_id, "crm.contact_create", "contact", str(row["id"])
    )
    return await _contact_out(conn, row["id"])


@router.get("/contacts/{contact_id}", response_model=ContactOut)
async def get_contact(
    contact_id: UUID,
    ctx: TenantContext = Depends(require_contacts),
    conn: asyncpg.Connection = Depends(get_conn),
):
    return await _contact_out(conn, contact_id)


@router.patch("/contacts/{contact_id}", response_model=ContactOut)
async def patch_contact(
    contact_id: UUID,
    body: ContactPatch,
    ctx: TenantContext = Depends(require_contacts),
    conn: asyncpg.Connection = Depends(get_conn),
):
    updates = body.model_dump(exclude_unset=True)
    if not updates:
        raise ApiError(400, "no_changes", "Nothing to update")
    if updates.get("company_id") is not None:
        await _visible_company(conn, updates["company_id"])
    sets, values = patch_sets("crm_contacts", updates)
    try:
        row = await conn.fetchrow(
            f"update crm_contacts set {sets}, updated_at = now() where id = $1 returning id",
            contact_id,
            *values,
        )
    except asyncpg.UniqueViolationError:
        raise ApiError(409, "duplicate_email", "A contact with this email already exists") from None
    if row is None:
        raise ApiError(404, "not_found", "Contact not found")
    await write_audit(
        conn, ctx.tenant_id, ctx.user_id, "crm.contact_update", "contact", str(contact_id)
    )
    return await _contact_out(conn, contact_id)


@router.delete("/contacts/{contact_id}", status_code=204)
async def delete_contact(
    contact_id: UUID,
    ctx: TenantContext = Depends(require_contacts),
    conn: asyncpg.Connection = Depends(get_conn),
):
    deleted = await conn.execute("delete from crm_contacts where id = $1", contact_id)
    if deleted == "DELETE 0":
        raise ApiError(404, "not_found", "Contact not found")
    await write_audit(
        conn, ctx.tenant_id, ctx.user_id, "crm.contact_delete", "contact", str(contact_id)
    )


@router.post("/contacts/{contact_id}/projects/{project_id}", status_code=201)
async def link_project(
    contact_id: UUID,
    project_id: UUID,
    ctx: TenantContext = Depends(require_contacts),
    conn: asyncpg.Connection = Depends(get_conn),
):
    if not await conn.fetchval("select 1 from crm_contacts where id = $1", contact_id):
        raise ApiError(404, "not_found", "Contact not found")
    if not await conn.fetchval("select 1 from projects where id = $1", project_id):
        raise ApiError(404, "not_found", "Project not found")
    await conn.execute(
        """
        insert into crm_contact_projects (tenant_id, contact_id, project_id)
        values ($1, $2, $3) on conflict (contact_id, project_id) do nothing
        """,
        ctx.tenant_id,
        contact_id,
        project_id,
    )
    await write_audit(
        conn,
        ctx.tenant_id,
        ctx.user_id,
        "crm.contact_link_project",
        "contact",
        str(contact_id),
        {"project_id": str(project_id)},
    )
    return {"contact_id": str(contact_id), "project_id": str(project_id)}


@router.delete("/contacts/{contact_id}/projects/{project_id}", status_code=204)
async def unlink_project(
    contact_id: UUID,
    project_id: UUID,
    ctx: TenantContext = Depends(require_contacts),
    conn: asyncpg.Connection = Depends(get_conn),
):
    deleted = await conn.execute(
        "delete from crm_contact_projects where contact_id = $1 and project_id = $2",
        contact_id,
        project_id,
    )
    if deleted == "DELETE 0":
        raise ApiError(404, "not_found", "Link not found")
    await write_audit(
        conn,
        ctx.tenant_id,
        ctx.user_id,
        "crm.contact_unlink_project",
        "contact",
        str(contact_id),
        {"project_id": str(project_id)},
    )


async def _visible_company(conn: asyncpg.Connection, company_id: UUID) -> None:
    if not await conn.fetchval("select 1 from crm_companies where id = $1", company_id):
        raise ApiError(404, "not_found", "Company not found")


async def _contact_out(conn: asyncpg.Connection, contact_id: UUID) -> dict:
    row = await conn.fetchrow(f"{_SELECT} where c.id = $1", contact_id)
    if row is None:
        raise ApiError(404, "not_found", "Contact not found")
    return dict(row)
