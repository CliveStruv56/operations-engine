# Project Review Report

**Project:** Operations Engine — AI Operations SaaS for UK SMBs  
**Date:** 2026-07-31  
**Review Mode:** B — Documented Project (pre-PLAID)  
**Tech Stack:** Next.js 16.2.12 / React 19.2.4 / Tailwind 4 (frontend); FastAPI / Python 3.12 / asyncpg / Pydantic v2 (API); arq / Python 3.12 (worker); Postgres 16 + pgvector / Redis / LiteLLM / Supabase Auth / Cloudflare R2 (infra)  
**Project Type:** Multi-tenant SaaS monorepo (web + API + worker + infra)

---

## Executive Summary

The Operations Engine is a thoughtfully architected, early-stage multi-tenant AI workspace. The core platform—auth, tenant isolation via Postgres RLS, streaming chat, hybrid vault retrieval, presigned uploads, and usage metering—is largely in place and backed by a strong CI-blocking isolation test suite. The recently added Groundwork module (development-project management) has a solid data spine and UI scaffolding but is roughly 55–60 % complete: W1 (schema/seeds) and most of W2 (CRUD UI) are done, while W3 (AI drafting workflows) and W4 (health-card PDF, polish, pilot onboarding) are not yet implemented. The main risks are dependency vulnerabilities in the web app, a permissive default CORS setup, several API-level race/validation gaps in the Groundwork module, and the absence of billing/Stripe and core settings/usage pages.

**Overall Health:** Needs Attention — solid foundations, but a focused hardening and completion push is required before pilot onboarding.

---

## 1. Security & Vulnerability Findings

### Critical Issues

No critical security issues found. No production secrets are committed to source control; `.env` files are correctly gitignored.

### High Priority

1. **Web dependency vulnerabilities** — `pnpm audit` reports 4 high-severity advisories via transitive `next` / `eslint` dependencies:
   - `sharp <0.35.0` — GHSA-f88m-g3jw-g9cj
   - `postcss ≤8.5.11` — GHSA-6g55-p6wh-862q
   - `postcss ≤8.5.17` — GHSA-r28c-9q8g-f849
   - `brace-expansion ≤5.0.7` — GHSA-mh99-v99m-4gvg
   **Files:** `apps/web/package.json`, `apps/web/pnpm-lock.yaml`  
   **Fix:** run `pnpm update` / upgrade `next` and `eslint-config-next`, then re-run `pnpm audit`.

2. **LiteLLM tenant virtual key stored as cleartext in the app database** — `tenants.litellm_key_id` holds the full key token (`apps/api/app/routers/tenants.py:46`). A compromised app DB exposes tenant model keys.  
   **Fix:** store only LiteLLM’s `key_id`; fetch the token at call time via the LiteLLM admin API, or seal it with a KMS/app-level encryption layer.

3. **CORS default is development-only and permissive** — `app/main.py:47-52` splits `CORS_ORIGINS` on commas and allows `allow_methods=["*"]`. If `CORS_ORIGINS=*` is accidentally set in production, any origin can call the API.  
   **Fix:** enumerate production origins explicitly; reject `*` in config validation; pin allowed methods.

4. **Cross-transaction races in document lifecycle** — `complete_upload` (`apps/api/app/routers/documents.py:85-122`) and `delete_document` (`apps/api/app/routers/documents.py:177-195`) read state in one transaction, perform I/O, then mutate in another. Concurrent requests can double-queue ingestion or double-delete.  
   **Fix:** perform the state check + mutation in a single transaction, or use advisory locks.

### Medium Priority

5. **Dynamic SQL `SET` builders** — `apps/api/app/routers/projects.py:67-72` and `apps/api/app/routers/documents.py:165-170` build SQL from Pydantic field names. Safe today, but a future schema change could introduce injection.  
   **Fix:** add an allowlist helper that validates column names.

6. **`window.open` on API-returned `download_url`** — `apps/web/app/app/projects/[id]/page.tsx:643` opens a presigned URL without origin validation. A compromised API could redirect users to an attacker site.  
   **Fix:** validate the URL host matches the configured storage origin, or proxy downloads through the API.

7. **Groundwork stage sign-off does not enforce the active stage** — `apps/api/app/routers/groundwork_room.py:247-300` allows signing off any stage, enabling stage skipping.  
   **Fix:** reject sign-off if `stage_key != project.stage_current`.

8. **Gate toggles accepted after sign-off** — `apps/api/app/routers/groundwork_room.py:211-244` does not reject toggles on already-signed-off stages.  
   **Fix:** return `409` (or `422`) when the parent stage is signed off.

9. **Worker S3 addressing style mismatch** — `apps/worker/worker/main.py:40` uses default boto3 addressing, while the API forces path-style (`apps/api/app/storage.py:43`). This can break MinIO/R2 path-style-only deployments.  
   **Fix:** set `s3={'addressing_style': 'path'}` in the worker boto3 config.

10. **Owner-removal race** — `apps/api/app/routers/members.py:41-46` counts owners without `FOR UPDATE`; concurrent deletions could leave the tenant ownerless.  
    **Fix:** acquire a row lock or use a single atomic check-and-delete.

### Low Priority

11. **Local `.env` files and `.claude/settings.local.json` contain dev secrets** — acceptable because they are untracked, but ensure they never enter CI logs.
12. **Frontend `tenantId` stored in `localStorage`** — not an auth token, but XSS could confuse UX. Consider a SameSite cookie if this becomes sensitive.
13. **CORS whitespace parsing** — `app/main.py:49` does not strip spaces after commas.
14. **JWT issuer validation not enforced** — typical for Supabase Auth but worth adding for production.

### Security Summary

| Category | Status |
|---|---|
| Secrets & Credentials | Clean (no committed secrets; dev values gitignored) |
| Dependencies | 4 high-severity transitive web advisories |
| Authentication | Solid (JWKS/HS256, audience check, bearer required) |
| Input Validation | Gaps Found (dynamic SQL builders, Groundwork stage/gate validation) |
| Data Exposure | Clean (RLS scoped, PII not logged, Sentry PII off) |
| Network Security | Gaps Found (CORS permissive; download_url not validated) |
| PWA Security | N/A |
| Mobile Security | N/A |
| Infrastructure | Gaps Found (worker S3 addressing; no dependency scanning in CI) |
| Third-Party | Clean (LiteLLM proxy used; no raw provider SDKs) |

---

## 2. Code Quality Assessment

| Category | Score | Key Finding |
|---|---|---|
| Architecture | Strong | Clean separation into routers/services; RLS pool wrapper enforces tenant context; module is additive with feature flags. |
| Type Safety | Strong | Python + Pydantic v2; Next.js strict TypeScript; web type-checks cleanly; zero `any` found in reviewed web code. |
| Error Handling | Adequate | Consistent `{error: {code, message}}` envelope; safe SSE stream errors; but frontend swallows many auxiliary-request failures. |
| State Management | Adequate | Server-driven state with `useState`/`useEffect`; no global store yet; fine for current scale but tab-heavy project room will benefit from refactoring. |
| Performance | Adequate | Streaming chat works; web build passes; but large client components are not code-split and Overview tab fires 5 parallel requests. |
| Testing | Strong | 82 API tests + 10 worker tests pass; isolation suite is CI-blocking; missing tests for some Groundwork tables and edge cases. |
| Accessibility | Needs Work | Login/signup inputs lack labels; tables lack `scope="col"`; no skip link; `window.prompt` for dormancy reason. |
| Code Hygiene | Strong | Zero TODO/FIXME and zero `console.log` in reviewed source; ruff clean; 1 minor web lint warning. |
| Developer Experience | Strong | uv/pnpm, ruff, mypy, GitHub Actions CI, clear README, `.env.example` files. |
| PWA Compliance | N/A | Not intended as a PWA. |
| Mobile Readiness | Adequate | Responsive breakpoints present; all pages are client components, so perceived load on mobile is weaker. |
| Cross-Platform | N/A | Web-only target. |

### Detailed Findings

- **Large frontend files** — `apps/web/app/app/projects/[id]/page.tsx` is 1,217 lines and bundles all 9 tabs. This harms maintainability and prevents code-splitting. Recommendation: split into `tabs/*.tsx` and use dynamic imports.
- **Frontend client components everywhere** — every route uses `"use client"`. Data fetching happens after mount, producing empty initial HTML and violating the spec’s “no layout shift” quality bar. Recommendation: move data reads into Server Components where possible and add `loading.tsx`/`error.tsx`.
- **Silent error swallowing** — `apps/web/app/app/projects/[id]/page.tsx:178-189` and `apps/web/app/app/page.tsx:50-56` use `.catch(() => {})`. Failed auxiliary requests leave UI partially blank without feedback.
- **Dynamic SQL builders** — see Security finding #5.
- **Worker HTTP/S3 clients recreated per call** — `apps/worker/worker/embed.py:25`, `apps/worker/worker/summarize.py:49`, and `apps/worker/worker/main.py:40` create new clients each time. Recommendation: cache clients on the arq context or module level.
- **Token estimate is crude** — `apps/api/app/routing.py:31-33` uses `len(text)//4`. Acceptable for routing, but document it or switch to a tokenizer near the 100K boundary.
- **Role validation `KeyError` risk** — `apps/api/app/tenant.py:69-73` assumes `ctx.role` is always valid. Add explicit validation.

---

## 3. Progress & Alignment

### Mode B — Documentation Alignment

The authoritative documents are `docs/phase-1-build-spec.md` (core Phase 1) and `docs/groundwork-module-prd.md` (module add-on), plus `docs/groundwork/ASSUMPTIONS.md` for documented divergences.

**Estimated Completion:** Core Phase 1 ≈ 70 %; Groundwork Module ≈ 55–60 %.

| Documented Feature | Status |
|---|---|
| Multi-tenant chat workspace with streaming | ✅ Built |
| Knowledge vault (RAG with citations) | ✅ Built |
| Postgres RLS tenant isolation + CI isolation suite | ✅ Built |
| LiteLLM gateway + route aliases + virtual keys | ✅ Built |
| Cost-routed model selection (`select_route`) | ✅ Built |
| Presigned R2/MinIO upload/download | ✅ Built |
| Usage metering (`/usage/summary`) | ✅ Built |
| Per-seat Stripe billing + webhooks | ❌ Not Started |
| `/app/settings` (brand, members, invites, billing portal) | ❌ Not Started |
| `/app/usage` frontend page | ❌ Not Started |
| Groundwork schema, seeds, RAG pure function | ✅ Built |
| Groundwork portfolio + project room UI | ⚠️ ~85 % (tabs present; some UX gaps) |
| Groundwork AI drafting workflows (monthly/feasibility/bid) | ❌ Not Started |
| Groundwork health-card PDF | ❌ Not Started |

**Undocumented features found in code:**

- Per-document summary chunk (`documents.summary`, `usage_events.kind='summary'`) — not explicitly mentioned in the build spec but additive and useful.

**Stale documentation:**

- `docs/phase-1-build-spec.md` still lists Stripe billing as in scope, but `docs/groundwork/ASSUMPTIONS.md` #7 records that Stripe has been re-sequenced after the Groundwork module. This is an accepted business decision, not a stale-doc bug, but it should be reflected in the core spec if it remains the plan.

---

## 4. Risk Assessment

### Top Risks

**Risk 1: Pilot value proposition is blocked until drafting/health-card are built.**  
**Impact:** Critical  
**Likelihood:** High  
**Detail:** The Groundwork module’s “magic moment” is generating a monthly client report from live project data. The UI currently has disabled placeholder buttons for “Draft with AI” and “Generate health card”. Without W3/W4, the pilot consultancy cannot experience the core value.  
**Mitigation:** Prioritize the three drafting workflows and health-card endpoint before any other module polish.

**Risk 2: Production security surface is wider than the codebase assumes.**  
**Impact:** High  
**Likelihood:** Medium  
**Detail:** CORS defaults to localhost, `allow_methods=["*"]`, and web dependencies carry 4 high-severity CVEs. If deployed to staging/production without hardening, the API is exposed to cross-origin abuse and the frontend bundle includes known-vulnerable packages.  
**Mitigation:** Patch web deps this week; add `pip-audit` and `pnpm audit` to CI; enforce origin enumeration and method pinning in production.

**Risk 3: Groundwork API correctness gaps could corrupt project state.**  
**Impact:** High  
**Likelihood:** Medium  
**Detail:** Signing off non-active stages and toggling gates after sign-off can advance a project incorrectly; `patch_project` allows applicability edits without re-seeding task/banner effects. These are not covered by the existing test suite.  
**Mitigation:** Add server-side validation and isolation tests for these edge cases before user data is entered.

**Risk 4: Document lifecycle races can produce duplicate ingestion or failed deletes.**  
**Impact:** Medium  
**Likelihood:** Medium  
**Detail:** `complete_upload` and `delete_document` perform state checks and mutations across separate transactions. Concurrent calls can pass the guard and double-queue or double-delete.  
**Mitigation:** Use a single transaction or advisory lock for state transitions.

**Risk 5: Worker S3 addressing mismatch breaks storage downloads in path-style environments.**  
**Impact:** Medium  
**Likelihood:** Medium  
**Detail:** The API forces path-style addressing for MinIO/R2 compatibility; the worker does not. Production R2/MinIO configs that require path-style will fail ingestion.  
**Mitigation:** Align worker boto3 config with the API.

**Risk 6: No dependency vulnerability scanning in CI.**  
**Impact:** Medium  
**Likelihood:** High  
**Detail:** Python projects lack `pip-audit`/`safety`; web only gets audited manually. Known CVEs will silently accumulate.  
**Mitigation:** Add `pip-audit` and `pnpm audit --audit-level high` to CI with fail-on-high thresholds.

### Launch Readiness

| Requirement | Status |
|---|---|
| Security vulnerabilities resolved | ❌ (web CVEs open) |
| Error handling complete | ⚠️ (frontend silent failures) |
| Environment config separated | ✅ |
| Monitoring in place | ⚠️ (Sentry configured but no runbook/alerting verified) |
| Analytics tracking | ❌ |
| Performance acceptable | ⚠️ (large client bundles, no code splitting) |
| Accessibility baseline | ❌ (missing labels, skip link, live regions) |
| Core user flows working | ✅ (chat + vault + Groundwork data spine) |

**Launch verdict:** Not ready — significant work needed. The platform is usable for internal dogfooding, but pilot onboarding should wait until the drafting/health-card layer is built, web CVEs are patched, and Groundwork edge-case validation is tightened.

---

## 5. Metrics Snapshot

| Metric | Value |
|---|---|
| Total source files (reviewed scope) | 72 |
| Lines of code (approx) | 10,806 |
| Dependencies (production) — API | 15 direct |
| Dependencies (production) — Worker | 7 direct (+ optional `docling[parse]`) |
| Dependencies (production) — Web | 6 direct |
| Known vulnerabilities | 4 high (web transitive), 0 critical |
| Test files | 13 API + 1 worker |
| Test results | API 82 passed; Worker 10 passed |
| TODO/FIXME count | 0 |
| `console.log` count (web) | 0 |
| TypeScript `any` count (reviewed web) | 0 |
| Largest file | `apps/web/app/app/projects/[id]/page.tsx` (1,217 lines) |
| Files over 300 lines | 9 |

---

## 6. Recommendations Summary

### Do Now (before any further development)

1. Patch the 4 high-severity web dependency vulnerabilities (`next`/`postcss`/`sharp`/`brace-expansion`).
2. Lock down production CORS: enumerate origins, reject `*`, pin allowed methods, and strip whitespace.
3. Add `pip-audit` and `pnpm audit --audit-level high` to CI.

### Do This Phase

4. Fix Groundwork stage sign-off to only allow the active stage (`apps/api/app/routers/groundwork_room.py:255-260`).
5. Reject gate toggles after sign-off (`apps/api/app/routers/groundwork_room.py:222-244`).
6. Fix `0002_projects.py` downgrade to nullify FKs or drop with cascade.
7. Fix worker S3 path-style addressing (`apps/worker/worker/main.py:40`).
8. Close document lifecycle races in `complete_upload` / `delete_document`.
9. Add isolation tests for `proj_budget_lines`, `proj_funding_sources`, `proj_conditions`, and `proj_stakeholders`.
10. Add frontend error boundaries, `error.tsx`, `loading.tsx`, and stop swallowing errors silently.

### Do Soon

11. Implement W3 drafting workflows: worker context-pack gatherer, common DOCX pipeline, `/projects/{id}/drafts` and `/projects/drafts/{job_id}` endpoints, `usage_events.kind='draft'` writes.
12. Implement W4 health-card PDF endpoint and UI flow.
13. Add `/app/settings` and `/app/usage` routes per Phase 1 spec.
14. Split `app/app/projects/[id]/page.tsx` into tab components with dynamic imports.
15. Cache worker boto3 and httpx clients; centralize vector serialization and cost constants.

### Do When Convenient

16. Replace `window.prompt` for dormancy reason with an accessible dialog.
17. Add CSP headers and `rel="noopener noreferrer"` guidance for external links.
18. Improve login/signup accessibility with explicit `<label>` elements.
19. Add `aria-live` regions for global errors and `scope="col"` to tables.
20. Consider storing only LiteLLM `key_id` instead of the full virtual key.

---

*This review was generated by the project-review skill. Previous reviews are preserved with date suffixes.*
