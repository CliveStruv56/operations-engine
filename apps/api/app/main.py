from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import sentry_sdk
from fastapi import FastAPI

from app.config import get_settings
from app.db import db
from app.errors import register_error_handlers
from app.routers import invites, members, tenants


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    await db.connect()
    yield
    await db.close()


def create_app() -> FastAPI:
    settings = get_settings()
    if settings.sentry_dsn:
        # No client content in logs/errors (spec §9.5): ids and counts only.
        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            environment=settings.environment,
            send_default_pii=False,
        )
    app = FastAPI(title="Operations Engine API", version="0.1.0", lifespan=lifespan)
    register_error_handlers(app)

    @app.get("/health", tags=["health"])
    @app.get("/api/v1/health", tags=["health"])
    async def health() -> dict:
        return {"status": "ok"}

    for router in (tenants.router, members.router, invites.router):
        app.include_router(router, prefix="/api/v1")
    return app


app = create_app()
