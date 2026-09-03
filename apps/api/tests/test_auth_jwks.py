"""The JWKS path: an unauthenticated caller must not be able to stall the loop.

Production verifies tokens against Supabase's JWKS, which means a blocking
HTTPS fetch decided by the caller's `kid` runs *before* any signature is
checked. The rest of the suite runs on the HS256 secret, so this file is the
only cover the JWKS branch has.
"""

import asyncio
import time

import jwt
import pytest

from app import auth
from app.config import get_settings
from app.errors import ApiError


@pytest.fixture(autouse=True)
def jwks_enabled(monkeypatch):
    monkeypatch.setattr(get_settings(), "supabase_jwks_url", "https://example.invalid/jwks")
    auth._kid_misses.clear()
    yield
    auth._kid_misses.clear()


_SECRET = "secret-long-enough-for-hs256-sha256"


def _token(kid: str) -> str:
    return jwt.encode({"sub": "irrelevant"}, _SECRET, headers={"kid": kid})


class _FakeClient:
    """Stands in for PyJWKClient: counts lookups, blocks like a real fetch."""

    def __init__(self, error: Exception, delay: float = 0.0) -> None:
        self.error = error
        self.delay = delay
        self.calls = 0

    def get_signing_key_from_jwt(self, token: str):
        self.calls += 1
        if self.delay:
            time.sleep(self.delay)
        raise self.error


def _install(monkeypatch, client: _FakeClient) -> _FakeClient:
    monkeypatch.setattr(auth, "_jwks_client", lambda url: client)
    return client


async def test_jwks_lookup_runs_off_the_event_loop(monkeypatch):
    client = _install(monkeypatch, _FakeClient(jwt.PyJWKClientError("no key"), delay=0.3))

    ticks = 0

    async def heartbeat() -> None:
        nonlocal ticks
        while True:
            await asyncio.sleep(0.01)
            ticks += 1

    beat = asyncio.create_task(heartbeat())
    try:
        with pytest.raises(ApiError):
            await auth.decode_token(_token("slow-kid"))
    finally:
        beat.cancel()

    assert client.calls == 1
    # A synchronous fetch on the loop pins ticks at 0 for its whole duration.
    assert ticks >= 5, f"event loop ticked only {ticks}x during a 0.3s JWKS fetch"


async def test_unknown_kid_fetches_once_then_is_refused_from_cache(monkeypatch):
    client = _install(monkeypatch, _FakeClient(jwt.PyJWKClientError("no key")))

    for _ in range(5):
        with pytest.raises(ApiError) as exc:
            await auth.decode_token(_token("bogus-kid"))
        assert exc.value.status_code == 401

    assert client.calls == 1, "an unknown kid forced a JWKS fetch per request"


async def test_each_unknown_kid_costs_at_most_one_fetch(monkeypatch):
    client = _install(monkeypatch, _FakeClient(jwt.PyJWKClientError("no key")))

    for i in range(3):
        with pytest.raises(ApiError):
            await auth.decode_token(_token(f"kid-{i}"))
        with pytest.raises(ApiError):
            await auth.decode_token(_token(f"kid-{i}"))

    assert client.calls == 3


async def test_miss_cache_is_bounded(monkeypatch):
    client = _install(monkeypatch, _FakeClient(jwt.PyJWKClientError("no key")))
    monkeypatch.setattr(auth, "_JWKS_MISS_MAX", 8)

    for i in range(40):
        with pytest.raises(ApiError):
            await auth.decode_token(_token(f"flood-{i}"))

    assert len(auth._kid_misses) <= 8
    assert client.calls == 40


async def test_unreachable_jwks_does_not_blacklist_the_kid(monkeypatch):
    """A network blip is not evidence about the key, so it must not be cached."""
    client = _install(monkeypatch, _FakeClient(jwt.PyJWKClientConnectionError("unreachable")))

    for _ in range(3):
        with pytest.raises(ApiError):
            await auth.decode_token(_token("real-kid"))

    assert client.calls == 3
    assert not auth._kid_misses


async def test_jwks_client_has_a_short_timeout():
    real = auth._jwks_client("https://example.invalid/jwks-timeout-probe")
    assert real.timeout <= 5, "a JWKS fetch must not hold a thread for PyJWT's default 30s"
