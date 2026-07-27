# Operations Engine

White-label, multi-tenant AI operations SaaS for UK SMBs (3–50 seats). One branded
workspace per client: chat workspace, cited knowledge vault (RAG), cost-routed
open-weight models via cloud APIs only.

Authoritative specification: [docs/phase-1-build-spec.md](docs/phase-1-build-spec.md).

## Layout

| Path | What |
| --- | --- |
| `apps/web` | Next.js frontend (tenant-themed workspace) |
| `apps/api` | FastAPI backend — `/api/v1`, JWT auth, tenant RLS context |
| `apps/worker` | arq worker — document parsing (Docling) + embedding |
| `infra` | Docker Compose, LiteLLM config, deploy notes |
| `packages/shared` | OpenAPI-generated TypeScript client |
| `docs` | Product spec and plans |

## Hard constraints

1. MIT/Apache-licensed components only.
2. Tenant isolation enforced by Postgres row-level security, not app code alone.
   A migration is not done until its table has RLS **and** an isolation test.
3. All model access through the LiteLLM gateway — no provider SDKs in app code.
4. Western zero-data-retention hosts by default. Cloud APIs only.
5. Cost telemetry on every LLM call.

## Local development

```sh
# infra: Postgres (pgvector) + Redis
docker compose -f infra/docker-compose.dev.yml up -d

# api
cd apps/api
uv sync
cp .env.example .env
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --port 8000

# web
cd apps/web
pnpm install
pnpm dev
```

Tests (includes the CI-blocking cross-tenant isolation suite):

```sh
cd apps/api && uv run pytest
```
