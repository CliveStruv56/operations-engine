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

    async def enqueue_harvest(self, tenant_id: UUID, application_id: UUID, user_id: UUID) -> None:
        """Read a just-submitted application for facts worth keeping on file.

        Fire-and-forget by design: harvesting is a by-product of work somebody
        has already finished, so it must never be able to fail the act of
        marking an application submitted. Callers catch its errors and tell
        the client whether the job queued (`harvest_queued`); the `_job_id`
        makes marking the same application submitted twice a no-op.
        """
        pool = await self._conn()
        await pool.enqueue_job(
            "harvest_claims_from_application",
            str(tenant_id),
            str(application_id),
            str(user_id),
            _job_id=f"harvest:{application_id}",
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

    async def enqueue_grant_draft(
        self, tenant_id: UUID, application_id: UUID, job_id: UUID, user_id: UUID
    ) -> None:
        pool = await self._conn()
        await pool.enqueue_job(
            "grant_draft_document",
            str(tenant_id),
            str(application_id),
            str(job_id),
            str(user_id),
            _job_id=f"grantdraft:{job_id}",
        )

    async def enqueue_impact_card(
        self, tenant_id: UUID, application_id: UUID, job_id: UUID, user_id: UUID
    ) -> None:
        pool = await self._conn()
        await pool.enqueue_job(
            "generate_impact_card",
            str(tenant_id),
            str(application_id),
            str(job_id),
            str(user_id),
            _job_id=f"impactcard:{job_id}",
        )

    async def enqueue_answer_pdf(self, tenant_id: UUID, job_id: UUID, user_id: UUID) -> None:
        """Render a chat answer to a branded PDF in the worker."""
        pool = await self._conn()
        await pool.enqueue_job(
            "render_answer_pdf",
            str(tenant_id),
            str(job_id),
            str(user_id),
            _job_id=f"answerpdf:{job_id}",
        )

    async def enqueue_workspace_export(self, tenant_id: UUID, job_id: UUID, user_id: UUID) -> None:
        """Assemble the whole-workspace archive in the worker."""
        pool = await self._conn()
        await pool.enqueue_job(
            "build_workspace_export",
            str(tenant_id),
            str(job_id),
            str(user_id),
            _job_id=f"wsexport:{job_id}",
        )

    async def enqueue_community_pdf(self, tenant_id: UUID, job_id: UUID, user_id: UUID) -> None:
        """Render the community profile to a one-page branded PDF."""
        pool = await self._conn()
        await pool.enqueue_job(
            "render_community_pdf",
            str(tenant_id),
            str(job_id),
            str(user_id),
            _job_id=f"communitypdf:{job_id}",
        )

    async def enqueue_health_card(
        self, tenant_id: UUID, project_id: UUID, job_id: UUID, user_id: UUID
    ) -> None:
        pool = await self._conn()
        await pool.enqueue_job(
            "generate_health_card",
            str(tenant_id),
            str(project_id),
            str(job_id),
            str(user_id),
            _job_id=f"healthcard:{job_id}",
        )


ingest_queue = IngestQueue()
