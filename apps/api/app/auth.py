import time
from dataclasses import dataclass
from functools import lru_cache
from threading import Lock
from uuid import UUID

import anyio.to_thread
import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import get_settings
from app.errors import ApiError

_bearer = HTTPBearer(auto_error=False)

# A JWKS fetch is a blocking HTTPS round trip made *before* any signature is
# checked, so an unauthenticated caller decides when one happens. PyJWT's
# default 30s timeout on the event loop is enough for a handful of requests a
# second to stall the whole API; 5s off the loop is not.
_JWKS_TIMEOUT = 5.0
# PyJWT memoises successful lookups only, so a token carrying an unknown `kid`
# forces a refresh every time. Remember the misses for a minute — long enough
# to make the flood cheap, short enough that a genuinely new signing key is
# picked up quickly.
_JWKS_MISS_TTL = 60.0
_JWKS_MISS_MAX = 1024

_kid_misses: dict[str, float] = {}
_kid_misses_lock = Lock()


@dataclass(frozen=True)
class AuthUser:
    id: UUID
    email: str | None


def is_platform_admin(email: str | None) -> bool:
    """Operator identity: login email is on the PLATFORM_ADMIN_EMAILS list.
    Empty list = no platform admins (console disabled)."""
    return email is not None and email.lower() in get_settings().platform_admin_email_list


@lru_cache
def _jwks_client(url: str) -> jwt.PyJWKClient:
    return jwt.PyJWKClient(url, cache_keys=True, timeout=_JWKS_TIMEOUT)


def _unverified_kid(token: str) -> str | None:
    try:
        kid = jwt.get_unverified_header(token).get("kid")
    except jwt.PyJWTError:
        return None
    return kid if isinstance(kid, str) else None


def _kid_recently_missed(kid: str) -> bool:
    with _kid_misses_lock:
        expiry = _kid_misses.get(kid)
        if expiry is None:
            return False
        if expiry <= time.monotonic():
            _kid_misses.pop(kid, None)
            return False
        return True


def _remember_kid_miss(kid: str) -> None:
    now = time.monotonic()
    with _kid_misses_lock:
        # The caller supplies these keys, so the cache has to be bounded.
        if len(_kid_misses) >= _JWKS_MISS_MAX:
            for stale in [k for k, expiry in _kid_misses.items() if expiry <= now]:
                del _kid_misses[stale]
            if len(_kid_misses) >= _JWKS_MISS_MAX:
                _kid_misses.clear()
        _kid_misses[kid] = now + _JWKS_MISS_TTL


def _fetch_signing_key(url: str, token: str, kid: str | None):
    """Blocking: runs in a worker thread, never on the event loop."""
    try:
        return _jwks_client(url).get_signing_key_from_jwt(token).key
    except jwt.PyJWKClientConnectionError:
        # The key set was unreachable — that says nothing about this `kid`, so
        # a network blip must not blacklist a legitimate one.
        raise
    except jwt.PyJWKClientError:
        if kid is not None:
            _remember_kid_miss(kid)
        raise


async def decode_token(token: str) -> dict:
    settings = get_settings()
    try:
        if settings.supabase_jwks_url:
            kid = _unverified_kid(token)
            if kid is not None and _kid_recently_missed(kid):
                raise ApiError(401, "unauthenticated", "Invalid token: unknown signing key")
            key = await anyio.to_thread.run_sync(
                _fetch_signing_key, settings.supabase_jwks_url, token, kid
            )
            return jwt.decode(
                token,
                key,
                algorithms=["RS256", "ES256"],
                audience=settings.jwt_audience,
            )
        if settings.supabase_jwt_secret:
            return jwt.decode(
                token,
                settings.supabase_jwt_secret,
                algorithms=["HS256"],
                audience=settings.jwt_audience,
            )
    except jwt.PyJWTError as exc:
        raise ApiError(401, "unauthenticated", f"Invalid token: {exc}") from exc
    raise ApiError(500, "auth_misconfigured", "No JWT verification method configured")


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> AuthUser:
    if credentials is None:
        raise ApiError(401, "unauthenticated", "Missing bearer token")
    claims = await decode_token(credentials.credentials)
    sub = claims.get("sub")
    if not sub:
        raise ApiError(401, "unauthenticated", "Token has no subject")
    try:
        user_id = UUID(sub)
    except ValueError as exc:
        raise ApiError(401, "unauthenticated", "Token subject is not a UUID") from exc
    return AuthUser(id=user_id, email=claims.get("email"))
