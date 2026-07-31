from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import sentry_sdk
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.db import db
from app.errors import register_error_handlers
from app.litellm import litellm_client
from app.queue import ingest_queue
from app.ratelimit import rate_limiter
from app.routers import (
    conversations,
    documents,
    groundwork,
    groundwork_room,
    invites,
    members,
    projects,
    tenants,
    usage,
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    await db.connect()
    yield
    await litellm_client.close()
    await rate_limiter.close()
    await ingest_queue.close()
    await db.close()


def create_app() -> FastAPI:
    settings = get_settings()
    if settings.litellm_base_url and not settings.litellm_key_encryption_key:
        # Fail at boot rather than write a tenant key to the DB in cleartext.
        raise RuntimeError(
            "LITELLM_KEY_ENCRYPTION_KEY must be set when LITELLM_BASE_URL is"
            " configured — generate one with: python -c 'from cryptography.fernet"
            " import Fernet; print(Fernet.generate_key().decode())'"
        )
    if settings.sentry_dsn:
        # No client content in logs/errors (spec §9.5): ids and counts only.
        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            environment=settings.environment,
            send_default_pii=False,
        )
    app = FastAPI(title="Operations Engine API", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Tenant-Id"],
    )
    register_error_handlers(app)

    @app.get("/health", tags=["health"])
    @app.get("/api/v1/health", tags=["health"])
    async def health() -> dict:
        return {"status": "ok"}

    for router in (
        tenants.router,
        members.router,
        invites.router,
        projects.router,
        groundwork.router,
        groundwork_room.router,
        conversations.router,
        documents.router,
        usage.router,
    ):
        app.include_router(router, prefix="/api/v1")
    return app


app = create_app()
