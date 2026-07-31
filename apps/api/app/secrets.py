"""Fernet encryption for tenant LiteLLM virtual keys at rest.

LiteLLM stores only key hashes server-side — the plaintext token exists
solely in our tenants row, so it is encrypted there. An empty
LITELLM_KEY_ENCRYPTION_KEY means pass-through (unit tests / gateway
disabled); startup refuses that combination when the gateway is enabled.
"""

from cryptography.fernet import Fernet, InvalidToken

from app.config import get_settings
from app.errors import ApiError


def _fernet() -> Fernet | None:
    key = get_settings().litellm_key_encryption_key
    return Fernet(key.encode()) if key else None


def encrypt_llm_key(token: str | None) -> str | None:
    fernet = _fernet()
    if token is None or fernet is None:
        return token
    return fernet.encrypt(token.encode()).decode()


def decrypt_llm_key(stored: str | None) -> str | None:
    fernet = _fernet()
    if stored is None or fernet is None:
        return stored
    try:
        return fernet.decrypt(stored.encode()).decode()
    except InvalidToken as exc:
        # Never fall through to using ciphertext as a bearer token.
        raise ApiError(
            503,
            "llm_unavailable",
            "Workspace model key cannot be decrypted — check LITELLM_KEY_ENCRYPTION_KEY",
        ) from exc
