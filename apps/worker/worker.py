"""arq worker scaffold.

Slice 3 adds the real jobs: parse_document (Docling → heading-aware chunks)
and embed_chunks (batches of 64 via the LiteLLM `embedder` alias).
Run: arq worker.WorkerSettings
"""

import os

from arq.connections import RedisSettings


async def ping(ctx: dict) -> str:
    return "pong"


class WorkerSettings:
    functions = [ping]
    redis_settings = RedisSettings.from_dsn(
        os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    )
