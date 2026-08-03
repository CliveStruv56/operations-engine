"""Grantwork module: grant applications and impact reporting, behind the
`grants` feature flag.

Everything hangs off `/grants`, so there is no collision with core routes and
no ordering constraint against other routers (unlike Groundwork, which had to
fight the core's `/projects` — ASSUMPTIONS #2). Ordering *within* the package
still matters: `funders.py` registers the literal `/grants/funder-catalogue`
alongside `/grants/funders/{funder_id}`, and `reporting.py` registers the
literal `/grants/reporting-calendar`, so both go in before the routers whose
paths could shadow them.
"""

from fastapi import APIRouter

from app.routers.grants import (
    applications,
    conditions,
    documents,
    funders,
    impact,
    reporting,
    stages,
    tasks,
)

router = APIRouter(tags=["grants"])
for _module in (funders, reporting, applications, stages, tasks, documents, conditions, impact):
    router.include_router(_module.router)
