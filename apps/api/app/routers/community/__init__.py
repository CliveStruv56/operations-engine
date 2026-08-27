"""Community module: the place a tenant covers, behind the `community` flag.

New top-level resource (/community/*) — no collision with core routes, so
include order relative to other routers does not matter.
"""

from fastapi import APIRouter

from app.routers.community import assets, profile, stats

router = APIRouter(tags=["community"])
router.include_router(profile.router)
router.include_router(assets.router)
router.include_router(stats.router)
