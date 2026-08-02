from dataclasses import dataclass
from functools import lru_cache
from uuid import UUID

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import get_settings
from app.errors import ApiError

_bearer = HTTPBearer(auto_error=False)


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
    return jwt.PyJWKClient(url, cache_keys=True)


def decode_token(token: str) -> dict:
    settings = get_settings()
    try:
        if settings.supabase_jwks_url:
            signing_key = _jwks_client(settings.supabase_jwks_url).get_signing_key_from_jwt(token)
            return jwt.decode(
                token,
                signing_key.key,
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
    claims = decode_token(credentials.credentials)
    sub = claims.get("sub")
    if not sub:
        raise ApiError(401, "unauthenticated", "Token has no subject")
    try:
        user_id = UUID(sub)
    except ValueError as exc:
        raise ApiError(401, "unauthenticated", "Token subject is not a UUID") from exc
    return AuthUser(id=user_id, email=claims.get("email"))
