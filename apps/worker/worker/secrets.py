"""Decrypt the tenant LiteLLM virtual key (Fernet, shared with the API).

Empty LITELLM_KEY_ENCRYPTION_KEY = pass-through (tests / gateway disabled).
"""

from cryptography.fernet import Fernet, InvalidToken

from worker.settings import get_settings


def decrypt_llm_key(stored: str | None) -> str | None:
    key = get_settings().litellm_key_encryption_key
    if stored is None or not key:
        return stored
    try:
        return Fernet(key.encode()).decrypt(stored.encode()).decode()
    except InvalidToken as exc:
        # Never use ciphertext as a bearer token — fail the job loudly.
        raise RuntimeError(
            "Cannot decrypt tenant model key — check LITELLM_KEY_ENCRYPTION_KEY"
        ) from exc
