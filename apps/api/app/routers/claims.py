"""The claims register — what this workspace asserts about itself.

Unflagged, like the funder forms it feeds and unlike the drafting modules that
consume it. Every vertical needs these facts, and a workspace with no vertical
module at all still benefits from having them in one place with a date on them.

Writes are member-level rather than admin, for the same reason question sets
are: the person who finds the insurance certificate on a Tuesday should not
have to wait for whoever holds the role. The safety mechanism was never the
role gate — it is that nothing enters confirmed without somebody confirming it,
and that a stale claim says so wherever it is used.

Register imports are the exception on rate limiting: they spend a platform-wide
allowance shared across every workspace, so one workspace cannot be allowed to
exhaust it.
"""

import re
from datetime import date
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends

from app.audit import write_audit
from app.claims.ccni import fetch_ccni
from app.claims.registers import fetch_charity_commission, fetch_companies_house, fetch_oscr
from app.claims.schemas import (
    COMPANY_NUMBER,
    EW_CHARITY_NUMBER,
    NI_CHARITY_NUMBER,
    SCOTTISH_CHARITY_NUMBER,
    ClaimIn,
    ClaimKindOut,
    ClaimOut,
    ClaimPatch,
    ClaimSummaryOut,
    RegisterImportIn,
    RegisterImportOut,
)
from app.claims.service import (
    claims_summary,
    create_claim,
    delete_claim,
    get_claim,
    import_register_facts,
    list_claims,
    load_kinds,
    update_claim,
)
from app.errors import ApiError
from app.ratelimit import rate_limiter
from app.tenant import TenantContext, get_conn, require_role

router = APIRouter(tags=["claims"])


@router.get("/claims", response_model=list[ClaimOut])
async def list_all(
    status: str | None = None,
    ctx: TenantContext = Depends(require_role("member")),
    conn: asyncpg.Connection = Depends(get_conn),
):
    return await list_claims(conn, date.today(), status=status)


@router.get("/claims/kinds", response_model=list[ClaimKindOut])
async def list_kinds(
    ctx: TenantContext = Depends(require_role("member")),
    conn: asyncpg.Connection = Depends(get_conn),
):
    """The catalogue of fact types.

    Declared before `/claims/{claim_id}` so the literal path wins the route
    match — otherwise "kinds" is parsed as a claim id and 422s.
    """
    return list((await load_kinds(conn)).values())


@router.get("/claims/summary", response_model=ClaimSummaryOut)
async def summary(
    ctx: TenantContext = Depends(require_role("member")),
    conn: asyncpg.Connection = Depends(get_conn),
):
    """What the register is waiting on, for a count shown outside the register.

    Declared before `/claims/{claim_id}` for the same reason as `kinds` — a
    literal path registered after the parameterised one never matches.

    Member-level like the rest: a count of facts needing a check is exactly the
    thing every member should see, and it reveals nothing a member cannot
    already read on the register screen.
    """
    return await claims_summary(conn, date.today())


@router.get("/claims/{claim_id}", response_model=ClaimOut)
async def get_one(
    claim_id: UUID,
    ctx: TenantContext = Depends(require_role("member")),
    conn: asyncpg.Connection = Depends(get_conn),
):
    claim = await get_claim(conn, claim_id, date.today())
    if claim is None:
        raise ApiError(404, "not_found", "Claim not found")
    return claim


@router.post("/claims", status_code=201, response_model=ClaimOut)
async def create(
    body: ClaimIn,
    ctx: TenantContext = Depends(require_role("member")),
    conn: asyncpg.Connection = Depends(get_conn),
):
    claim = await create_claim(conn, ctx.tenant_id, ctx.user_id, body, date.today())
    await write_audit(
        conn,
        ctx.tenant_id,
        ctx.user_id,
        "claims.create",
        "claim",
        str(claim.id),
        {"kind": claim.kind, "subject": claim.subject},
    )
    return claim


@router.patch("/claims/{claim_id}", response_model=ClaimOut)
async def update(
    claim_id: UUID,
    body: ClaimPatch,
    ctx: TenantContext = Depends(require_role("member")),
    conn: asyncpg.Connection = Depends(get_conn),
):
    claim = await update_claim(conn, ctx.tenant_id, ctx.user_id, claim_id, body, date.today())
    action = {
        "confirmed": "claims.confirm",
        "rejected": "claims.reject",
    }.get(body.status or "", "claims.verify" if body.verified else "claims.update")
    await write_audit(
        conn, ctx.tenant_id, ctx.user_id, action, "claim", str(claim_id), {"kind": claim.kind}
    )
    return claim


@router.delete("/claims/{claim_id}", status_code=204)
async def remove(
    claim_id: UUID,
    ctx: TenantContext = Depends(require_role("member")),
    conn: asyncpg.Connection = Depends(get_conn),
):
    await delete_claim(conn, claim_id)
    await write_audit(conn, ctx.tenant_id, ctx.user_id, "claims.delete", "claim", str(claim_id))


async def _import(
    fetcher,
    number: str,
    body: RegisterImportIn,
    ctx: TenantContext,
    conn: asyncpg.Connection,
    *,
    shared_allowance: bool = True,
) -> RegisterImportOut:
    """Shared body of the four import routes.

    The dead-record gate lives here rather than in each client: a dissolved
    company and a removed charity both return complete, plausible data, and a
    bid asserting current registration from a dead record is the worst thing
    this feature could produce. Overriding it is possible — a dissolved
    predecessor entity is a real thing to want on file — but it has to be asked
    for, and the answer says which status it was overridden from.

    `shared_allowance` is the rate-limit switch: three registers spend
    platform-wide API keys; the CCNI snapshot is a local read and spends
    nothing another workspace needs.
    """
    if shared_allowance:
        await rate_limiter.check_register_lookup(ctx.tenant_id)
    found = await fetcher(number)
    if not found.active and not body.allow_inactive:
        raise ApiError(
            409,
            "register_record_inactive",
            f"That record's status is “{found.registration_status}”, not active."
            " Re-run with allow_inactive if you meant to import it anyway.",
        )

    proposed, unchanged, unknown = await import_register_facts(
        conn, ctx.tenant_id, ctx.user_id, found, date.today()
    )
    await write_audit(
        conn,
        ctx.tenant_id,
        ctx.user_id,
        "claims.import",
        "register",
        found.register,
        {
            "number": number,
            "proposed": len(proposed),
            "unchanged": unchanged,
            "status": found.registration_status,
        },
    )
    return RegisterImportOut(
        register_key=found.register,
        source_url=found.source_url,
        registration_status=found.registration_status,
        inactive=not found.active,
        proposed=proposed,
        unchanged=unchanged,
        skipped_unknown_kinds=unknown,
    )


@router.post("/claims/import/companies-house", response_model=RegisterImportOut)
async def import_companies_house(
    body: RegisterImportIn,
    ctx: TenantContext = Depends(require_role("member")),
    conn: asyncpg.Connection = Depends(get_conn),
):
    """Look a company up at Companies House and propose what it says.

    Works for any UK company including Scottish and Northern Irish ones, and
    for a charitable company its directors are its charity trustees — which is
    what gives a Scottish charitable company a usable board list without OSCR.
    """
    number = _normalise(body.number, COMPANY_NUMBER, "an eight-character company number")
    return await _import(fetch_companies_house, number, body, ctx, conn)


@router.post("/claims/import/charity-commission", response_model=RegisterImportOut)
async def import_charity_commission(
    body: RegisterImportIn,
    ctx: TenantContext = Depends(require_role("member")),
    conn: asyncpg.Connection = Depends(get_conn),
):
    """England and Wales only. Scottish charities use the OSCR route."""
    number = _normalise(body.number, EW_CHARITY_NUMBER, "a six to eight digit charity number")
    return await _import(fetch_charity_commission, number, body, ctx, conn)


@router.post("/claims/import/oscr", response_model=RegisterImportOut)
async def import_oscr(
    body: RegisterImportIn,
    ctx: TenantContext = Depends(require_role("member")),
    conn: asyncpg.Connection = Depends(get_conn),
):
    """The Scottish Charity Register.

    Richer than the other two on finance — the annual return carries a series
    of years and staff numbers, which no other UK register publishes.
    """
    number = _normalise(
        body.number, SCOTTISH_CHARITY_NUMBER, "a Scottish charity number like SC012345"
    )
    return await _import(fetch_oscr, number, body, ctx, conn)


@router.post("/claims/import/ccni", response_model=RegisterImportOut)
async def import_ccni(
    body: RegisterImportIn,
    ctx: TenantContext = Depends(require_role("member")),
    conn: asyncpg.Connection = Depends(get_conn),
):
    """Northern Ireland, from the operator-refreshed snapshot.

    CCNI publishes no lookup API, so this reads `ref_ccni_charities` — loaded
    by the operator from the register's bulk export (`python -m
    app.claims.ccni`). A local read spends no shared allowance, hence no rate
    limit; the trade is freshness, which is why review dates on these claims
    derive from the snapshot's own loaded date.
    """
    number = _normalise(
        body.number, NI_CHARITY_NUMBER, "a Northern Ireland charity number like NIC100012"
    ).removeprefix("NIC")

    async def fetcher(n: str):
        return await fetch_ccni(conn, n)

    return await _import(fetcher, number, body, ctx, conn, shared_allowance=False)


def _normalise(raw: str, pattern: str, expected: str) -> str:
    """Uppercase, strip spaces, then validate.

    People copy "sc 012 345" off a letterhead. Normalising before validating
    accepts that; validating before building a URL is what keeps the register
    clients free of any URL-construction defence, because a value that matches
    one of these patterns cannot express a path segment or a host.
    """
    candidate = re.sub(r"\s+", "", raw).upper()
    if not re.match(pattern, candidate):
        raise ApiError(422, "bad_register_number", f"That does not look like {expected}")
    return candidate
