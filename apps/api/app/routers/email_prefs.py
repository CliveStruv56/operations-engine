"""Digest unsubscribe — the one endpoint reached from an email, not the app.

No session: the link's HMAC token is the authorisation, keyed on
(tenant_id, membership_id) so it proves the pair and nothing else. GET shows
a confirm button rather than acting — mail scanners prefetch links, and a
prefetch must not change anybody's preference. The confirm buttons POST with
the same query string (query params, deliberately: a form body would pull in
a multipart dependency for three fields). The POST does the work inside an
ordinary tenant transaction — the memberships policy accepts the tenant
predicate, so no cross-tenant connection is involved — and the audit row's
acting user is the member the preference belongs to.

The same signed link can also switch the digest back on (`action=resume`) —
without that, an accidental click is permanent and the only fix is SQL.
"""

import hmac
from typing import Literal
from uuid import UUID

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from app.audit import write_audit
from app.db import db
from app.email import unsubscribe_token
from app.errors import ApiError

router = APIRouter(tags=["email"])

_PAGE = """<!doctype html>
<html><head><meta charset="utf-8"><title>Flowgrid email preferences</title></head>
<body style="font-family: sans-serif; max-width: 26rem; margin: 4rem auto; line-height: 1.5">
<h1 style="font-size: 1.2rem">Flowgrid digest emails</h1>
{body}
</body></html>"""

_CONFIRM = """
<p>Stop receiving the weekly facts digest for this workspace?</p>
<form method="post" action="/api/v1/email/digest?{query}&action=pause"
      style="display: inline"><button type="submit">Stop the digest</button></form>
<form method="post" action="/api/v1/email/digest?{query}&action=resume"
      style="display: inline; margin-left: .5rem">
<button type="submit">Keep receiving it</button></form>"""


def _check_token(tenant: UUID, membership: UUID, token: str) -> None:
    if not hmac.compare_digest(unsubscribe_token(tenant, membership), token):
        raise ApiError(400, "invalid_token", "This link is not valid")


@router.get("/email/digest", response_class=HTMLResponse)
async def digest_pref_page(tenant: UUID, membership: UUID, token: str) -> HTMLResponse:
    _check_token(tenant, membership, token)
    query = f"tenant={tenant}&membership={membership}&token={token}"
    return HTMLResponse(_PAGE.format(body=_CONFIRM.format(query=query)))


@router.post("/email/digest", response_class=HTMLResponse)
async def set_digest_pref(
    tenant: UUID, membership: UUID, token: str, action: Literal["pause", "resume"]
) -> HTMLResponse:
    _check_token(tenant, membership, token)
    opt_out = action == "pause"
    async with db.tenant_tx(membership, tenant) as conn:
        row = await conn.fetchrow(
            "update memberships set digest_opt_out = $2 where id = $1 and tenant_id = $3"
            " returning user_id",
            membership,
            opt_out,
            tenant,
        )
        if row is None:
            raise ApiError(404, "not_found", "This membership no longer exists")
        await write_audit(
            conn,
            tenant,
            row["user_id"],
            "member.digest_pref",
            "membership",
            str(membership),
            meta={"digest_opt_out": opt_out},
        )
    message = (
        "<p>Done — no more digest emails for this workspace. Changed your mind?"
        " The same link can switch them back on.</p>"
        if opt_out
        else "<p>Done — you'll keep receiving the weekly digest.</p>"
    )
    return HTMLResponse(_PAGE.format(body=message))
