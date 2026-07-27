"""No endpoint is reachable without a valid JWT (spec §11)."""

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


def _all_protected_routes():
    for route in app.routes:
        if isinstance(route, APIRoute) and route.path not in PUBLIC_PATHS:
            for method in route.methods - {"HEAD", "OPTIONS"}:
                yield method, route.path.replace("{membership_id}", str(uuid4()))


async def test_every_endpoint_requires_token(client):
    for method, path in _all_protected_routes():
        resp = await client.request(method, path, json={})
        assert resp.status_code == 401, f"{method} {path} -> {resp.status_code}"
        assert resp.json()["error"]["code"] == "unauthenticated"


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
