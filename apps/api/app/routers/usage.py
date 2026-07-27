import re
from datetime import UTC, date, datetime

import asyncpg
from fastapi import APIRouter, Depends, Query

from app.errors import ApiError
from app.schemas import UsageSummaryOut
from app.tenant import TenantContext, get_conn, require_role

router = APIRouter(tags=["usage"])


@router.get("/usage/summary", response_model=UsageSummaryOut)
async def usage_summary(
    month: str | None = Query(default=None, description="YYYY-MM, defaults to current month"),
    ctx: TenantContext = Depends(require_role("member")),
    conn: asyncpg.Connection = Depends(get_conn),
):
    if month is None:
        month = datetime.now(UTC).strftime("%Y-%m")
    if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", month):
        raise ApiError(400, "invalid_month", "month must be YYYY-MM")
    start = date.fromisoformat(f"{month}-01")

    where = "created_at >= $1::date and created_at < $1::date + interval '1 month'"
    totals = await conn.fetchrow(
        f"""
        select coalesce(sum(tokens_in), 0) tokens_in,
               coalesce(sum(tokens_out), 0) tokens_out,
               coalesce(sum(cost_usd), 0) cost_usd,
               count(*) requests
        from usage_events where {where}
        """,
        start,
    )

    async def buckets(column: str) -> list[dict]:
        rows = await conn.fetch(
            f"""
            select coalesce({column}::text, 'unknown') key,
                   coalesce(sum(tokens_in), 0) tokens_in,
                   coalesce(sum(tokens_out), 0) tokens_out,
                   coalesce(sum(cost_usd), 0) cost_usd,
                   count(*) requests
            from usage_events where {where}
            group by 1 order by cost_usd desc
            """,
            start,
        )
        return [{**dict(r), "cost_usd": float(r["cost_usd"])} for r in rows]

    return {
        "month": month,
        "tokens_in": totals["tokens_in"],
        "tokens_out": totals["tokens_out"],
        "cost_usd": float(totals["cost_usd"]),
        "requests": totals["requests"],
        "by_user": await buckets("user_id"),
        "by_model": await buckets("model"),
    }
