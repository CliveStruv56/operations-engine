"""CRM module: tenant-wide contact book behind the `contacts` feature flag.

New top-level resources (/contacts, /companies) — no collision with core
routes, so include order relative to other routers does not matter.
"""

from fastapi import APIRouter

from app.routers.crm import companies, contacts

router = APIRouter(tags=["crm"])
router.include_router(contacts.router)
router.include_router(companies.router)
