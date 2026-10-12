"""Rate limits the suite otherwise never reaches: REDIS_URL is empty in tests,
so the limiter is a no-op unless a test hands it a connection. These use an
in-memory stand-in for the two Redis calls the limiter makes."""

from uuid import uuid4

import pytest

from app.config import Settings, get_settings
from app.ratelimit import rate_limiter
from tests.conftest import auth, make_token, seed_tenant


class FakeRedis:
    def __init__(self) -> None:
        self.counts: dict[str, int] = {}
        self.ttls: dict[str, int] = {}

    async def incr(self, key: str) -> int:
        self.counts[key] = self.counts.get(key, 0) + 1
        return self.counts[key]

    async def expire(self, key: str, seconds: int) -> None:
        self.ttls[key] = seconds


@pytest.fixture
def fake_redis(monkeypatch):
    fake = FakeRedis()
    monkeypatch.setattr(rate_limiter, "_conn", lambda: fake)
    return fake


def test_signup_is_closed_unless_a_service_opts_in(monkeypatch):
    """A new service that forgets OPEN_SIGNUP must not open self-serve signup."""
    monkeypatch.delenv("OPEN_SIGNUP", raising=False)
    assert Settings(_env_file=None).open_signup is False  # type: ignore[call-arg]


async def test_tenant_create_is_rate_limited_per_account(client, fake_redis, monkeypatch):
    monkeypatch.setenv("TENANT_CREATE_RATE_LIMIT_PER_DAY", "2")
    get_settings.cache_clear()
    try:
        user = uuid4()
        for i in range(2):
            r = await client.post("/api/v1/tenants", json={"name": f"ws {i}"}, headers=auth(user))
            assert r.status_code == 201, r.text
        r = await client.post("/api/v1/tenants", json={"name": "ws 3"}, headers=auth(user))
        assert r.status_code == 429
        assert r.json()["error"]["code"] == "rate_limited"
        assert fake_redis.ttls[f"rl:tenantcreate:{user}"] == 86400

        # The count is per account, not global.
        r = await client.post("/api/v1/tenants", json={"name": "other"}, headers=auth(uuid4()))
        assert r.status_code == 201, r.text

        # Platform admins are exempt — the operator console path must not stall.
        admin = {"Authorization": f"Bearer {make_token(uuid4(), email='operator@example.com')}"}
        for i in range(3):
            r = await client.post("/api/v1/tenants", json={"name": f"op {i}"}, headers=admin)
            assert r.status_code == 201, r.text
    finally:
        monkeypatch.delenv("TENANT_CREATE_RATE_LIMIT_PER_DAY", raising=False)
        get_settings.cache_clear()


async def test_transcribe_is_rate_limited_per_tenant(client, fake_redis, monkeypatch):
    monkeypatch.setenv("TRANSCRIBE_RATE_LIMIT_PER_HOUR", "1")
    get_settings.cache_clear()
    try:
        t = await seed_tenant(client, f"rltx-{uuid4().hex[:6]}")
        body = {"source": "1. Describe your project. (250 words)"}
        headers = auth(t.owner_id, t.id)
        # No gateway key in tests, so the first call stops at 503 — after the
        # limiter has counted it, which is the point: the count comes first.
        first = await client.post("/api/v1/question-sets/transcribe", json=body, headers=headers)
        assert first.status_code == 503
        second = await client.post("/api/v1/question-sets/transcribe", json=body, headers=headers)
        assert second.status_code == 429
        assert fake_redis.counts[f"rl:transcribe:{t.id}"] == 2
    finally:
        monkeypatch.delenv("TRANSCRIBE_RATE_LIMIT_PER_HOUR", raising=False)
        get_settings.cache_clear()
