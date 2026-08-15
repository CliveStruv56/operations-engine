# Staging deploy checklist (W4 pilot prep)

> **Deployed 31 Jul 2026 — divergence from spec §12**: staging runs on
> **Railway** (backend: project `ops-engine-staging` — postgres/pgvector,
> redis, litellm + own postgres, api, worker; `railway up` per app dir,
> volumes on both postgres + worker cache, api domain
> https://api-production-71150.up.railway.app) and **Vercel** (web: project
> `ops-engine-staging-web`, https://ops-engine-staging-web.vercel.app,
> NEXT_PUBLIC_* set in Vercel env, no Docker build). Chosen over
> Hetzner+Coolify because the user already had Railway/Vercel accounts and
> Railway supplies domains — no server ops for the pilot. The compose file
> below stays for a later self-hosted move. Railway gotchas: PGDATA must
> point at a subdir of the volume mount (lost+found breaks initdb); do NOT
> set LC_ALL=C (SQL_ASCII cluster breaks psycopg3 — returns bytes);
> apps must bind `::` (IPv6 private mesh) and the Dockerfile needs EXPOSE
> for edge port detection; LiteLLM config is baked via infra/litellm/Dockerfile
> (Railway can't mount files).
>
> **Deploying api/worker to Railway** (verified 3 Aug 2026). Both services are
> source-deployed — no linked repo, no source image — so a deploy is a CLI
> upload that Railway builds from the app's own Dockerfile:
>
> ```sh
> railway up ./apps/api     --path-as-root --service api     --environment production
> railway up ./apps/worker  --path-as-root --service worker  --environment production
> railway up ./infra/litellm --path-as-root --service litellm --environment production
> ```
>
> **The gateway is a deploy too** (added 4 Aug 2026). `infra/litellm/config.yaml`
> is *baked into the image* via `infra/litellm/Dockerfile` because Railway
> cannot mount files — so editing an alias in that file changes nothing until
> the `litellm` service is deployed. Nothing warns you; the old aliases keep
> serving. Verify with
> `railway ssh --service litellm "cat /app/config.yaml"` rather than assuming
> the build shipped what you edited.
>
> `--path-as-root` is not optional. `railway up` archives from the **linked
> project root**, not the working directory, so running it from inside
> `apps/api` uploads the whole monorepo and Railpack fails with "could not
> determine how to build the app". A failed build leaves the running
> deployment untouched, so this is safe to get wrong. Add `--detach --json`
> to get a deployment id back and poll `railway deployment list --json
> --service <svc>` instead of streaming (the log stream drops on long builds,
> and `railway logs` without an explicit id shows the last *successful*
> deployment, not the one that just failed).
>
> **Migrations run as a Railway pre-deploy hook** (set 3 Aug 2026). The api
> service has `preDeployCommand = ["alembic upgrade head"]`, so Railway runs
> migrations against the new image after build and **before** switching
> traffic. A failing migration fails the deploy and leaves the previous
> release serving.
>
> This matters because the API container's CMD is only uvicorn — there was no
> migration step at all, and nothing warns you. Migration 0012 added
> `tenants.suspended_at`, which tenant resolution selects on every request, so
> shipping that code against an unmigrated database would have 500'd every
> tenant request until someone noticed.
>
> **The hook is Railway-side state, not in this repo** — a rebuilt project
> will not have it. To re-apply, either set it in the service's Settings →
> Deploy → Pre-deploy Command, or:
>
> ```sh
> # serviceId/environmentId from `railway status --json`
> curl -s https://backboard.railway.com/graphql/v2 \
>   -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
>   -d '{"query":"mutation{serviceInstanceUpdate(serviceId:\"<svc>\",environmentId:\"<env>\",input:{preDeployCommand:[\"alembic upgrade head\"]})}"}'
> ```
>
> The database is on `postgres.railway.internal`, so it is unreachable from a
> laptop: `railway run` injects the env vars but still executes locally and
> cannot resolve the private host. For one-off SQL or to check state, use
> `railway ssh --service api "alembic current"`, which runs inside the
> deployed container — note that container only carries the migrations that
> shipped in *its* image, so it cannot apply a revision newer than itself.
> That is the whole reason the hook exists rather than a manual step.
>
> **Seeding platform reference data on staging** (done 4 Aug 2026). The
> seeders need the *owner* connection and their fixtures ship inside the api
> image (`COPY app/ app/`, and `.dockerignore` does not strip json), so they
> run in the container rather than from a laptop:
>
> ```sh
> railway ssh --service api --environment production "python -m app.grants.seeds"
> railway ssh --service api --environment production "python -m app.groundwork.seeds"
> railway ssh --service api --environment production "python -m app.refdata.seeds"
> railway ssh --service api --environment production "python -m app.claims.ccni"
> ```
>
> All upsert by key, so re-running is safe. Grantwork's prints a warning that
> all 13 catalogue rows are `status='unverified'` and stale — that is by
> design (ASSUMPTIONS #24), not a failed seed. `app.claims.ccni` is different
> in kind: it **downloads** the Northern Ireland charity register export and
> replaces the snapshot whole, so it is a periodic operator refresh (monthly
> is fine), not a one-off seed — and it takes a file path or URL argument if
> CCNI's export endpoint drifts.
>
> `railway ssh` may print a one-time "Railway agent tooling not detected"
> notice instead of running; just issue the command again.
>
> **Railway does not consume the GHCR images** — it builds from the uploaded
> source. The GHCR images serve the local dev stack and the future
> self-hosted move; see the Images note below.

Original plan below — target: Hetzner + Coolify per spec §12. Postgres 16 + pgvector, Redis,
LiteLLM proxy (own Postgres), API, worker, web. Cloudflare R2 replaces dev
MinIO. Work through in order; every step is verifiable before the next.

Deploy artifacts (all in-repo): `infra/docker-compose.staging.yml` (the stack
Coolify runs), `infra/.env.staging.example` (env matrix template — the filled
copy lives gitignored at `infra/.env.staging`), `infra/staging-roles.sql`
(one-time role bootstrap). Images: API + worker are CI-built on GHCR
(`.github/workflows/app-images.yml` / `worker-image.yml`); web is built by
Coolify from `apps/web/Dockerfile` because `NEXT_PUBLIC_*` values bake into
the bundle at build time.

**Who actually consumes the GHCR images** (3 Aug 2026): the **worker** image
is pulled by `infra/docker-compose.dev.yml` — that is what runs locally, and
why the worker is never built on a dev machine. Both images are also pinned
by `infra/docker-compose.staging.yml`, which belongs to the Hetzner+Coolify
plan and is **not** what staging runs today. So the API image currently has
no consumer; it stays because it is the artefact the self-hosted move needs.
After a worker change lands, `docker compose -f infra/docker-compose.dev.yml
pull worker` is the step that picks it up locally — CI publishing it is not
enough.

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

## 2b. Observability (optional, opt-in)

**Langfuse traces.** The gateway config carries a commented
`litellm_settings` block (`infra/litellm/config.yaml`): uncomment it, set
`LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` / `LANGFUSE_HOST` on the
litellm service, and **redeploy litellm** (the config is baked into the
image). Per-tenant attribution is free — traces group by virtual-key alias
`tenant-<id>`. Message content is off by default
(`turn_off_message_logging: true`); turning it on sends tenant prompts to
wherever Langfuse runs, which is a hard-constraint-4 decision, not a tweak.
Where to run Langfuse: the EU-region Langfuse Cloud free tier is the
low-ops path; self-hosting v3 needs Postgres + ClickHouse + Redis + S3 —
a real stack, not a casual Railway add.

**Prompt canaries.** `.github/workflows/prompt-checks.yml` runs the
`infra/promptfoo/` suites (empty-output, phantom-table and invented-limit
classes) against the staging gateway, weekly and on demand. Enable by
setting two repo secrets: `STAGING_LITELLM_BASE_URL` and
`STAGING_LITELLM_KEY` (the master key, or a dedicated virtual key). Without
them the workflow skips and says so.

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
| `RESEND_API_KEY` / `EMAIL_FROM` | ✓ | ✓ | | empty = email off; sender domain must be verified in Resend first |
| `EMAIL_UNSUBSCRIBE_SECRET` | ✓ | ✓ | | same value both sides — the API verifies links the worker signs; API boot refuses Resend without it |
| `WEB_BASE_URL` | ✓ | ✓ | | staging web origin (links in email) |
| `API_BASE_URL` | | ✓ | | staging API origin (the unsubscribe link's host) |
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
   **On Railway `alembic upgrade head` is not a manual step** — it is the
   service's pre-deploy hook (see the header note), so it runs on every
   deploy. The seed script is still manual and idempotent:
   `railway ssh --service api "python -m app.groundwork.seeds"`.
2. LiteLLM proxy up with `infra/litellm-config` aliases + provider keys;
   verify `/health` and one completion per alias.
3. API up → `/api/v1/health` → sign up a staging tenant (email confirm) —
   bootstrap must mint an encrypted virtual key (check `tenants` row).
4. Worker up. On Railway this is `railway up ./apps/worker --path-as-root
   --service worker` (built from source there, not pulled from GHCR — see
   the header note). The GHCR image is what the **local dev** stack pulls;
   never build the worker image on the dev machine. Verified 31 Jul in dev:
   job_timeout 3600, WeasyPrint + pango, health-card function; container
   health-card proof green.
5. Web up → full smoke: upload a PDF → `ready`; cited chat answer; monthly
   report draft (expect ~10–30 min); health card (~seconds, opens PDF).
6. Point Sentry at both API + worker and confirm an event arrives.

## 5. Pilot onboarding (after smoke)

- Set `features.projects = true` on the pilot tenant (ops action, SQL).
- Set the tenant `brand` accent (jsonb) — the health card header uses it.
- Enter 1–2 real projects with the consultant (target ≤ 90 min each),
  then generate the first real monthly report together (PRD §9 exit).
