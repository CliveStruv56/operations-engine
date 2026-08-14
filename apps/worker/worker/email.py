"""Resend transport + unsubscribe token — deliberate mirror of `app/email.py`.

Same rule as `worker/drafting/retrieval.py`: the worker cannot import from the
API app, so the client and (especially) the token algorithm are duplicated and
must stay in step. The token matters most — the API's /email/digest endpoint
verifies exactly what this side signs into each digest's unsubscribe link.
"""

import hashlib
import hmac
import logging

import httpx

from worker.settings import get_settings

logger = logging.getLogger("worker.email")

RESEND_URL = "https://api.resend.com/emails"
TIMEOUT_S = 10.0


async def send_email(to: str, subject: str, text: str) -> bool:
    """One message; True only when Resend accepted it. Best-effort by
    contract — a digest that fails to send is logged and skipped, never
    retried into somebody's inbox twice."""
    settings = get_settings()
    if not settings.resend_api_key:
        return False
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_S) as client:
            resp = await client.post(
                RESEND_URL,
                headers={"Authorization": f"Bearer {settings.resend_api_key}"},
                json={
                    "from": settings.email_from,
                    "to": [to],
                    "subject": subject,
                    "text": text,
                },
            )
        resp.raise_for_status()
        return True
    except httpx.HTTPError:
        logger.warning("digest email to %s failed", to)
        return False


def unsubscribe_token(tenant_id: str, membership_id: str) -> str:
    """Must produce byte-for-byte what `app/email.py::unsubscribe_token` does."""
    secret = get_settings().email_unsubscribe_secret
    return hmac.new(
        secret.encode(), f"{tenant_id}:{membership_id}".encode(), hashlib.sha256
    ).hexdigest()
