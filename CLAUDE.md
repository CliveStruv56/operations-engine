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
| `apps/api` | FastAPI (Python 3.12) — `/api/v1`, Supabase JWT auth, tenant RLS context, raw asyncpg SQL + Alembic, Pydantic v2 |
| `apps/worker` | arq worker — document parsing (Docling) + embedding |
| `packages/shared` | Placeholder for OpenAPI-generated TypeScript types — README only, generation not yet wired (shared web types live in `apps/web/lib/*.ts`) |
| `infra` | Docker Compose (Postgres 16 + pgvector, Redis), LiteLLM config |
| `docs` | Specs, briefs, review reports, handoff context |

Each app is independently managed — there is **no root package.json or
workspace**. `pnpm-workspace.yaml` lives in `apps/web/`.

Key api modules: `app/tenant.py` (RLS context), `app/retrieval.py` (RAG),
`app/routing.py` + `app/litellm.py` (model routing), `app/schemas.py`,
`app/groundwork/schemas.py` and `app/crm/schemas.py` (all Pydantic models —
add new ones there, not inline), `app/crm/` + `app/routers/crm/` (contact
book, chat lookup, CSV import), `app/claims/` + `app/routers/claims.py` (the
claims register — unflagged core; `registers.py` holds the only third-party
HTTP clients besides Exa), `app/routers/admin.py` (operator console —
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
| `docs/vertical-module-roadmap.md` | Which vertical module to build next, and the "module kit" that makes each one cheaper |
| `docs/modules/*.md` | Mini-PRDs for researched-but-unbuilt modules (Grantwork, Tenderhouse, Assurance) |
| `docs/drafting-engine-brief.md` | DRAFT-001/002 on the shared drafting engine — closed 4 Aug 2026 |
| `docs/funder-forms-guide.md` | How funder forms work end to end — transcribe, verify, draft, paste; Flowgrid never submits to a funder |
| `docs/claims-register-brief.md` | The core claims register — one true place for what a tenant asserts about itself. **Approved and in build from 12 Aug 2026**; §12's open questions are settled in `docs/groundwork/ASSUMPTIONS.md` #30–#35 |
| `docs/next-phase-brief.md` | Earlier work brief, closed 1 Aug 2026 |
| `docs/performance-review-aug-2026.md` | LLM latency review — read its status banner first: several findings were later disproven by measurement |
| `docs/staging-deploy-checklist.md` | How staging actually deploys (Railway + Vercel, **not** the compose file) |
| `docs/backup-and-export.md` | Workspace export (self-serve ZIP) + the operator backup checklist — supersedes the spec's stale "Supabase PITR" line |
| `docs/review-context-handoff.md` | Session-resume context |
| `docs/code-review-sep-2026.md` | Full security/health review, 2–3 Sep 2026 — read §1 for the ranked action list and §4 for the checks only the operator can run |
| `docs/review-report.md` | Earlier full project review (Aug 2026) |

## Working conventions

- UI design system: **Huddle-inspired editorial catalogue** — paper-white
  canvas, Ink Black (#151515) text, Inter, thin bone hairlines, flat and
  shadowless cards at 8px with pill (999px) buttons. Two accents only, both
  muted: Burnt Amber (#65451d) fills primary actions exclusively; Deep Violet
  (#453b60) owns links, focus, selection and every "interactive/selected"
  edge (no saturated colour anywhere — Electric Blue is retired, and
  `--color-electric-blue` now aliases the violet). The pastel Stamp tones are
  a fixed status taxonomy — sage = upcoming, lavender = in progress (`active`
  = deep-violet text on lavender), rose = shipped/complete — never decorative.
  `grounded` green stays scoped to trust states; `--ok` is the RAG status
  green. Tenant `brand.accent` colours remain **exports only** (slides,
  health-card PDFs), never app chrome — see `docs/groundwork/ASSUMPTIONS.md`
  #17. Legacy utility names alias the current palette in
  `apps/web/app/globals.css`.
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
