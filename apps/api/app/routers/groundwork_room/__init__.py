"""Groundwork W2 (PRD §3): project detail, stages & gates, tasks, document
registry with versioned uploads, budget, funding + programme catalogue,
risks, conditions, stakeholders, activity.

All routes sit behind the module feature flag (require_projects) and RLS.
Route order matters: literal paths (portfolio, funding-programmes) are
registered in groundwork.py / detail.py before the {project_id} matcher is
hit, so `detail` must stay first in the include order below.
"""

from fastapi import APIRouter

from app.routers.groundwork_room import (
    activity,
    budget,
    conditions,
    detail,
    documents,
    funding,
    risks,
    stages,
    stakeholders,
    tasks,
)

router = APIRouter(tags=["groundwork"])
for _module in (
    detail,
    stages,
    tasks,
    documents,
    budget,
    funding,
    risks,
    conditions,
    stakeholders,
    activity,
):
    router.include_router(_module.router)
