# Flowgrid OS — agent guide

Flowgrid OS (codename "Operations Engine" until Aug 2026) — white-label, multi-tenant AI operations SaaS for UK SMBs. One branded workspace
per client: chat workspace, cited knowledge vault (RAG), cost-routed open-weight
models via cloud APIs only. Per-tenant modules gate on `tenants.features` jsonb
(`projects`, `contacts`, `web_search`); client workspaces are created by the
platform operator via `/admin` (see `PLATFORM_ADMIN_EMAILS` / `OPEN_SIGNUP`).

## Hard constraints (non-negotiable)

1. MIT/Apache-licensed components only.
2. Tenant isolation is enforced by Postgres row-level security, not app code
   alone. A migration is not done until its table has RLS **and** an isolation
   test in `apps/api/tests/test_isolation.py`.
3. All model access goes through the LiteLLM gateway — no provider SDKs in app
   code.
4. Western zero-data-retention hosts by default. Cloud APIs only.
5. Cost telemetry on every LLM call.

## Spec precedence

`docs/phase-1-build-spec.md` is the authoritative product spec;
`docs/groundwork-module-prd.md` covers the Groundwork module. Where the repo's
conventions differ from a spec, **the repo wins** — and every divergence must be
recorded in `docs/groundwork/ASSUMPTIONS.md` (read it before Groundwork work;
it documents the projects-table extension pattern, route collisions, RLS
pattern, and vault excerpt format).

## Layout

| Path | What |
| --- | --- |
| `apps/web` | Next.js 16 / React 19 / Tailwind 4 / TS strict — tenant-themed workspace |
| `apps/api` | FastAPI (Python 3.12) — `/api/v1`, Supabase JWT auth, tenant RLS context, SQLAlchemy 2 + Alembic, Pydantic v2 |
| `apps/worker` | arq worker — document parsing (Docling) + embedding |
| `packages/shared` | OpenAPI-generated TypeScript types (`types.ts`) + drift check |
| `infra` | Docker Compose (Postgres 16 + pgvector, Redis), LiteLLM config |
| `docs` | Specs, briefs, review reports, handoff context |

Each app is independently managed — there is **no root package.json or
workspace**. `pnpm-workspace.yaml` lives in `apps/web/`.

Key api modules: `app/tenant.py` (RLS context), `app/retrieval.py` (RAG),
`app/routing.py` + `app/litellm.py` (model routing), `app/schemas.py`,
`app/groundwork/schemas.py` and `app/crm/schemas.py` (all Pydantic models —
add new ones there, not inline), `app/crm/` + `app/routers/crm/` (contact
book, chat lookup, CSV import), `app/routers/admin.py` (operator console —
`db.platform_tx()` is the ONLY sanctioned cross-tenant connection; never use
it in tenant-facing handlers).

## Commands

api and worker (run from `apps/api` / `apps/worker`):

```sh
uv run pytest            # includes CI-blocking cross-tenant isolation suite
uv run ruff check . && uv run ruff format --check .
uv run mypy app          # api only
```

web (run from `apps/web`):

```sh
pnpm lint
pnpm typecheck           # tsc --noEmit
pnpm build
```

Local infra: `docker compose -f infra/docker-compose.dev.yml up -d`
(see README for full first-run setup). CI (`.github/workflows/ci.yml`) runs all
of the above plus `pip-audit` / `pnpm audit` — a change isn't done until the
relevant app's commands pass locally.

## Docs map

| Doc | Role |
| --- | --- |
| `docs/phase-1-build-spec.md` | Authoritative core spec |
| `docs/groundwork-module-prd.md` | Groundwork module PRD (read §0 first) |
| `docs/groundwork/ASSUMPTIONS.md` | Divergence log — repo-vs-spec rulings |
| `docs/next-phase-brief.md` | Active work brief (ordered FIX-IDs) |
| `docs/review-context-handoff.md` | Session-resume context |
| `docs/review-report.md` | Last full project review |

## Working conventions

- UI design system: **Hearth** (`docs/concept-01-hearth-warm-approachable.html`
  + `docs/hearth-tailwind-implementation-kit.html`) — fixed terracotta chrome,
  Fraunces display / Plus Jakarta Sans UI, `grounded` green scoped to trust
  states. Tenant `brand.accent` colours **exports only** (slides, health-card
  PDFs), never app chrome — see `docs/groundwork/ASSUMPTIONS.md` #17. Legacy
  token names alias the Hearth palette in `apps/web/app/globals.css`.
- Tenant scoping: every new API route runs inside the tenant RLS context
  (`app/tenant.py`); never query tenant tables without it.
- Frontend API access goes through `apps/web/lib/api.ts`; shared response types
  live in `apps/web/lib/groundwork.ts` and `packages/shared` — no inline ad-hoc
  types for API payloads.
- Keep source files under ~400 lines; extract components/routers along resource
  seams rather than growing monoliths.
- Prefer small, single-phase commits; commit on green (tests + typecheck)
  before switching tasks or resetting context.
- Use subagents for codebase discovery; load only the modules relevant to the
  task when editing.
