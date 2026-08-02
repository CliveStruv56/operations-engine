"""Company directory: list with contact counts, CRUD."""

from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends

from app.audit import write_audit
from app.crm.schemas import CompanyIn, CompanyOut, CompanyPatch
from app.errors import ApiError
from app.routers.crm.common import require_contacts
from app.sqlutil import like_contains, patch_sets
from app.tenant import TenantContext, get_conn

router = APIRouter()

_SELECT = """
select co.*, (select count(*) from crm_contacts c where c.company_id = co.id)::int
       as contact_count
from crm_companies co
"""


@router.get("/companies", response_model=list[CompanyOut])
async def list_companies(
    q: str | None = None,
    ctx: TenantContext = Depends(require_contacts),
    conn: asyncpg.Connection = Depends(get_conn),
):
    if q:
        rows = await conn.fetch(
            f"{_SELECT} where co.name ilike $1 order by co.name", like_contains(q)
        )
    else:
        rows = await conn.fetch(f"{_SELECT} order by co.name")
    return [dict(r) for r in rows]


@router.post("/companies", status_code=201, response_model=CompanyOut)
async def create_company(
    body: CompanyIn,
    ctx: TenantContext = Depends(require_contacts),
    conn: asyncpg.Connection = Depends(get_conn),
):
    row = await conn.fetchrow(
        """
        insert into crm_companies (tenant_id, name, website, email, phone, address_line1,
                                   address_line2, city, postcode, notes, created_by)
        values ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11) returning id
        """,
        ctx.tenant_id,
        body.name,
        body.website,
        body.email,
        body.phone,
        body.address_line1,
        body.address_line2,
        body.city,
        body.postcode,
        body.notes,
        ctx.user_id,
    )
    await write_audit(
        conn, ctx.tenant_id, ctx.user_id, "crm.company_create", "company", str(row["id"])
    )
    return await _company_out(conn, row["id"])


@router.get("/companies/{company_id}", response_model=CompanyOut)
async def get_company(
    company_id: UUID,
    ctx: TenantContext = Depends(require_contacts),
    conn: asyncpg.Connection = Depends(get_conn),
):
    return await _company_out(conn, company_id)


@router.patch("/companies/{company_id}", response_model=CompanyOut)
async def patch_company(
    company_id: UUID,
    body: CompanyPatch,
    ctx: TenantContext = Depends(require_contacts),
    conn: asyncpg.Connection = Depends(get_conn),
):
    updates = body.model_dump(exclude_unset=True)
    if not updates:
        raise ApiError(400, "no_changes", "Nothing to update")
    sets, values = patch_sets("crm_companies", updates)
    row = await conn.fetchrow(
        f"update crm_companies set {sets}, updated_at = now() where id = $1 returning id",
        company_id,
        *values,
    )
    if row is None:
        raise ApiError(404, "not_found", "Company not found")
    await write_audit(
        conn, ctx.tenant_id, ctx.user_id, "crm.company_update", "company", str(company_id)
    )
    return await _company_out(conn, company_id)


@router.delete("/companies/{company_id}", status_code=204)
async def delete_company(
    company_id: UUID,
    ctx: TenantContext = Depends(require_contacts),
    conn: asyncpg.Connection = Depends(get_conn),
):
    deleted = await conn.execute("delete from crm_companies where id = $1", company_id)
    if deleted == "DELETE 0":
        raise ApiError(404, "not_found", "Company not found")
    await write_audit(
        conn, ctx.tenant_id, ctx.user_id, "crm.company_delete", "company", str(company_id)
    )


async def _company_out(conn: asyncpg.Connection, company_id: UUID) -> dict:
    row = await conn.fetchrow(f"{_SELECT} where co.id = $1", company_id)
    if row is None:
        raise ApiError(404, "not_found", "Company not found")
    return dict(row)
