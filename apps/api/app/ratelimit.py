"""Redis fixed-window rate limits (spec §3): 60 chat req/min per tenant.

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

    async def check_chat(self, tenant_id: UUID) -> None:
        conn = self._conn()
        if conn is None:
            return
        key = f"rl:chat:{tenant_id}"
        try:
            count = await conn.incr(key)
            if count == 1:
                await conn.expire(key, 60)
        except aioredis.RedisError:
            return
        if count > get_settings().chat_rate_limit_per_min:
            raise ApiError(429, "rate_limited", "Chat rate limit reached, retry in a minute")


rate_limiter = RateLimiter()
