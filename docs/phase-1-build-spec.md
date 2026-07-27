# Phase 1 Build Specification — Product Core

Area: AI Operations Engine (https://www.notion.so/AI-Operations-Engine-3a976ad66d8c80db8d67c5055ff35951?pvs=21)
Doc Type: Specifications
Last Reviewed: 25 July 2026
Project: AI Operations Engine (https://www.notion.so/AI-Operations-Engine-3a376ad66d8c801988bee7e1179d55bf?pvs=21)
Source Link: https://hyperagent.com/thread/cmrz503wa1jjl07ad10jagfz1
Status: Verified

> Handoff-ready specification for the Phase 1 build (product core, roadmap weeks 3–8). Audience: freelance full-stack developer(s). Exit condition: one real tenant (the founder's company) using it daily. Derived from the Consolidated Recommendations; all prices/models verified July 2026.
> 

# 1. Scope & Hard Constraints

**Phase 1 delivers:** multi-tenant chat workspace · per-tenant knowledge vault (RAG with page-level citations) · cost-routed open-weight model gateway · per-seat Stripe billing · tenant theming groundwork · usage metering.

**Non-negotiables:**

1. MIT/Apache-licensed components only (no Open WebUI, Dify, n8n — licences prohibit our use case; check any new dependency).
2. Tenant isolation enforced by Postgres row-level security, not app code alone.
3. All model access through the LiteLLM gateway — no direct provider SDKs in app code.
4. Default routing on Western zero-data-retention hosts; Chinese home APIs exist as a per-tenant flag but are NOT wired in Phase 1.
5. Cloud APIs only. 6. Cost telemetry on every LLM call.

# 2. Architecture & Stack (Pinned)

Browser → Next.js (tenant-themed) → FastAPI /api/v1 (JWT → tenant middleware → RLS context) → LiteLLM proxy (virtual key per tenant → route → fallback) → DeepInfra / Groq / OpenRouter. Postgres (Supabase) for data + pgvector; R2 for files; Redis for queue; Docling worker for parsing.

- Frontend: Next.js 15+ / React 19 / Tailwind / assistant-ui (MIT)
- API: FastAPI, Python 3.12, asyncpg, Pydantic v2
- DB: Supabase Postgres 16, extensions pgvector ≥0.7 + pg_trgm, region eu-west-2 (London)
- Auth: Supabase Auth; JWTs validated in FastAPI via JWKS
- Storage: Cloudflare R2 (presigned uploads, versioning ON) · Queue: Redis (Upstash or container)
- Parsing: Docling in a worker container (arq/rq) · Billing: Stripe (per-seat quantity) + Stripe Tax
- Email: Resend · Errors: Sentry · Hosting: Hetzner + Coolify, Docker Compose
- Monorepo: /apps/web · /apps/api · /apps/worker · /infra · /packages/shared (OpenAPI-generated TS client). CI: GitHub Actions; migrations: Alembic (reversible).

# 3. Data Model & RLS

Tables (all tenant-scoped ones carry tenant_id uuid + RLS): tenants (plan, seats, brand jsonb, features jsonb, model_mode, soft_budget_usd, stripe ids, litellm_key_id) · memberships (user_id, tenant_id, role owner/admin/member) · documents (title, storage_key, mime, status uploaded→parsing→embedding→ready/failed) · doc_chunks (content, heading_path, page_start/end, token_count, embedding vector(2048), tsv generated tsvector; HNSW + GIN indexes) · conversations · messages (role, content, citations jsonb, model, tokens_in/out, cost_usd) · usage_events (kind chat/embed/parse, model, tokens, cost) · invites · audit_log.

**RLS pattern on every tenant table:**

```sql
alter table documents enable row level security;
create policy tenant_isolation on documents
  using (tenant_id = current_setting('app.current_tenant', true)::uuid);
```

The API sets tenant per transaction: `select set_config('app.current_tenant', $tenant_id, true);` — implemented as a pool wrapper so no handler can get a connection without tenant context. **A migration is not done until its table has RLS + a test proving isolation.**

Tenant resolution: X-Tenant-Id header (must match a membership) → sole membership fallback → 400 with membership list. Roles enforced via require_role() dependency. Rate limits (Redis): 60 chat req/min, 20 uploads/hour per tenant.

# 4. LiteLLM Gateway & Routing

LiteLLM proxy in its own container + small dedicated Postgres (virtual keys + spend). Internal network only. App code references **aliases**:

| Alias | Purpose | Primary (verified Jul 2026) | Fallback |
| --- | --- | --- | --- |
| workhorse | chat, admin, RAG answers | GLM 4.7-Flash @ DeepInfra ($0.06/$0.40) | drafter |
| drafter | reports, multi-step drafting | GPT-OSS-120B @ Groq ($0.15/$0.60) | workhorse |
| reasoner | financial/complex analysis | GLM 5.2 @ DeepInfra ($0.93/$3.00) | longdoc |
| longdoc | >150K-token documents | DeepSeek V4 Flash via OpenRouter, US pinned, data_collection=deny | reasoner |
| embedder | vault embeddings | Qwen3-Embedding-4B @ DeepInfra ($0.01/M, 2048 dims) | — |

```yaml
model_list:
  - model_name: workhorse
    litellm_params: { model: deepinfra/zai-org/GLM-4.7-Flash, api_key: os.environ/DEEPINFRA_API_KEY }  # verify slug
  - model_name: drafter
    litellm_params: { model: groq/openai/gpt-oss-120b, api_key: os.environ/GROQ_API_KEY }              # verify slug
  - model_name: reasoner
    litellm_params: { model: deepinfra/zai-org/GLM-5.2, api_key: os.environ/DEEPINFRA_API_KEY }        # verify slug
  - model_name: longdoc
    litellm_params:
      model: openrouter/deepseek/deepseek-v4-flash                                                     # verify slug
      api_key: os.environ/OPENROUTER_API_KEY
      extra_body: { provider: { order: ["Together","DeepInfra"], allow_fallbacks: false, data_collection: deny } }
  - model_name: embedder
    litellm_params: { model: deepinfra/Qwen/Qwen3-Embedding-4B, api_key: os.environ/DEEPINFRA_API_KEY } # verify slug
router_settings:
  fallbacks: [{workhorse: [drafter]}, {drafter: [workhorse]}, {reasoner: [longdoc]}, {longdoc: [reasoner]}]
  num_retries: 2
  timeout: 120
general_settings:
  master_key: os.environ/LITELLM_MASTER_KEY
  database_url: os.environ/LITELLM_DATABASE_URL
```

⚠️ Exact provider slugs MUST be re-verified against live catalogues at build time.

**Per-tenant virtual keys:** created on tenant creation (metadata: tenant_id; max_budget = 2× soft cap; budget_duration 30d). **Budget behaviour:** soft cap (default seats × $1.50) → pin routing to workhorse + banner; hard cap → friendly block message. Never surprise invoices. Routing is a pure function select_route(task_kind, context_tokens) with unit tests: default workhorse; analyse/report → drafter; financial → reasoner; >100K tokens → longdoc.

# 5. Knowledge Vault (RAG)

Ingestion: POST /documents → presigned R2 PUT (pdf/docx/xlsx/pptx/txt/md/csv, ≤50MB) → complete → queue → Docling parse (markdown with page anchors) → heading-aware chunks (600 tokens, 15% overlap, tables never split mid-row) → embed batches of 64 → doc_chunks. Delete cascades chunks + R2 object.

Retrieval per message: query embed → pgvector cosine top-24 + tsvector full-text top-24 (both tenant-scoped by RLS) → reciprocal-rank fusion → top 8 → chunks wrapped as data with ids → answers cite [c:chunk_id] → post-process to {document, title, page}. **Contract: vault-grounded answers carry ≥1 citation; weak retrieval → say the vault doesn't cover it (no bluffing).** ParadeDB/BM25 + reranker are Phase 2.

# 6. API Surface (/api/v1)

- Tenants/members: POST /tenants (bootstrap + LiteLLM key + 14-day trial) · GET/PATCH /tenants/me · GET /members · DELETE /members/{id} · POST /invites (seat-enforced) · POST /invites/accept
- Vault: POST /documents → {id, upload_url} · POST /documents/{id}/complete · GET /documents?status= · GET/DELETE /documents/{id} · POST /documents/{id}/reprocess · POST /vault/search (admin debug)
- Chat: POST/GET /conversations · DELETE /conversations/{id} · GET /conversations/{id}/messages · POST /conversations/{id}/messages (SSE stream; final event = persisted message with citations, model, cost)
- Billing: POST /billing/checkout-session {plan, seats} · POST /billing/portal-session · POST /webhooks/stripe (signature-verified, idempotent)
- Usage: GET /usage/summary?month= (tenant + per-user + per-model) · GET /health
- Every mutating endpoint writes audit_log. Errors: {error:{code,message}}. OpenAPI is the contract.

# 7. Frontend

/login · /signup · /invite/[token] · /app (chat: streaming, citation chips → side panel with doc/page/chunk, vault toggle, model indicator, soft-cap banner) · /app/vault (drag-drop upload, status pills, delete/reprocess) · /app/settings (brand: logo + colours → CSS variables; members/invites; billing portal) · /app/usage (month picker, totals, per-user/model, £ at configured rate). Responsive to 360px; no layout shift on stream.

# 8. Billing & Trials

Stripe: Core £29/seat, Pro £49/seat, quantity = seats; Managed manually invoiced (plan flag only). 14-day trial (no card), read-only on expiry. Seat enforcement: members + pending invites ≤ seats. Webhooks are source of truth; idempotent via stored event ids. Cancel → read-only at period end; no data deletion without explicit request. Stripe Tax (UK VAT) on.

# 9. Security Requirements

1. **CI-blocking cross-tenant isolation suite** (two seeded tenants; every read endpoint + direct-object-reference attacks; SQL-level RLS check).
2. Secrets env-only; LiteLLM + worker internal; service-role key confined to API/worker.
3. Presigned uploads validated server-side; private bucket; short-lived GET links.
4. Vault chunks delimited as data (prompt-injection baseline); no agent tools in Phase 1 (caps blast radius).
5. All default routes US ZDR; no client content in logs (ids + counts only, Sentry scrubbing on).
6. Supabase PITR + R2 versioning; restore runbook tested once. GDPR groundwork: doc delete cascades; tenant-delete stub logged.

# 10. Non-Goals (Phase 1)

Custom domains/Cloudflare for SaaS (P2) · email/calendar/Nylas (P2) · slides/images/search modules (P2) · meeting intelligence (P3) · report workflows/agents (P3) · admin console (P3) · ParadeDB + reranker (P2) · SSO · mobile · China-direct routing.

**Open decisions at kickoff (≤30 min):** verify 5 provider slugs · Redis Upstash vs container · trial policy confirmation · assistant-ui vs hand-rolled (half-day spike) · GBP display rate.

# 11. Acceptance Criteria (Definition of Done)

- Isolation suite green in CI and staging; no endpoint without valid JWT; role checks enforced; LiteLLM unreachable publicly.
- 25-page PDF → ready ≤3 min; question answerable only from it → correct doc+page citation; uncovered question → honest no-coverage answer; delete removes chunks + object.
- p50 first streamed token <2.5s on workhorse; revoke DeepInfra key → automatic Groq failover with no user-visible error; every assistant message has model/tokens/cost; /usage reconciles with LiteLLM spend within 5%.
- Soft cap → banner + workhorse pinning, chat keeps working; hard cap → friendly block. Stripe test-mode: checkout syncs plan/seats; over-seat invites blocked; cancel → read-only; webhook replay idempotent.
- Theming: logo + colours reflect for all tenant users; second tenant unaffected. Invite flow end-to-end via Resend.
- Ops: clean-clone docker compose up ≤30 min; Alembic up/down clean; deploy + rollback runbook; staging restored from backup once; /health monitored; Sentry live; "add a model" = YAML edit only (demonstrated).
- **Exit demo:** founder's company as tenant #1 — branded workspace, 50+ real documents, one week of daily use, weekly cost within the modelled $0.35–0.70/user envelope.

# 12. Milestones (6 Weeks)

| Week | Deliverable | Proof |
| --- | --- | --- |
| W1 | Repo + CI + deploy skeleton; schema + RLS + isolation tests; auth | Isolation suite green |
| W2 | LiteLLM + virtual keys; chat E2E streaming; usage capture; select_route() | Streamed chat with cost rows |
| W3 | Vault ingestion (upload → Docling → chunk → embed); status UI | 25-page PDF ready <3 min |
| W4 | Retrieval + RRF + citations; vault UI; no-coverage behaviour | Citation tests pass |
| W5 | Stripe + invites/roles + theming + usage page | Billing criteria in test mode |
| W6 | Hardening: failover, budgets, backup drill, runbooks; founder onboarding | Full acceptance list green |

**Budget note:** at UK freelance rates (£350–500/day), Phase 1 ≈ £10.5–15K; fixed infra during build ≈ £50–80/month — both consistent with the financial model.