"""Ingestion queue — arq over Redis; the worker app consumes `ingest_document`.

Same disabled-mode convention as the other integrations: no redis_url means
enqueueing raises 503 (tests inject a fake; dev/prod always have Redis).
"""

from uuid import UUID

from arq import create_pool
from arq.connections import ArqRedis, RedisSettings

from app.config import get_settings
from app.errors import ApiError


class IngestQueue:
    def __init__(self) -> None:
        self._pool: ArqRedis | None = None

    async def _conn(self) -> ArqRedis:
        url = get_settings().redis_url
        if not url:
            raise ApiError(503, "queue_unavailable", "Ingestion queue is not configured")
        if self._pool is None:
            self._pool = await create_pool(RedisSettings.from_dsn(url))
        return self._pool

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.aclose()
            self._pool = None

    async def enqueue_ingest(self, tenant_id: UUID, document_id: UUID, user_id: UUID) -> None:
        pool = await self._conn()
        # _job_id dedupes: re-completing or reprocessing while a run is queued
        # replaces nothing and cannot double-run the same document.
        await pool.enqueue_job(
            "ingest_document",
            str(tenant_id),
            str(document_id),
            str(user_id),
            _job_id=f"ingest:{document_id}",
        )

    async def enqueue_draft(
        self, tenant_id: UUID, project_id: UUID, job_id: UUID, user_id: UUID
    ) -> None:
        pool = await self._conn()
        await pool.enqueue_job(
            "draft_document",
            str(tenant_id),
            str(project_id),
            str(job_id),
            str(user_id),
            _job_id=f"draft:{job_id}",
        )


ingest_queue = IngestQueue()
