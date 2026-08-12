"""Redis fixed-window rate limits (spec §3): 60 chat req/min and 20
uploads/hour per tenant.

Disabled when redis_url is unset (unit tests); the limiter is fail-open on
Redis outage — losing rate limiting must not take chat down with it.
"""

from uuid import UUID

import redis.asyncio as aioredis

from app.config import get_settings
from app.errors import ApiError


class RateLimiter:
    def __init__(self) -> None:
        self._redis: aioredis.Redis | None = None

    def _conn(self) -> aioredis.Redis | None:
        url = get_settings().redis_url
        if not url:
            return None
        if self._redis is None:
            self._redis = aioredis.from_url(url)
        return self._redis

    async def close(self) -> None:
        if self._redis is not None:
            await self._redis.aclose()
            self._redis = None

    async def _check(self, key: str, limit: int, window_s: int, message: str) -> None:
        conn = self._conn()
        if conn is None:
            return
        try:
            count = await conn.incr(key)
            if count == 1:
                await conn.expire(key, window_s)
        except aioredis.RedisError:
            return
        if count > limit:
            raise ApiError(429, "rate_limited", message)

    async def check_chat(self, tenant_id: UUID) -> None:
        await self._check(
            f"rl:chat:{tenant_id}",
            get_settings().chat_rate_limit_per_min,
            60,
            "Chat rate limit reached, retry in a minute",
        )

    async def check_upload(self, tenant_id: UUID) -> None:
        await self._check(
            f"rl:upload:{tenant_id}",
            get_settings().upload_rate_limit_per_hour,
            3600,
            "Upload limit reached, retry later",
        )

    async def check_register_lookup(self, tenant_id: UUID) -> None:
        """Public-register lookups, which spend a platform-wide allowance.

        Unlike chat and uploads, the resource being protected is not ours:
        Companies House allows 600 requests per five minutes per application
        and suspends applications that habitually exceed it. One workspace in a
        loop would take the registers down for every other workspace, so this
        is the one limit whose job is to protect other tenants.
        """
        await self._check(
            f"rl:register:{tenant_id}",
            get_settings().register_lookup_rate_limit_per_hour,
            3600,
            "Too many register lookups — try again later",
        )


rate_limiter = RateLimiter()
