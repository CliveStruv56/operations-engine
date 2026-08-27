import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

TEST_DB = "ops_engine_test"
PG_HOST = os.environ.get("TEST_PG_HOST", "localhost")
PG_PORT = os.environ.get("TEST_PG_PORT", "5432")
OWNER_URL = f"postgresql://ops:ops@{PG_HOST}:{PG_PORT}/{TEST_DB}"
APP_URL = f"postgresql://ops_app:ops_app@{PG_HOST}:{PG_PORT}/{TEST_DB}"
JWT_SECRET = "test-secret-not-for-production-0123456789"

# Must be set before any app module import: Settings is lru_cached and reads
# env at first access. Explicit assignment (not setdefault) so a local .env
# can never leak the dev database into the test run.
os.environ["DATABASE_URL"] = OWNER_URL
os.environ["APP_DATABASE_URL"] = APP_URL
os.environ["SUPABASE_JWT_SECRET"] = JWT_SECRET
os.environ["SUPABASE_JWKS_URL"] = ""
os.environ["SENTRY_DSN"] = ""
os.environ["REDIS_URL"] = ""
# Gateway/storage disabled mode: a developer .env with live endpoints must not
# turn unit tests into integration tests (tests inject fakes instead).
os.environ["LITELLM_BASE_URL"] = ""
os.environ["LITELLM_MASTER_KEY"] = ""
os.environ["LITELLM_KEY_ENCRYPTION_KEY"] = ""
os.environ["STORAGE_ENDPOINT"] = ""
# A developer .env with a live Exa key must not turn the search unit tests
# into integration tests. The register keys are blanked for the same reason,
# and with sharper teeth: a live key would make the claims tests hit Companies
# House, the Charity Commission and OSCR on every run.
os.environ["EXA_API_KEY"] = ""
os.environ["COMPANIES_HOUSE_API_KEY"] = ""
os.environ["CHARITY_COMMISSION_API_KEY"] = ""
os.environ["OSCR_API_KEY"] = ""
# Operator console: tokens minted with this email are platform admins.
os.environ["PLATFORM_ADMIN_EMAILS"] = "operator@example.com"
os.environ["OPEN_SIGNUP"] = "true"

import jwt as pyjwt  # noqa: E402
import psycopg  # noqa: E402
import pytest  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402

from app.db import db  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def test_database():
    admin_url = f"postgresql://ops:ops@{PG_HOST}:{PG_PORT}/postgres"
    with psycopg.connect(admin_url, autocommit=True) as conn:
        conn.execute(f"drop database if exists {TEST_DB} (force)")
        conn.execute(f"create database {TEST_DB}")
    from alembic import command
    from alembic.config import Config

    cfg = Config(os.path.join(os.path.dirname(__file__), "..", "alembic.ini"))
    cfg.set_main_option(
        "script_location", os.path.join(os.path.dirname(__file__), "..", "migrations")
    )
    command.upgrade(cfg, "head")

    # The claim-kind catalogue is platform reference data every claims route
    # reads, so the test database needs it for the same reason production
    # does. Loading it through the real seeder rather than a fixture literal
    # means a malformed claim_kinds.json fails the suite, which is where a
    # fixture error should surface.
    import asyncio

    import asyncpg

    from app.refdata.seeds import seed_claim_kinds

    async def _seed() -> None:
        conn = await asyncpg.connect(OWNER_URL)
        try:
            await seed_claim_kinds(conn)
        finally:
            await conn.close()

    asyncio.run(_seed())
    yield


@pytest.fixture
async def client(test_database):
    await db.connect()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    await db.close()


def make_token(user_id: UUID, email: str = "user@example.com", **overrides) -> str:
    claims = {
        "sub": str(user_id),
        "email": email,
        "aud": "authenticated",
        "exp": datetime.now(UTC) + timedelta(hours=1),
        **overrides,
    }
    return pyjwt.encode(claims, JWT_SECRET, algorithm="HS256")


def auth(user_id: UUID, tenant_id: UUID | None = None) -> dict[str, str]:
    headers = {"Authorization": f"Bearer {make_token(user_id)}"}
    if tenant_id is not None:
        headers["X-Tenant-Id"] = str(tenant_id)
    return headers


@dataclass
class Tenant:
    id: UUID
    owner_id: UUID
    membership_id: UUID
    project_id: UUID
    document_id: UUID
    conversation_id: UUID
    invite_id: UUID
    invite_token: str
    company_id: UUID
    contact_id: UUID
    funder_id: UUID
    application_id: UUID
    claim_id: UUID
    plan_task_id: UUID
    community_asset_id: UUID
    community_stat_id: UUID


async def _seed_grantwork(conn, tenant_id: UUID, owner_id: UUID, project_id: UUID, name: str):
    """One row in every Grantwork tenant table, as a coherent chain.

    `test_sql_level_rls_per_table` asserts a tenant context sees *some* of its
    own rows in each listed table, so seeding is what turns the RLS check from
    "no foreign rows leaked" into a real two-sided assertion. The application
    carries `project_id` deliberately: the soft cross-module link is the one
    place a Grantwork row points at a core table, so isolation must hold
    across it too (ASSUMPTIONS #23).
    """
    funder_id = await conn.fetchval(
        """
        insert into grant_funders (tenant_id, name, kind, created_by)
        values ($1, $2, 'trust', $3) returning id
        """,
        tenant_id,
        f"{name} foundation",
        owner_id,
    )
    application_id = await conn.fetchval(
        """
        insert into grant_applications (tenant_id, funder_id, project_id, title,
                                        amount_requested, created_by)
        values ($1, $2, $3, $4, 50000, $5) returning id
        """,
        tenant_id,
        funder_id,
        project_id,
        f"{name} community fund bid",
        owner_id,
    )
    await conn.execute(
        """
        insert into grant_stages (tenant_id, application_id, stage_key, label, position)
        values ($1, $2, 'case', 'Case for support', 1)
        """,
        tenant_id,
        application_id,
    )
    await conn.execute(
        """
        insert into grant_tasks (tenant_id, application_id, stage_key, title)
        values ($1, $2, 'case', $3)
        """,
        tenant_id,
        application_id,
        f"Gather need evidence for {name}",
    )
    period_id = await conn.fetchval(
        """
        insert into grant_reporting_periods (tenant_id, application_id, label,
                                             period_start, period_end, due_date)
        values ($1, $2, 'Year 1', '2026-04-01', '2027-03-31', '2027-04-30') returning id
        """,
        tenant_id,
        application_id,
    )
    await conn.execute(
        """
        insert into grant_documents (tenant_id, application_id, doc_type_key, title,
                                     stage_key, reporting_period_id)
        values ($1, $2, 'monitoring_report', $3, 'monitor', $4)
        """,
        tenant_id,
        application_id,
        f"{name} year 1 monitoring return",
        period_id,
    )
    await conn.execute(
        """
        insert into grant_conditions (tenant_id, application_id, number, description)
        values ($1, $2, '1', $3)
        """,
        tenant_id,
        application_id,
        f"Acknowledge the funder in all {name} publicity",
    )
    measure_id = await conn.fetchval(
        """
        insert into grant_impact_measures (tenant_id, application_id, name, unit, target)
        values ($1, $2, 'Beneficiaries reached', 'people', 250) returning id
        """,
        tenant_id,
        application_id,
    )
    await conn.execute(
        """
        insert into grant_outcomes (tenant_id, measure_id, reporting_period_id, value, narrative)
        values ($1, $2, $3, 180, $4)
        """,
        tenant_id,
        measure_id,
        period_id,
        f"Confidential outcome narrative for {name}",
    )
    await conn.execute(
        """
        insert into grant_draft_jobs (tenant_id, application_id, kind, created_by)
        values ($1, $2, 'monitoring_report', $3)
        """,
        tenant_id,
        application_id,
        owner_id,
    )
    return funder_id, application_id


async def seed_tenant(client: AsyncClient, name: str) -> Tenant:
    """Bootstrap a tenant through the API, then add one row to each
    tenant-scoped content table so SQL-level isolation checks have data."""
    owner_id = uuid4()
    resp = await client.post("/api/v1/tenants", json={"name": name}, headers=auth(owner_id))
    assert resp.status_code == 201, resp.text
    tenant_id = UUID(resp.json()["id"])

    resp = await client.post(
        "/api/v1/invites",
        json={"email": f"invitee-{name}@example.com", "role": "member"},
        headers=auth(owner_id, tenant_id),
    )
    assert resp.status_code == 201, resp.text
    invite = resp.json()

    async with db.tenant_tx(owner_id, tenant_id) as conn:
        membership_id = await conn.fetchval(
            "select id from memberships where tenant_id = $1 and user_id = $2",
            tenant_id,
            owner_id,
        )
        project_id = await conn.fetchval(
            """
            insert into projects (tenant_id, name, created_by)
            values ($1, $2, $3) returning id
            """,
            tenant_id,
            f"{name} project",
            owner_id,
        )
        document_id = await conn.fetchval(
            """
            insert into documents (tenant_id, title, status, created_by)
            values ($1, $2, 'ready', $3) returning id
            """,
            tenant_id,
            f"{name} handbook",
            owner_id,
        )
        await conn.execute(
            """
            insert into doc_chunks (tenant_id, document_id, content, page_start, page_end)
            values ($1, $2, $3, 1, 1)
            """,
            tenant_id,
            document_id,
            f"Secret content for {name}",
        )
        conversation_id = await conn.fetchval(
            "insert into conversations (tenant_id, user_id, title)"
            " values ($1, $2, $3) returning id",
            tenant_id,
            owner_id,
            f"{name} chat",
        )
        await conn.execute(
            """
            insert into messages (tenant_id, conversation_id, role, content)
            values ($1, $2, 'user', $3)
            """,
            tenant_id,
            conversation_id,
            f"Hello from {name}",
        )
        await conn.execute(
            """
            insert into usage_events (tenant_id, user_id, kind, model, tokens_in, tokens_out)
            values ($1, $2, 'chat', 'workhorse', 10, 20)
            """,
            tenant_id,
            owner_id,
        )
        company_id = await conn.fetchval(
            """
            insert into crm_companies (tenant_id, name, created_by)
            values ($1, $2, $3) returning id
            """,
            tenant_id,
            f"{name} ltd",
            owner_id,
        )
        contact_id = await conn.fetchval(
            """
            insert into crm_contacts (tenant_id, company_id, name, email, created_by)
            values ($1, $2, $3, $4, $5) returning id
            """,
            tenant_id,
            company_id,
            f"{name} contact",
            f"contact-{name}@example.com",
            owner_id,
        )
        await conn.execute(
            """
            insert into crm_contact_projects (tenant_id, contact_id, project_id)
            values ($1, $2, $3)
            """,
            tenant_id,
            contact_id,
            project_id,
        )
        funder_id, application_id = await _seed_grantwork(
            conn, tenant_id, owner_id, project_id, name
        )
        # One confirmed claim and its opening revision. Both tables need a row
        # apiece or `test_sql_level_rls_per_table` can only prove that nothing
        # leaked, never that the policy lets a tenant read its own.
        claim_id = await conn.fetchval(
            """
            insert into claims (tenant_id, kind, statement, value, status, source,
                                last_verified, next_review, created_by)
            values ($1, 'registered_name', $2, $3, 'confirmed', 'typed',
                    current_date, current_date + 365, $4)
            returning id
            """,
            tenant_id,
            f"The organisation's registered name is {name} Ltd.",
            json.dumps(f"{name} Ltd"),
            owner_id,
        )
        await conn.execute(
            """
            insert into claim_revisions (tenant_id, claim_id, statement, value,
                                         source, changed_by, note)
            values ($1, $2, $3, $4, 'typed', $5, 'created')
            """,
            tenant_id,
            claim_id,
            f"The organisation's registered name is {name} Ltd.",
            json.dumps(f"{name} Ltd"),
            owner_id,
        )
        await conn.execute(
            """
            insert into community_profile (tenant_id, place_name, created_by)
            values ($1, $2, $3)
            """,
            tenant_id,
            f"{name} island",
            owner_id,
        )
        community_asset_id = await conn.fetchval(
            """
            insert into community_assets (tenant_id, category, name, attributes, created_by)
            values ($1, 'education', $2, $3, $4) returning id
            """,
            tenant_id,
            f"{name} community school",
            json.dumps({"pupils": 68}),
            owner_id,
        )
        community_stat_id = await conn.fetchval(
            """
            insert into community_statistics (tenant_id, label, value, unit, created_by)
            values ($1, 'Usual residents', 494, 'people', $2) returning id
            """,
            tenant_id,
            owner_id,
        )
        await conn.execute("update projects set has_plan = true where id = $1", project_id)
        plan_task_id = await conn.fetchval(
            """
            insert into project_tasks (tenant_id, project_id, title, position)
            values ($1, $2, $3, 1) returning id
            """,
            tenant_id,
            project_id,
            f"{name} first task",
        )
    return Tenant(
        id=tenant_id,
        owner_id=owner_id,
        membership_id=membership_id,
        project_id=project_id,
        document_id=document_id,
        conversation_id=conversation_id,
        invite_id=UUID(invite["id"]),
        invite_token=invite["token"],
        company_id=company_id,
        contact_id=contact_id,
        funder_id=funder_id,
        application_id=application_id,
        claim_id=claim_id,
        plan_task_id=plan_task_id,
        community_asset_id=community_asset_id,
        community_stat_id=community_stat_id,
    )


@pytest.fixture
async def two_tenants(client) -> tuple[Tenant, Tenant]:
    a = await seed_tenant(client, f"alpha-{uuid4().hex[:6]}")
    b = await seed_tenant(client, f"beta-{uuid4().hex[:6]}")
    return a, b
