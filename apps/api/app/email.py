"""Resend transport — the platform's one email client (plain httpx, no SDK).

Empty RESEND_API_KEY = email disabled, matching the gateway/storage/register
convention: senders no-op and report False rather than failing at the network.
Sending is best-effort everywhere by contract — an invite exists whether or
not its notification landed, so callers treat False as "tell the user to copy
the link", never as an error.

The worker keeps a deliberate mirror of this client and the unsubscribe token
(`worker/email.py`) — same rule as `worker/drafting/retrieval.py`: the two
must stay in step, and the token algorithm especially so, because the API
verifies what the worker signed.
"""

import hashlib
import hmac
import logging
from uuid import UUID

import httpx

from app.config import get_settings

logger = logging.getLogger("app.email")

RESEND_URL = "https://api.resend.com/emails"
TIMEOUT_S = 10.0


class EmailClient:
    @property
    def enabled(self) -> bool:
        return bool(get_settings().resend_api_key)

    async def send(
        self,
        to: str,
        subject: str,
        text: str,
        *,
        client: httpx.AsyncClient | None = None,
    ) -> bool:
        """One message; True only when Resend accepted it."""
        settings = get_settings()
        if not settings.resend_api_key:
            return False
        payload = {
            "from": settings.email_from,
            "to": [to],
            "subject": subject,
            "text": text,
        }
        headers = {"Authorization": f"Bearer {settings.resend_api_key}"}
        try:
            if client is None:
                async with httpx.AsyncClient(timeout=TIMEOUT_S) as own:
                    resp = await own.post(RESEND_URL, headers=headers, json=payload)
            else:  # injected in tests
                resp = await client.post(RESEND_URL, headers=headers, json=payload)
            resp.raise_for_status()
            return True
        except httpx.HTTPError:
            # Address only — never the body, which may carry an invite token.
            logger.warning("email to %s failed", to)
            return False


email_client = EmailClient()


def unsubscribe_token(tenant_id: UUID | str, membership_id: UUID | str) -> str:
    """HMAC for the digest unsubscribe link — proof the link came from us,
    since the endpoint has no session to lean on. Keyed on both ids so a
    token cannot be replayed against another workspace's membership."""
    secret = get_settings().email_unsubscribe_secret
    return hmac.new(
        secret.encode(), f"{tenant_id}:{membership_id}".encode(), hashlib.sha256
    ).hexdigest()


def invite_email(workspace: str, role: str, link: str, expires_days: int) -> tuple[str, str]:
    """(subject, text) for an invite. Plain text on purpose — a joining link
    from a workspace tool, not a campaign."""
    subject = f"You're invited to {workspace} on Flowgrid"
    text = (
        f"You've been invited to join {workspace} as {'an' if role[0] in 'aeiou' else 'a'}"
        f" {role}.\n\n"
        f"Accept the invite:\n{link}\n\n"
        f"The link expires in {expires_days} days. If you weren't expecting this,"
        " you can ignore it."
    )
    return subject, text
