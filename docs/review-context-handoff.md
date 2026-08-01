# Session Context Handoff

**Project:** Operations Engine
**Handoff date:** 2026-08-01
**Prepared by:** UI-overhaul session (supersedes the 2026-07-31 review handoff; the review itself remains in `docs/review-report.md`)
**Purpose:** Resume in a new context window without re-deriving this session's work.

---

## 1. What just happened

A full UI/UX overhaul plus two feature additions landed as nine commits,
`6ab5fbc..0a54ecc`, all green and committed on `main` (not pushed unless the
user pushed separately). Plan file: `~/.claude/plans/jiggly-imagining-snowglobe.md`.

| Commit | What |
|---|---|
| `6ab5fbc` | API foundations: migration **0007** (`memberships.email`, 3-arg `accept_invite`, `usage_events.kind` + `'search'`), `PATCH /members/{id}` role change, `is_development` on `GET /projects` |
| `c9d6ac6` | Shared `app/app/layout.tsx` + unified sidebar (dev projects nested under their heading, chats merged in with two-step delete, mobile drawer), URL-driven nav state |
| `333686a` | Activity indicators (`components/activity.tsx`: Spinner + PulsingDots, reduced-motion safe) |
| `2bd9f84` | Tenant theming live (`lib/brand.ts` derives vars from one accent hex) + `/app/settings` (name, colour, logo upload, members/invites/roles) |
| `288916b` | Composer task-mode picker; `task_kind` widened to `slides|research`; prompts moved to `apps/api/app/prompts.py` |
| `999e592` | Research mode: Exa web search (`apps/api/app/search.py`), per-tenant gate `features.web_search`, web citations with `url`/`source_type` |
| `4560a86` | Slides → native PPTX export (`apps/api/app/slides.py` + `routers/slides.py`, python-pptx), "download .pptx" button in chat |
| `0a54ecc` | Per-tenant `.pptx` template upload (Settings → Brand) + native column charts from numeric bullets |
| `17aa84d` | Evidence panel becomes overlay below `md` |

All spec divergences are recorded in `docs/groundwork/ASSUMPTIONS.md`
**items 14–16** (task modes incl. slides/research vs spec §10 non-goals,
dev-project presentation, member-email caching).

---

## 2. Architecture decisions a new session must respect

- **Workspace shell:** `apps/web/app/app/layout.tsx` mounts `WorkspaceProvider`
  (`workspace.tsx` — tenant/projects/conversations + refreshers) and
  `sidebar.tsx`. Nav state lives in the **URL**: `/app?view=vault`,
  `?project=<id>`, `?c=<conversationId>`. Don't reintroduce component-local
  nav state; `?c=` is the single source of the active conversation
  (`chat.tsx` uses `justCreatedRef` to avoid refetch-after-create).
- **Dev projects** are still ordinary `projects` rows (Groundwork 1:1
  extension); only the *presentation* is split, via `is_development` from a
  `left join proj_projects` in `routers/projects.py::_LIST_SQL`.
- **Theming:** one `brand.accent` hex (server-validated) → `lib/brand.ts`
  derives `--accent-soft`/`--accent-ink` (luminance-checked), injected as
  inline style on the layout root. Logo + slides template keys also live in
  `tenants.brand` jsonb — **no dedicated columns, no migration needed**.
- **Member emails:** app DB cannot reach Supabase `auth.users`; the JWT email
  claim is cached on `memberships.email` (written at bootstrap/accept,
  self-healed in `app/tenant.py::resolve_tenant` via a tenant-tx — the
  memberships UPDATE RLS policy needs tenant context, so it can't happen in
  `user_tx`). Nullable end-to-end.
- **Task modes:** `task_kind` regex `chat|analyse|report|financial|slides|research`
  (`schemas.py`); routing aliases in `routing.py`; per-task system prompts in
  `app/prompts.py` (`TASK_PROMPTS`). Mode picker is a `stamp`-styled `<select>`
  in the composer, sticky per conversation, client-side only.
- **Research/Exa:** `app/search.py` is plain httpx (search API ≠ model, so the
  LiteLLM-gateway constraint doesn't apply). Empty `EXA_API_KEY` → 503
  (disabled-service convention). Gated per tenant on `features.web_search`
  (default off — data leaves the trust boundary to Exa). Web results become
  pseudo-chunks with minted uuids so `_resolve_citations` (now in
  `conversations.py`, takes a merged vault+web pool) works unchanged;
  `Citation` gained `url` + `source_type` with back-compatible defaults.
  Each research call inserts `usage_events kind='search', model='exa'`.
- **Slides export:** synchronous by design (deterministic, sub-second — NOT on
  the draft-job queue). `parse_deck` (tolerant markdown parser) →
  `render_pptx` → `storage.upload_bytes` → presigned GET. Output key
  `{tenant_id}/slides/{message_id}.pptx` (re-export overwrites). Template
  mode builds on the tenant master's layouts/placeholders, clears its sample
  slides, silently falls back to the generated theme on unreadable files
  (API never sees template bytes at upload — presigned PUT). Chart rule:
  ≥3 bullets, ALL parse as "Label: number", not all-year-no-unit → native
  column chart (`chart_spec`).
- **Storage:** `upload_bytes`/`download_bytes` added to `app/storage.py` for
  server-generated artefacts only — user uploads stay browser→R2 presigned.
- **422 handler** (`app/errors.py`) now wraps `exc.errors()` in
  `jsonable_encoder` — custom pydantic validators used to crash the response.
- **Test hygiene:** `tests/conftest.py` zeroes `EXA_API_KEY` (like LiteLLM/
  storage) so a live dev key can't turn unit tests into integration tests.

---

## 3. Local environment state (as of handoff)

- Dev DB migrated to **0007** (`uv run alembic current` → `0007 (head)`).
- `EXA_API_KEY` is set in `apps/api/.env` and **verified with a live call**.
- `features.web_search` enabled for the **Struvers** tenant (dev DB) only.
- Dev servers were left running: API `uvicorn` on :8000, `pnpm dev` on :3000
  (logs in the session scratchpad — gone after reboot; just restart them).
- python-pptx added to `apps/api/pyproject.toml` (MIT; pulls Pillow/XlsxWriter).

---

## 4. Key files added/changed this session

| Path | What |
|---|---|
| `apps/web/app/app/layout.tsx` / `workspace.tsx` / `sidebar.tsx` | Shell, provider/context, unified sidebar |
| `apps/web/app/app/page.tsx` | Slim chat/vault switcher (URL params) |
| `apps/web/app/app/chat.tsx` | No inner sidebar; mode picker; web citations; pptx button |
| `apps/web/app/app/settings/page.tsx` + `settings/members.tsx` | Admin settings |
| `apps/web/lib/brand.ts`, `apps/web/components/activity.tsx` | Brand vars, spinners |
| `apps/api/migrations/versions/0007_member_email_search_usage.py` | The one migration |
| `apps/api/app/prompts.py`, `app/search.py`, `app/slides.py` | Prompts, Exa, PPTX |
| `apps/api/app/routers/slides.py` | Export endpoint (registered in `main.py`) |
| `apps/api/app/routers/tenants.py` | Logo + slides-template presign, `logo_url` |
| `apps/api/app/routers/members.py` | Role-change endpoint |
| `tests/test_slides.py`, `test_search.py` (+ additions across suites) | New coverage |

---

## 5. Verification

```sh
cd apps/api    && uv run pytest -q && uv run ruff check . && uv run ruff format --check . && uv run mypy app
cd apps/worker && uv run pytest -q && uv run ruff check . && uv run ruff format --check .
cd apps/web    && pnpm lint && pnpm typecheck && pnpm build
```

Expected at handoff: **API 139 passed**, worker 31 passed, web clean.

---

## 6. Open items / what a new session should pick up

1. **Manual visual QA is outstanding** — automated checks all pass, but no
   logged-in browser pass happened (session only reached `/login`; needs the
   user's Supabase credentials). Checklist: onboarding gate, dev-project rows
   scope chat/vault + ↗ opens room, recent chat clicked from a Groundwork
   page opens in `/app`, delete active/inactive chat, 360 px drawer +
   evidence overlay, reduce-motion, settings (colour retint, logo, invite/
   role-change/remove, last-owner block), slides outline → pptx download
   (generated theme, then with an uploaded template; numeric bullets →
   chart), research query → web-cited answer (flag-off tenant → 400).
2. **Staging rollout needs:** run migration 0007, set `EXA_API_KEY` in the
   Railway env, flip `features.web_search` for the pilot tenant, verify R2
   (not MinIO) presign flows for logo/template/slides.
3. **Spec DoD still open:** Stripe billing (deliberately deferred); theming
   DoD "second tenant unaffected" check ideally verified with two real
   tenants. ~~`/app/usage` page~~ — built 1 Aug (commit 0c98c89: month
   picker, totals, per-model/member tables, £ at `NEXT_PUBLIC_GBP_PER_USD`).
   NEXT-009 error handling also landed 1 Aug (commit fd7743a: `app/error.tsx`
   + `app/loading.tsx`, `useGwLoad`/`LoadError` retry banners in all project
   room tabs, workspace/vault loaders surface failures).
4. **Deferred by decision:** image-creation mode (no image model behind the
   LiteLLM gateway).
5. **Follow-up ideas (not commitments):** invite-email delivery (Resend),
   surface `slide_count`/filename in the pptx button toast, multi-series
   charts, per-tenant template preview in Settings.

## 6b. Hearth UI overhaul (1 Aug 2026, after this handoff was written)

Commits `636080f..f379af6`: the whole web app moved to the **Hearth** design
system (`docs/concept-01-hearth-warm-approachable.html` +
`docs/hearth-tailwind-implementation-kit.html`). Key decisions (user-chosen):
fixed terracotta chrome — tenant accent only on exports (ASSUMPTIONS #17);
whole-app sweep in one pass; new features: empty-state hero + starter
prompts, ⌘K search (`GET /api/v1/search` + command palette, 5 tests),
date-grouped chat list; inline source cards **replace** the evidence panel.
Chat pin/rename deliberately not built. Composer is now a mode-pill
radiogroup with vault switch, auto-growing textarea and a working Stop
(aborts the SSE fetch, then re-fetches messages to converge). Manual visual
QA of the Hearth screens is still outstanding (same blocker: needs a
logged-in browser session).

## 7. Read first in a new session

1. This file.
2. `docs/groundwork/ASSUMPTIONS.md` (items 14–16 are new).
3. `CLAUDE.md` (unchanged conventions: RLS, LiteLLM-only, commit-on-green).
