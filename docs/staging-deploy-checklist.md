# Staging deploy checklist (W4 pilot prep)

Target: Hetzner + Coolify per spec §12. Postgres 16 + pgvector, Redis,
LiteLLM proxy (own Postgres), API, worker, web. Cloudflare R2 replaces dev
MinIO. Work through in order; every step is verifiable before the next.

Deploy artifacts (all in-repo): `infra/docker-compose.staging.yml` (the stack
Coolify runs), `infra/.env.staging.example` (env matrix template — the filled
copy lives gitignored at `infra/.env.staging`), `infra/staging-roles.sql`
(one-time role bootstrap). Images: API + worker are CI-built on GHCR
(`.github/workflows/app-images.yml` / `worker-image.yml`); web is built by
Coolify from `apps/web/Dockerfile` because `NEXT_PUBLIC_*` values bake into
the bundle at build time.

## 1. Cloudflare R2 (bucket exists — wire it up)

1. Create an **API token scoped to the bucket** (R2 → Manage API Tokens →
   Object Read & Write, this bucket only). Record: Access Key ID, Secret
   Access Key, and the account endpoint
   `https://<account_id>.r2.cloudflarestorage.com`.
2. **Bucket CORS** — browser uploads PUT directly against presigned URLs, so
   the bucket must allow the staging web origin (downloads open as
   navigations and need nothing):

   ```json
   [
     {
       "AllowedOrigins": ["https://<staging-web-domain>"],
       "AllowedMethods": ["PUT"],
       "AllowedHeaders": ["Content-Type"],
       "MaxAgeSeconds": 3600
     }
   ]
   ```
3. The storage clients already use path-style + SigV4 (`region=auto`) — no
   code changes. Smoke-test from a laptop before deploying (put/get/delete a
   test object with the token via the API's `Storage` client or `aws s3api`).

## 2. Secrets to generate once

- `LITELLM_KEY_ENCRYPTION_KEY` — **must be identical on API and worker**:
  `python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'`
  (API refuses boot without it when the gateway is configured.)
- `LITELLM_MASTER_KEY` — proxy admin key (matches the LiteLLM container env).
- Strong passwords for the `ops` (owner) and `ops_app` (runtime) DB roles —
  `ops_app` is created by migration 0001 in dev/CI; **create it manually in
  staging** with RLS-enforced (non-owner, no BYPASSRLS).

## 3. Environment matrix

| Var | API | Worker | Web | Staging value |
| --- | :-: | :-: | :-: | --- |
| `DATABASE_URL` | ✓ | | | owner role, migrations only |
| `APP_DATABASE_URL` | ✓ | ✓ | | `ops_app` runtime role |
| `REDIS_URL` | ✓ | ✓ | | |
| `SUPABASE_JWKS_URL` | ✓ | | | real project JWKS (leave `SUPABASE_JWT_SECRET` unset) |
| `CORS_ORIGINS` | ✓ | | | staging web origin — validator rejects `*` |
| `LITELLM_BASE_URL` / `LITELLM_MASTER_KEY` | ✓ | ✓ (base URL only) | | |
| `LITELLM_KEY_ENCRYPTION_KEY` | ✓ | ✓ | | same Fernet key both sides |
| `STORAGE_ENDPOINT` | ✓ | ✓ | | `https://<account_id>.r2.cloudflarestorage.com` |
| `STORAGE_BUCKET` / `_ACCESS_KEY` / `_SECRET_KEY` | ✓ | ✓ | | R2 token creds; `STORAGE_REGION=auto` |
| `SENTRY_DSN` / `ENVIRONMENT` | ✓ | ✓ | | `staging` |
| `NEXT_PUBLIC_SUPABASE_URL` / `_ANON_KEY` | | | ✓ | |
| `NEXT_PUBLIC_API_URL` | | | ✓ | staging API origin |
| `NEXT_PUBLIC_STORAGE_ORIGIN` | | | ✓ | the R2 endpoint origin — presigned-URL open allowlist |

## 4. Order of operations

1. Postgres up → `infra/staging-roles.sql` (pre-creates `ops_app` with the
   strong password; migration 0001's `if not exists` then only applies
   grants) → `alembic upgrade head` (as owner) →
   `python -m app.groundwork.seeds` (reference data, idempotent). Both
   commands run from the API image:
   `docker compose -f infra/docker-compose.staging.yml run --rm api <cmd>`.
2. LiteLLM proxy up with `infra/litellm-config` aliases + provider keys;
   verify `/health` and one completion per alias.
3. API up → `/api/v1/health` → sign up a staging tenant (email confirm) —
   bootstrap must mint an encrypted virtual key (check `tenants` row).
4. Worker up — the CI-built GHCR image (verified 31 Jul in dev: job_timeout
   3600, WeasyPrint + pango, health-card function; container health-card
   proof green). Never build images on the dev machine — pull from GHCR.
5. Web up → full smoke: upload a PDF → `ready`; cited chat answer; monthly
   report draft (expect ~10–30 min); health card (~seconds, opens PDF).
6. Point Sentry at both API + worker and confirm an event arrives.

## 5. Pilot onboarding (after smoke)

- Set `features.projects = true` on the pilot tenant (ops action, SQL).
- Set the tenant `brand` accent (jsonb) — the health card header uses it.
- Enter 1–2 real projects with the consultant (target ≤ 90 min each),
  then generate the first real monthly report together (PRD §9 exit).
