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
os.environ["STORAGE_ENDPOINT"] = ""

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
    return Tenant(
        id=tenant_id,
        owner_id=owner_id,
        membership_id=membership_id,
        project_id=project_id,
        document_id=document_id,
        conversation_id=conversation_id,
        invite_id=UUID(invite["id"]),
        invite_token=invite["token"],
    )


@pytest.fixture
async def two_tenants(client) -> tuple[Tenant, Tenant]:
    a = await seed_tenant(client, f"alpha-{uuid4().hex[:6]}")
    b = await seed_tenant(client, f"beta-{uuid4().hex[:6]}")
    return a, b
