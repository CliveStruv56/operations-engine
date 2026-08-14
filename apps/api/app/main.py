import logging
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
    activity,
    admin,
    claims,
    conversations,
    crm,
    documents,
    global_search,
    grants,
    groundwork,
    groundwork_drafts,
    groundwork_room,
    invites,
    members,
    project_plan,
    projects,
    question_sets,
    slides,
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


def configure_logging() -> None:
    """Make this app's own logs actually reach the container output.

    Uvicorn installs handlers for its `uvicorn*` loggers and never calls
    `basicConfig`, so the root logger keeps its WARNING default and every
    `logger.info()` in `app.*` is discarded before it reaches a handler. The
    chat latency line shipped to staging that way and emitted **nothing**,
    which is indistinguishable from "the code never ran" — the failure mode
    instrumentation must never have.

    Safe alongside uvicorn: its loggers set `propagate = False`, so this adds
    no duplicate access lines. `basicConfig` is a no-op when the root logger
    already has handlers, so a host that configures logging itself still wins.
    """
    logging.basicConfig(level=logging.INFO, format="%(levelname)s:     %(name)s %(message)s")
    logging.getLogger("app").setLevel(logging.INFO)


def create_app() -> FastAPI:
    configure_logging()
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
    app = FastAPI(title="Flowgrid API", version="0.1.0", lifespan=lifespan)
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
        admin.router,
        tenants.router,
        members.router,
        invites.router,
        projects.router,
        project_plan.router,
        groundwork.router,
        groundwork_drafts.router,  # literal /projects/drafts path before room matchers
        groundwork_room.router,
        grants.router,
        crm.router,
        question_sets.router,
        claims.router,
        conversations.router,
        slides.router,
        documents.router,
        usage.router,
        global_search.router,
        activity.router,
    ):
        app.include_router(router, prefix="/api/v1")
    return app


app = create_app()
