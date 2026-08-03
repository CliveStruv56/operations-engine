"""Module registry: one declaration per feature-flagged module.

Adding a module used to mean hand-editing six unrelated places — the
`FEATURE_FLAGS` allowlist, the operator console's flag list, a copy-pasted
`require_<flag>()` gate, the activity feed's action allowlist, the isolation
suite's table list, and the RLS block in the migration. Nothing tied them
together, and the one that fails quietly is RLS: a module table that never
got its policy leaks across tenants without turning a single test red.

So the manifest below is the source of truth. `FEATURE_FLAGS`, the gate
dependencies, the feed's module namespaces and the isolation suite's RLS
coverage check all derive from it.

Declaring a module here does not create its tables — the migration still
does that (`migrations/rls.py` has the policy helper). But a table declared
here whose policy is missing fails `test_every_module_table_has_rls`, which
is the whole point of writing the list down once.
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

import asyncpg
from fastapi import Depends

from app.errors import ApiError
from app.tenant import TenantContext, get_conn, require_role


@dataclass(frozen=True)
class Module:
    """A `tenants.features` entitlement.

    `tables` are the tenant-scoped tables the module owns; every one must
    carry the `tenant_isolation` policy. `feed_prefix` is the `audit_log`
    action namespace whose rows surface in the tenant activity feed — None
    keeps them out of it, which is the CRM's current deliberate position
    (its `crm.*` rows exist for audit but are not team-broadcast).
    """

    flag: str
    label: str
    tables: tuple[str, ...] = ()
    feed_prefix: str | None = None


MODULES: tuple[Module, ...] = (
    Module(
        flag="projects",
        label="Development projects",
        tables=(
            "proj_projects",
            "proj_stages",
            "proj_tasks",
            "proj_documents",
            "proj_budget_lines",
            "proj_funding_sources",
            "proj_risks",
            "proj_conditions",
            "proj_stakeholders",
            "proj_draft_jobs",
        ),
        feed_prefix="projects",
    ),
    Module(
        flag="grants",
        label="Grant funding",
        tables=(
            "grant_funders",
            "grant_applications",
            "grant_stages",
            "grant_tasks",
            "grant_reporting_periods",
            "grant_documents",
            "grant_conditions",
            "grant_impact_measures",
            "grant_outcomes",
            "grant_draft_jobs",
        ),
        feed_prefix="grants",
    ),
    Module(
        flag="contacts",
        label="Contacts (CRM)",
        tables=("crm_companies", "crm_contacts", "crm_contact_projects"),
    ),
    # Cross-cutting enrichment rather than a module of its own: `web_search`
    # gates research mode inside the shared chat endpoint (400 `feature_disabled`,
    # not a 404 router), so it owns no tables. It belongs here because it is
    # still an entitlement the operator console has to offer.
    Module(flag="web_search", label="Web search"),
)

FEATURE_FLAGS: frozenset[str] = frozenset(m.flag for m in MODULES)

#: Every tenant-scoped table owned by a module — the RLS coverage check reads this.
MODULE_TENANT_TABLES: tuple[str, ...] = tuple(t for m in MODULES for t in m.tables)

#: LIKE patterns for the module audit namespaces the activity feed surfaces.
FEED_PATTERNS: tuple[str, ...] = tuple(f"{m.feed_prefix}.%" for m in MODULES if m.feed_prefix)


def make_feature_gate(flag: str) -> Callable[..., Awaitable[TenantContext]]:
    """Build a module gate dependency: every route 404s without the flag.

    404 rather than 403 is deliberate and matches both existing modules — a
    module the tenant has not bought should not be discoverable at all.
    """
    if flag not in FEATURE_FLAGS:
        raise ValueError(f"unknown module flag: {flag}")

    async def gate(
        ctx: TenantContext = Depends(require_role("member")),
        conn: asyncpg.Connection = Depends(get_conn),
    ) -> TenantContext:
        # $2 is cast because `jsonb ->> text` and `jsonb ->> int` both exist,
        # so an untyped parameter leaves the operator ambiguous.
        enabled = await conn.fetchval(
            "select features->>$2::text = 'true' from tenants where id = $1",
            ctx.tenant_id,
            flag,
        )
        if not enabled:
            raise ApiError(404, "not_found", "Not found")
        return ctx

    gate.__name__ = f"require_{flag}"
    return gate
