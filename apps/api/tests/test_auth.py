"""No endpoint is reachable without a valid JWT (spec §11)."""

import re
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt as pyjwt
from fastapi.routing import APIRoute

from app.main import app
from tests.conftest import auth, make_token

PUBLIC_PATHS = {
    "/health",
    "/api/v1/health",
    "/openapi.json",
    "/docs",
    "/docs/oauth2-redirect",
    "/redoc",
}

# Unauthenticated by design, and the only ones: the digest links are authorised
# by an HMAC in the URL, not by a JWT, because they are followed from an email.
HMAC_PATHS = {
    "/api/v1/email/digest",
}

# The walk below reaches into FastAPI's include_router internals, so it can
# break silently the way the old `app.routes` scan did — that version found two
# routes, both public, and so asserted nothing at all while passing. A floor on
# the count turns that failure mode from invisible into a red test.
MIN_PROTECTED_ROUTES = 150

_PATH_PARAM = re.compile(r"\{[^{}]+\}")


def _iter_api_routes(routes, prefix: str = ""):
    """Every APIRoute in the app, with its full path.

    Since FastAPI 0.140 / Starlette 1.3, `include_router()` no longer copies a
    router's routes onto the app: `app.routes` holds an `_IncludedRouter`
    wrapper carrying the original router and the prefix it was mounted under,
    and included routers nest. Recurse through both.
    """
    for route in routes:
        if isinstance(route, APIRoute):
            yield prefix + route.path, route
            continue
        included = getattr(route, "original_router", None)
        if included is not None:
            yield from _iter_api_routes(included.routes, prefix + route.include_context.prefix)


def _all_protected_routes():
    for path, route in _iter_api_routes(app.routes):
        if path in PUBLIC_PATHS or path in HMAC_PATHS:
            continue
        concrete = _PATH_PARAM.sub(str(uuid4()), path)
        for method in sorted(route.methods - {"HEAD", "OPTIONS"}):
            yield method, concrete


async def test_route_walk_sees_the_whole_app():
    """The guard on the guard: if the walk ever empties itself, fail loudly."""
    found = list(_iter_api_routes(app.routes))
    assert len(found) > MIN_PROTECTED_ROUTES, (
        f"route walk found only {len(found)} routes — include_router's shape has "
        "changed again and test_every_endpoint_requires_token is checking nothing"
    )
    paths = {path for path, _ in found}
    # The docs paths are Starlette Routes, not APIRoutes, so they never appear.
    assert PUBLIC_PATHS - paths == {"/openapi.json", "/docs", "/docs/oauth2-redirect", "/redoc"}
    assert HMAC_PATHS <= paths


async def test_every_endpoint_requires_token(client):
    checked = 0
    for method, path in _all_protected_routes():
        resp = await client.request(method, path, json={})
        assert resp.status_code == 401, f"{method} {path} -> {resp.status_code}"
        assert resp.json()["error"]["code"] == "unauthenticated"
        checked += 1
    assert checked > MIN_PROTECTED_ROUTES, f"only {checked} routes checked"


async def test_bad_signature_rejected(client):
    token = pyjwt.encode(
        {
            "sub": str(uuid4()),
            "aud": "authenticated",
            "exp": datetime.now(UTC) + timedelta(hours=1),
        },
        "wrong-secret-that-is-long-enough-for-hs256",
        algorithm="HS256",
    )
    resp = await client.get("/api/v1/tenants/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401


async def test_expired_token_rejected(client):
    token = make_token(uuid4(), exp=datetime.now(UTC) - timedelta(minutes=1))
    resp = await client.get("/api/v1/tenants/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401


async def test_wrong_audience_rejected(client):
    token = make_token(uuid4(), aud="anon")
    resp = await client.get("/api/v1/tenants/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401


async def test_health_is_public(client):
    for path in ("/health", "/api/v1/health"):
        resp = await client.get(path)
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


async def test_valid_token_unknown_user_has_no_memberships(client):
    resp = await client.get("/api/v1/tenants/me", headers=auth(uuid4()))
    assert resp.status_code == 400
    body = resp.json()["error"]
    assert body["code"] == "tenant_required"
    assert body["memberships"] == []
