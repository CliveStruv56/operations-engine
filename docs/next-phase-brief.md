# Next Phase Brief

**Project:** Operations Engine  
**Generated:** 2026-07-31  
**Based on:** Review Report 2026-07-31  
**Review Mode:** B — Documented Project

> **Status (1 Aug 2026): this brief is complete.** All FIX items landed in
> the 31 Jul hardening pass; NEXT-001–007 and 010 landed with W3/W4;
> NEXT-008 (`/app/settings` 1 Aug morning, `/app/usage` commit 0c98c89) and
> NEXT-009 (error/loading routes + surfaced failures, fd7743a) closed on
> 1 Aug. Still open from the wider Phase 1 spec: Stripe billing
> (deliberately re-sequenced). See `docs/review-context-handoff.md` for
> everything that happened after this brief, including the Hearth UI system,
> the CRM contact book (2 Aug, handoff §6d) and the operator console with
> invite-only signup (2 Aug, §6d).

---

## Context

The Operations Engine core (multi-tenant chat, RAG vault, LiteLLM gateway, RLS isolation) is built and tested. The Groundwork module’s data spine and UI are roughly 85 % complete, but the value-generating features—AI-drafted monthly reports, feasibility studies, funding bids, and the one-page health-card PDF—are not yet implemented. Meanwhile, the web app carries 4 high-severity transitive dependency vulnerabilities, CORS is permissive by default, and several Groundwork API edge cases (stage skipping, post-sign-off gate toggles) need hardening before real consultant data is entered.

**Current state:** Groundwork Module W2 complete; W3 drafting and W4 health-card/pilot not started. Core Phase 1 missing Stripe billing, settings, and usage pages (re-sequenced after module).

---

## Pre-Build Fixes

These must be resolved before starting new feature work.

### FIX-001 — Patch web dependency vulnerabilities
**Severity:** High  
**Files:** `apps/web/package.json`, `apps/web/pnpm-lock.yaml`  
**Problem:** `pnpm audit` reports 4 high-severity CVEs via `next`/`eslint` transitive deps (`sharp`, `postcss`, `brace-expansion`).  
**Action:**
1. `cd apps/web`
2. `pnpm update next eslint-config-next`
3. If advisories remain, `pnpm update sharp postcss brace-expansion`
4. Run `pnpm audit` until no high/critical findings remain.
5. Run `pnpm lint`, `pnpm exec tsc --noEmit`, and `pnpm build` to confirm.
**Verification:** `pnpm audit` exits clean; CI web job passes.

### FIX-002 — Lock down production CORS
**Severity:** High  
**Files:** `apps/api/app/config.py`, `apps/api/app/main.py`  
**Problem:** `allow_methods=["*"]` and comma-split origin parsing with no validation. A production `CORS_ORIGINS=*` would allow any origin.  
**Action:**
1. In `app/config.py`, add a validator/normalizer for `cors_origins` that strips whitespace, rejects `"*"`, and returns a list.
2. In `app/main.py`, replace `allow_methods=["*"]` with `["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]`.
3. Add a test asserting that `Settings(cors_origins="*")` raises `ValidationError`.
**Verification:** API tests pass; manually `curl -H "Origin: https://evil.com"` against a prod-like config and confirm 403.

### FIX-003 — Harden Groundwork stage sign-off and gate toggles
**Severity:** High  
**Files:** `apps/api/app/routers/groundwork_room.py`  
**Problem:** `signoff_stage` can sign off non-active stages; `toggle_gate_item` accepts toggles after sign-off.  
**Action:**
1. In `signoff_stage`, after fetching the stage, verify `stage_key == project["stage_current"]`; return `422` otherwise.
2. In `toggle_gate_item`, verify the parent stage is not signed off (`gate_signed_off_at is None`); return `409` otherwise.
3. Add tests in `tests/test_groundwork_room.py` covering both rejections.
**Verification:** New tests pass; existing 20 Groundwork tests still pass.

### FIX-004 — Fix worker S3 path-style addressing
**Severity:** Medium  
**Files:** `apps/worker/worker/main.py`  
**Problem:** Worker uses default boto3 addressing; API forces path-style for MinIO/R2 compatibility.  
**Action:**
1. Import `botocore.config.Config`.
2. In `_download`, build the S3 client with `config=Config(signature_version="s3v4", s3={"addressing_style": "path"})`.
3. Match the API’s endpoint/region handling.
**Verification:** Worker integration test with MinIO still passes; run `cd apps/worker && uv run pytest`.

### FIX-005 — Close document lifecycle races
**Severity:** Medium  
**Files:** `apps/api/app/routers/documents.py`  
**Problem:** `complete_upload` and `delete_document` read state and mutate across separate transactions.  
**Action:**
1. Refactor both endpoints so the state read + guard + mutation happen inside the single tenant transaction already injected via `get_conn`.
2. Use `SELECT ... FOR UPDATE` on the document row during the state transition.
**Verification:** Existing document tests pass; add a concurrency test with `asyncio.gather` if feasible.

---

## Task List

### NEXT-001 — Add dependency scanning to CI
**Files:** `.github/workflows/ci.yml`  
**Context:** Currently no automated dependency vulnerability scanning; CVEs accumulate silently.  
**Action:**
1. Add a step in the API job: `uv tool run pip-audit --desc --format=json .` (or install `pip-audit` in the dev group).
2. Add a step in the Worker job: same.
3. Add a step in the Web job: `pnpm audit --audit-level high`.
4. Make each step fail the job on high/critical findings.
**Acceptance:** CI fails if any high-severity advisory is introduced.

### NEXT-002 — Implement worker drafting context-pack gatherer
**Files:** `apps/worker/worker/groundwork_drafts.py` (new), `apps/worker/worker/main.py`  
**Context:** Common first step for all three Groundwork drafts.  
**Action:**
1. Create a module that, given `tenant_id` + `project_id` + `kind`, opens a tenant-scoped transaction and selects: project + stages + tasks + budget totals + funding stack + risks + conditions + stakeholders.
2. For `feasibility_study` and `funding_bid`, run the existing core vault retrieval with fixed query sets and collect chunks with ids.
3. Return a typed `ContextPack` Pydantic model.
**Acceptance:** Unit test creates a project and verifies the context pack contains expected record counts and no cross-tenant leakage.

### NEXT-003 — Implement common DOCX drafting pipeline
**Files:** `apps/worker/worker/groundwork_drafts.py`, `apps/worker/pyproject.toml`  
**Context:** PRD §5 requires a reusable 5-step pipeline: gather → outline → section calls → DOCX assembly → register.  
**Action:**
1. Add `python-docx` (MIT) to `apps/worker/pyproject.toml`.
2. Implement `outline_document(kind, context, instructions)` using the `drafter` alias (low temperature).
3. Implement `draft_sections(kind, outline, context)` using `drafter`/`reasoner` per section; enforce the `[TO CONFIRM: ...]` convention in prompts.
4. Implement `assemble_docx(...)` with title page, headings, real data tables, citation footnotes mapped from `[c:<chunk_id>]`, and a Data Sources appendix.
5. Implement `register_draft(...)` to upload DOCX to R2 under `tenants/{tenant_id}/projects/{project_id}/drafts/...`, update `proj_documents.versions`, set status `drafting`, write `usage_events` per LLM call, and audit-log.
6. Enforce the 15-call / 24k-token guard with friendly failure.
**Acceptance:** Generate a monthly report DOCX from the demo project; spot-check 10 figures → 10/10 traceable to module records; zero invented content.

### NEXT-004 — Add Groundwork draft API endpoints
**Files:** `apps/api/app/routers/groundwork_drafts.py` (new), `apps/api/app/main.py`  
**Context:** Frontend needs `POST /projects/{id}/drafts` and `GET /projects/drafts/{job_id}`.  
**Action:**
1. Create a new router under `/api/v1/projects/{id}/drafts`:
   - `POST /projects/{id}/drafts` — validate `kind` and params, enqueue an arq job, return `{job_id}`.
   - `GET /projects/drafts/{job_id}` — poll job status; on complete return document id + presigned download URL.
2. Include the router in `app/main.py`.
3. Add isolation tests: tenant A cannot see tenant B’s job or document.
**Acceptance:** End-to-end test submits a draft, polls to completion, and downloads a DOCX.

### NEXT-005 — Wire Draft with AI modal in project room
**Files:** `apps/web/app/app/projects/[id]/page.tsx`, `apps/web/lib/groundwork.ts`  
**Context:** Three `ai_draftable` registry rows currently show disabled buttons.  
**Action:**
1. Add a `DraftModal` component supporting:
   - monthly report: month picker
   - funding bid: funding-source picker
   - feasibility study: free-text instructions
2. On submit, call `POST /projects/{id}/drafts` and poll `GET /projects/drafts/{job_id}`.
3. On complete, show success panel with download link and “N items to confirm” count.
4. Update `lib/groundwork.ts` with the new API calls.
**Acceptance:** Manual walkthrough generates a monthly report from the UI and downloads the DOCX.

### NEXT-006 — Implement health-card PDF endpoint and UI
**Files:** `apps/worker/worker/health_card.py` (new), `apps/api/app/routers/groundwork.py`, `apps/web/app/app/projects/[id]/page.tsx`, `apps/worker/pyproject.toml`  
**Context:** PRD §5.4 requires a one-page WeasyPrint PDF, no LLM.  
**Action:**
1. Add `weasyprint` (BSD-3) to worker dependencies.
2. Create a worker function that builds an HTML template with: project + client, stage bar, three RAG dots with explanations, money summary, next 3 milestones, top 3 risks, decisions needed; use tenant brand colour in header.
3. Expose `POST /projects/{id}/health-card` that enqueues the job and returns a poll id.
4. Wire the existing “Generate health card” button to call the endpoint, poll, and open the presigned PDF URL.
**Acceptance:** Generated PDF is one page, contains all six content blocks, and renders the tenant brand colour.

### NEXT-007 — Add missing Groundwork edge-case tests
**Files:** `apps/api/tests/test_groundwork.py`, `apps/api/tests/test_groundwork_room.py`  
**Context:** Isolation coverage is incomplete and sign-off edge cases are untested.  
**Action:**
1. Extend isolation tests to cover `proj_budget_lines`, `proj_funding_sources`, `proj_conditions`, and `proj_stakeholders`.
2. Add tests for: signing off non-active stage, toggling gate after sign-off, deleting tasks/funding/conditions/stakeholders, vault document cross-project link rejection, applicability mutation effects.
**Acceptance:** CI passes with new tests.

### NEXT-008 — Add `/app/settings` and `/app/usage` routes
**Files:** `apps/web/app/app/settings/page.tsx`, `apps/web/app/app/usage/page.tsx`, `apps/web/app/app/page.tsx`  
**Context:** Phase 1 spec §7 requires brand/members/invites/billing settings and a usage page.  
**Action:**
1. Create `/app/settings` with sections for brand (logo + colours → CSS variables), members, invites, and a Stripe billing portal button.
2. Create `/app/usage` with month picker, totals, per-user/model breakdown, and £ display at a configured rate.
3. Add nav links in the workspace sidebar.
**Acceptance:** Pages render; settings update tenant `brand` jsonb; usage calls `/api/v1/usage/summary`.

### NEXT-009 — Improve frontend error handling and loading UX
**Files:** `apps/web/app/app/projects/[id]/page.tsx`, `apps/web/app/app/page.tsx`, `apps/web/app/error.tsx`, `apps/web/app/loading.tsx`  
**Context:** Silent failures and empty shells degrade perceived reliability.  
**Action:**
1. Add `error.tsx` and `loading.tsx` route files.
2. Replace `.catch(() => {})` with at least `console.error`/Sentry capture and inline fallback UI.
3. Add a reusable `<ErrorBoundary>` for catastrophic errors.
**Acceptance:** Broken auxiliary requests show user-facing error state; build and type-check pass.

### NEXT-010 — Refactor project room into tab components
**Files:** `apps/web/app/app/projects/[id]/page.tsx` → `apps/web/app/app/projects/[id]/tabs/*.tsx`  
**Context:** The project room is 1,217 lines and bundles all tabs.  
**Action:**
1. Create one component file per tab (Overview, Stages, Tasks, Documents, Funding, Budget, Risks, Conditions, Stakeholders).
2. Use `next/dynamic` to lazy-load non-Overview tabs.
3. Keep shared types/hooks in `apps/web/lib/groundwork.ts`.
**Acceptance:** Build passes; no behavioural regression; bundle analysis shows tab chunks split.

---

## Architecture Notes

- **RLS is the isolation boundary.** Every new Groundwork endpoint must use `get_conn` (tenant-scoped transaction) and include an isolation test before merge.
- **LiteLLM aliases only.** Drafting must use `drafter`/`reasoner` aliases with the tenant’s virtual key; never direct provider SDKs.
- **Worker upload helper.** The worker currently only downloads from R2; NEXT-003 must add a small upload helper for generated DOCX files (recorded in `docs/groundwork/ASSUMPTIONS.md` #8).
- **Draft-first rule.** Generated documents must be registered at status `drafting`. No auto-send, auto-submit, or status advance beyond `drafting`.
- **Cost guard.** Cap each draft job at ≤ 15 LLM calls and ≤ 24k tokens per call; abort with a friendly error and no orphaned registry rows.
- **Audit + usage.** Every mutation writes `audit_log` with `projects.*` action names; every LLM call writes `usage_events` with `kind='draft'`.

---

## Testing Requirements

**Minimum testing for this phase:**
- [ ] Dependency audit steps fail CI on new high-severity CVEs.
- [ ] New Groundwork sign-off/gate tests pass.
- [ ] Context-pack gatherer unit test passes with no cross-tenant leakage.
- [ ] Monthly report DOCX spot-check: 10/10 figures traceable, zero invented content.
- [ ] Feasibility study from demo project has ≥ 5 resolvable vault citations.
- [ ] Funding bid against an `announced` programme carries the status warning block.
- [ ] Draft job respects 15-call/24k-token guard; failure path returns friendly error and no orphan rows.
- [ ] Health-card PDF is one page and contains all six content blocks.
- [ ] Isolation suite covers all 9 Groundwork tenant tables.

**Testing pattern to establish:**
- Continue using `pytest` + `pytest-asyncio` for API/worker; add worker integration tests that hit MinIO + Postgres.
- For web, add at least one happy-path component test with React Testing Library once the tab refactor lands.

---

## Dependencies & Setup

**New packages:**
```bash
# Worker
uv add --project apps/worker python-docx weasyprint

# (Optional) CI dependency scanning
uv add --project apps/api --dev pip-audit
```

**New environment variables:**
None required for this phase.

**Configuration changes:**
- Update `.github/workflows/ci.yml` to run `pip-audit` and `pnpm audit`.
- Update `apps/worker/pyproject.toml` to include `python-docx` and `weasyprint` in production dependencies.

---

## Definition of Done

This phase is complete when:
- [ ] All FIX tasks resolved and verified
- [ ] NEXT-001 through NEXT-007 completed
- [ ] NEXT-008 and NEXT-009 at minimum scaffolded and functional
- [ ] All existing tests still pass (API 82, worker 10)
- [ ] New tests added for drafting, health-card, and Groundwork edge cases pass
- [ ] `pnpm audit` and `pip-audit` exit clean
- [ ] App runs without errors
- [ ] No new security issues introduced
- [ ] A demo project can generate a monthly report DOCX and a health-card PDF end-to-end

---

## Notes for the Developer / Agent

- The pilot consultancy is committed to onboarding at exit. The magic moment for this module is: *keep the project spine current → the monthly client report assembles itself.* Prioritize the report draft over polish.
- Stripe billing and the core `/app/settings`/`/app/usage` pages are explicitly out of the Groundwork PRD’s 4-week scope but are in the Phase 1 core spec. Tackle them after NEXT-001–NEXT-007 if pilot timing allows.
- The core prerequisite caveats in `docs/groundwork/ASSUMPTIONS.md` (#7–#8) remain true: production R2 must be provisioned before pilot, and the worker needs an upload helper.
- Funding programme facts are snapshots (verified 28 Jul 2026); do not treat them as immutable truth. The catalogue already surfaces `stale` badges when `next_review < today`.

---

*This brief was generated from a project review. See `docs/review-report.md` for the full assessment.*
