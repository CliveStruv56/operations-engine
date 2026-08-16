# Session Context Handoff

**Project:** Flowgrid OS (codename "Operations Engine" until 2 Aug 2026)
**Handoff date:** 2026-08-16 (**§6k–§6q are the latest state**; §1–6j are
history, oldest first)
**Prepared by:** the UI-overhaul session, extended through the 1–4 Aug QA,
rename, module-kit, Grantwork and smoke-test sessions, the 12 Aug
claims-register build, the 14 Aug evaluation-gap and project-plan work, and
the 16 Aug public marketing-site build
**Purpose:** Resume in a new context window without re-deriving this work.
**Start at §7** — it names the active task and the order to read things in.

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

Follow-ups landed 1 Aug evening (user-reviewed live on :3000):
- `01b93e2` — `suppressHydrationWarning` on `<body>` (browser extensions,
  e.g. ColorZilla's `cz-shortcut-listen`, stamp attributes pre-hydration).
- `80479de` + `02f3a34` — sidebar sections separated by `edge-strong`
  hairline dividers above each label.
- `41084f6` — **context-aware chat empty state**: hero extracted to
  `apps/web/app/app/hero.tsx`; chip counts the selected project's *ready*
  docs (neutral chip + add-documents CTA when the project has none);
  suggestions derive from real document titles (`buildSuggestions`); dev
  projects lead with a live status card (stage, RAG, next milestone,
  overdue/risk counts from `GET /projects/portfolio`, silent on 404);
  project banner shows only during a conversation. Design constraint:
  chat retrieval is vault-only, so Groundwork structured facts render as
  UI, never as suggested chat prompts.

## 6c. Current state (2 Aug 2026) — superseded; see §7 for what to read first

**Product renamed to "Flowgrid OS"** (commit `bc9aaf6`): sidebar platform
tag, page title, auth/onboarding kickers, API title, README/CLAUDE.md.
Domain **flowgridos.co.uk** purchased. The go-live checklist lives in the
Notion task **"Get flowgridos.co.uk live"** (Ultimate Brain Tasks DB,
project "Flowgrid OS"): Part A (user: Cloudflare nameservers, Vercel
domain `app.`, Railway api domain `api.` on port 8000) then Part B
(Claude: CORS_ORIGINS, NEXT_PUBLIC_API_URL rebuild, Supabase redirect
allow-list, R2 bucket CORS, smoke test). Name was NOT on the sprint
shortlist — user still owes a trademark/Companies House screen.

**QA pass done (1 Aug, driven in the user's Chrome).** All Hearth flows
verified live: hero states, ⌘K, cited chat, Stop, research, slides→pptx,
settings, usage, chat delete, dev-project creation + status card. Fixes
that came out of it (commits `2eed3aa`, `6f2ab19`):
- CJK-bracket citation markers (【c:…】 from GLM/DeepSeek) now resolve in
  both api and worker resolvers (+test).
- Chat answers render **markdown** (`components/markdown.tsx`,
  `AnswerMarkdown`, `.md-answer` styles) with [n] cite buttons injected
  recursively; streaming buffer too.
- Sidebar refreshes after dev-project creation; grounded-badge grammar.
Still unverified: 360 px drawer (window wouldn't resize), file-upload
dialogs (logo/slides template).

**Staging is fully current** (api + worker + web at `bc9aaf6`):
EXA_API_KEY is live on the Railway api service (user-run CLI set;
dashboard attempts didn't reach the service env) and research mode was
**verified end-to-end on staging** as Struvers2. `features.web_search`
on for Struvers2.

**Notion is current**: project page renamed "Flowgrid OS"; Build Status
section added; milestones ticked (Phase 1 core, Groundwork+staging,
name chosen); tasks updated (developer-hire task closed as
overtaken-by-events; new tasks: pilot onboarding 15 Aug, domain go-live
8 Aug, staging QA 5 Aug — done in substance, Stripe 15 Sep).

**Local dev state:** api uvicorn on :8000 (restarted 1 Aug, NO --reload
— restart it after API changes), pnpm dev on :3000. Dev tenant Struvers
has a "QA Demo Scheme" dev project + a few QA test chats (kept as demo
data). One pre-fix research message in dev DB still shows raw 【c:…】
markers (historical data, not a bug).

**Team visibility landed (2 Aug 2026 evening,** commits `a560d01..`**)**:
- **Chats truly private** — migration **0008** (`conversations.visibility`),
  admin/owner read override removed; **share with team** = read-only for
  members (sidebar "Shared with team" section, ⌘K "shared" tag, ShareBar
  toggle in chat, read-only strip replaces composer). ASSUMPTIONS **#18**.
- **Tenant activity feed** — `GET /activity` (curated allowlist over
  audit_log, actor emails, target titles) + "Recent team activity" card on
  the hero (`activity-card.tsx`).
- **Refetch-on-focus** — WorkspaceProvider refreshes projects+conversations
  on visibilitychange (20 s throttle).
- Sidebar chat lists extracted to `sidebar-chats.tsx`; new
  `share-bar.tsx`. Dev DB migrated to 0008. Staging still at `bc9aaf6` —
  **run migration 0008 on staging before deploying these commits**.
  Manual two-user QA of sharing not yet done (needs two Struvers sessions).

**Next up:** (1) domain Part B when the user finishes Part A; (2) pilot
consultancy onboarding (PRD §9) — the platform is ready; (3) Stripe
billing (Slice 5); (4) Slice 6 hardening — draft latency is the top item.

## 6d. CRM module + operator console (2 Aug 2026, after §6c)

**CRM contact book — all four phases live on dev AND staging** (commits
`5e8cece`, `c7f09b9`, `fb11b6f`, `7f95d45`; plan agreed in-chat for the
consultant evaluation):
- **Migration 0009**: `crm_companies` (structured UK address),
  `crm_contacts` (phone+mobile, free-text address, `tags text[]`,
  per-tenant unique `lower(email)` → 409 `duplicate_email`),
  `crm_contact_projects` (join to **core** `projects`, chosen over
  `uuid[]` for FK cascade). Standard RLS; tables seeded in
  `tests/conftest.py` and covered by `test_isolation.py` TENANT_TABLES.
- **API**: `/contacts` + `/companies` in `app/routers/crm/`, gated on
  `tenants.features->>'contacts'` (mirrors `require_projects`). FK checks
  bypass RLS, so cross-tenant `company_id`/`project_id` are rejected by
  RLS-scoped existence checks. `POST /contacts/import` (CSV text, 2MB/2000
  rows, header normalisation incl. first/last-name combine, email-dedupe
  update-in-place, tag merge, company auto-create, line-numbered skip
  reasons). Deleting a company detaches its contacts (`set null`).
- **Web**: `/app/contacts` (People/Companies toggle, search, tag chips,
  slide-over editors, Import CSV w/ result banner), flag-gated sidebar
  entry, project-room **Contacts** tab (link/unlink), `lib/crm.ts`.
- **⌘K + chat**: `GET /search` gained a flag-gated `contacts` group;
  palette hands off to `/app/contacts?c=<id>` (auto-opens editor). Chat
  injects matching contact/company records via `app/crm/lookup.py`
  (stopword-filtered token ILIKE, possessive stripping) under
  `CONTACTS_PROMPT` — quoted-exactly, no-invention, deliberately **no**
  `[c:]` markers (resolver would drop them as fabricated).
- ASSUMPTIONS **#19**: `proj_stakeholders` deliberately NOT unified.

**Operator console + invite-only signup** (commit `f30dbae`,
migration **0010** widens `invites.role` to allow `'owner'`):
- `PLATFORM_ADMIN_EMAILS` (login-email match, `is_platform_admin` in
  `app/auth.py`) gates `/admin/*`. `POST /admin/tenants` creates a client
  workspace (seats/trial/features/brand-accent + LiteLLM key) and returns
  an **owner-role invite**; operator holds no membership. Reissue via
  `POST /admin/tenants/{id}/owner-invite`. Tenant-facing `InviteCreate`
  still caps at admin|member.
- `GET /admin/tenants` (fleet view w/ members, pending invites, month
  usage) uses **`db.platform_tx()`** — THE single fenced cross-tenant
  owner-role connection; never use it in tenant-facing handlers.
- `OPEN_SIGNUP=false` → `POST /tenants` 403s (`signup_closed`) except for
  platform admins. Web `/admin` page (standalone route, outside the /app
  shell): fleet table, new-workspace slide-over, copyable invite links.
  Shared `Panel` moved to `apps/web/components/Panel.tsx`.

**Environment state**: dev DB at **0010**; `PLATFORM_ADMIN_EMAILS=
clive@platform91.com` in `apps/api/.env` (OPEN_SIGNUP defaults true
locally). Staging: api + web deployed, DB at 0010,
`PLATFORM_ADMIN_EMAILS=clive@platform91.com` + `OPEN_SIGNUP=false` on the
Railway api service — **staging is invite-only**; new client workspaces
only via `/admin`. Contacts flag ON: Struvers + W1 Proof (dev), Struvers2
(staging). API suite now **177 tests**. §6c's "staging still at bc9aaf6"
is superseded — staging is fully current.

## 6e. Code-review fixes + deploy (2 Aug 2026, after §6d)

A high-effort `/code-review` over the §6d diff (57 changed files) returned
**10 verified findings — all fixed** in three commits: `9e0f10e` (activity
leak), `3ecb7fc` (CRM API), `d583dcf` (web). Merged fast-forward to `main`;
CI + App images green. **New invariants a future session must not undo:**

- **Audit meta is not a safe place for content.** `patch_conversation` now
  attaches `meta={"title": ...}` **only on share**, never on unshare —
  `/activity` returns `meta` verbatim to every member, so the unshare row
  was publishing the title of a chat the owner had just made private.
  Migration **0011** scrubs the key from existing rows; its `downgrade` is
  deliberately a **no-op** (restoring the titles would restore the bug).
- **Patch models reject an explicit `null`** on NOT NULL columns via the
  `NotNull` `BeforeValidator` in `app/crm/schemas.py` (`ContactPatch.name`
  /`.tags`, `CompanyPatch.name`) → 422, not a 500 from asyncpg. Unset still
  means "unchanged"; nullable `company_id` still accepts null.
- **The CSV importer must not out-write the editor.** Field caps live once
  in `app/crm/schemas.py` (`NAME_MAX`, `JOB_TITLE_MAX`, …) and the importer
  imports them; a row whose email fails `EMAIL` is **skipped with its line
  and reason**, not stored. Previously such rows imported fine and then
  could never be saved again from `ContactEditor`.
- **`like_contains()` in `app/sqlutil.py` is now the only way to build an
  ILIKE pattern** — escapes `%`, `_`, `\`. Contacts, companies and
  `global_search` all use it (the latter's private `_LIKE_SPECIALS` is
  gone). Unescaped, `_` silently matched any character and `%` matched the
  whole tenant.
- **Chat lookup matches whole words** (`app/crm/lookup.py`): a POSIX
  `\m(tok|tok)\M` regex over names/company names, plus email matched in
  **full or by local part**. Substring matching put a bystander's mobile
  and home address into the prompt ("the SAM report" → Samantha Fry), and
  a bare domain token returned everyone at that company. These are private
  contact details — a wrong match is a disclosure, not just noise.
- **`GET /contacts` has an opt-in `limit` (1–100)**, used by pickers. There
  is deliberately **no default cap**: silent truncation in the address book
  would read as "these contacts no longer exist".
- **Web guards fail closed.** The composer's `readOnly` no longer treats
  "absent from `ws.conversations`" as writable — that list is also empty
  when its fetch failed. Ownership is positive: unknown id ⇒ read-only
  unless this panel created it (`createdHereIds`). New context field
  **`ws.conversationsLoaded`** distinguishes "no chats" from "fetch
  failed"; the banner wording depends on it.
- Contacts page: `Empty` (onboarding) now keys off the **unfiltered**
  list, with a separate `NoMatches` + Clear filters for filtered-to-nothing.
  `ContactsTab` picker is a debounced server-side search (no wholesale
  fetch) and link/unlink surface failures. `InviteLink` is reused for
  invite **re-issue** (prop widened to `{name, invite}`) so the token is
  always rendered — a clipboard rejection previously discarded the only
  copy of a live invite.

**Deploy gotcha (cost us one failed deploy):** `railway up` uploads the
**linked project root**, not your cwd — running it from `apps/api` sends
the whole repo and Railpack fails with "could not determine how to build".
Correct form, from the repo root:
`railway up ./apps/api --path-as-root --service api` (reproduces the
`DOCKERFILE` builder earlier deploys used). Migrations were then run inside
the deployed container: `railway ssh -s api "alembic upgrade head"` — note
the **remote** shell expands `$$`, so dollar-quoted SQL in a `railway ssh`
one-liner breaks; use `%s` params instead.

**Environment state**: `main` = `d583dcf` (origin/main had been **11
commits behind** — the whole §6d series was local-only until this push).
Staging redeployed from that commit: Railway `api` (health OK) + Vercel
`ops-engine-staging-web`; **staging DB at 0011**, worker untouched (no
changes). Staging had **zero** `conversation.unshare` rows, so the scrub
was a no-op there — nothing had actually leaked. API suite now **185
tests**. ⚠️ **Local dev DB is still at 0010** — run
`cd apps/api && uv run alembic upgrade head` before working on audit/feed
code.

## 6f. Module kit + drafting-engine extraction (3 Aug 2026) — Grantwork's foundation (built, see §6g)

**Grantwork is built** (§6g); everything below is the ground it stood on, and
is still the reference for how any future module is wired. Spec: `docs/modules/grantwork-prd.md`. Sequencing and
rationale: `docs/vertical-module-roadmap.md`.

### What shipped today (all on `main`, pushed, CI green)

| Commit | What |
| --- | --- |
| `8cfbcc7` | Module manifest, RLS coverage test, `PATCH /admin/tenants/{id}/features` |
| `9b62239` | Vertical-module roadmap + mini-PRDs (Grantwork, Tenderhouse, Assurance) |
| `322f869` `6c35e6c` | CI actions off the deprecated Node 20 runtime |
| `d1d4e62` | Worker image builds again — CPU torch (see below) |
| `cf9124e` `b92f68d` | Staging checklist corrections |
| `f5fa56f` | Operator console: edit + suspend workspaces (migration **0012**) |
| `760df09` `30dc4d2` | Web: module flag guard; suspended-workspace screen |
| `c62b6d7` | **Drafting pipeline extracted from Groundwork** — the thing Grantwork builds on |

Suites at the time of this section: **API 195**, **worker 31**, **web 10**
(`pnpm test` — vitest + Testing Library, added 3 Aug in `18c6f3d`; covers the
module feature gate and the projects page). Web coverage is still thin —
anything outside those two files is verifiable only by running the app.
API is **196** as of `ff957ab` (§6g).

### The drafting seam (read before writing any Grantwork drafting code)

`worker/drafting/` is now module-agnostic and owns the pipeline, the
`LlmLedger` cost guard (≤15 calls, ≤24k context), hybrid retrieval, prompt
construction, DOCX assembly, citation resolution and the `[TO CONFIRM]`
contract. `worker/drafts/` is the **Groundwork adapter** and is the worked
example to copy.

A vertical supplies one `DraftModule` (`worker/drafting/engine.py`):
`storage_segment`, `job_table`, `system_prompt`, `skeletons`, `tables`, and
four callables — `gather`, `queries_for`, `scope_weights`, `register`. Its
pack subclasses `DraftPackBase` (`worker/drafting/pack.py`) and overrides
only the hooks that differ; Groundwork overrides five (`doc_title`,
`subject_lines`, `prompt_notes`, `warning_block`, `source_notes`).
Build the system prompt with `prompts.grounding_prompt(domain)` — never
restate the grounding contract.

### Module registration (what a new flag now costs)

`apps/api/app/modules.py` is the manifest. Add one `Module(flag, label,
tables, feed_prefix)` entry and `FEATURE_FLAGS`, the gate dependency, the
activity-feed namespaces and the RLS coverage test all follow. Then:

- migration: tables + `enable_tenant_rls()` from `migrations/rls.py`
- `app/<mod>/schemas.py` for Pydantic models (**not** core `schemas.py` —
  ASSUMPTIONS #20; Groundwork's split is legacy, do not copy it)
- `sqlutil.PATCHABLE_COLUMNS` entries for any PATCH endpoint
- router package + registration in `app/main.py` (**order-sensitive**)
- `tests/test_isolation.py` `TENANT_TABLES` + attack list + `conftest`
  fixture rows
- web: `lib/<mod>.ts` client, pages, sidebar nav + icon, and the flag guard
  via `app/app/module-gate.tsx` (`useModuleEnabled` + `ModuleDisabled`)
- worker jobs: `app/queue.py` enqueue method + `worker/main.py` functions

`test_every_module_table_has_rls` is the safety net: a table declared in the
manifest without RLS **and** both policy clauses fails the suite. This is
the check that makes the previously-silent failure loud — do not weaken it.

### Environment state

- **Staging fully current**: api `16:48`, worker `16:07`, web (Vercel)
  `19:05`, all 3 Aug. Staging DB at **0012**.
- **Migrations run as a Railway pre-deploy hook** on the api service
  (`alembic upgrade head`). It is Railway-side state, not in the repo — see
  the header note in `docs/staging-deploy-checklist.md` for how to re-apply.
- **Deploys**: `railway up ./apps/api --path-as-root --service api`.
  `--path-as-root` is mandatory (see checklist). Web: `vercel --prod` from
  `apps/web`. **Railway builds from source and never pulls the GHCR
  images** — those serve local dev.
- **Local worker image refreshed** to the CPU-torch build (9.54 GB → 2.79
  GB). Torch PyPI wheels bundle CUDA; the Dockerfile now installs
  torch/torchvision from the PyTorch CPU index first so docling never pulls
  it. Do not undo that.
- Postgres/redis/litellm services last deployed 31 Jul — correct, they only
  redeploy on config change.

### Open items (not blockers for Grantwork)

1. **Hard delete of a workspace.** Suspension shipped; purge did not. Needs
   the R2 prefix, the LiteLLM virtual key, and an RLS delete policy on
   `tenants` (deliberately absent since 0001).
2. Groundwork's schema split (ASSUMPTIONS #20) left as-is.
3. Roadmap §1.6 hygiene: only the web flag guard was done.
4. Two harmless ad-hoc SQL parse errors in the staging Postgres log (2 Aug,
   3 Aug) — not app code, no data touched; something holds a direct psql
   connection to staging.

### Suggested first move on Grantwork

Phased, committing on green at each step, because CLAUDE.md's hard
constraint is that **a migration is not done until its table has RLS and an
isolation test**:

1. Migration `0013` — `grant_*` tables + `enable_tenant_rls()`; manifest
   entry; isolation tests and `conftest` fixture rows. Commit.
2. Routers + schemas + the `grants` gate. Commit.
3. Seeds: funder catalogue extending the `proj_ref_programmes` shape, with
   `last_verified`/`next_review`. Commit.
4. Drafting: pack + skeletons + registry via `DraftModule`. Commit.
5. Web: client, pages, nav, flag guard. Commit.

## 6g. Grantwork build — all five steps done (3 Aug 2026)

**Rulings taken before any code** (founder, recorded as ASSUMPTIONS **#23**):
two funding surfaces rather than one — Grantwork does not absorb Groundwork's
funding tab; applications are **standalone** rows, *not* core-project
extensions (the opposite of #1's ruling for `proj_projects`, because a
charity's twenty-bid portfolio would flood the sidebar and split the vault);
`grant_applications.project_id` is a nullable soft link to the **core**
`projects` row. All four draftable document kinds are in scope for this phase.

**Shipped** (`ff957ab`, on `main`, **not pushed**): migration **0013** — ten
tenant tables (`grant_funders`, `grant_applications`, `grant_stages`,
`grant_tasks`, `grant_reporting_periods`, `grant_documents`,
`grant_conditions`, `grant_impact_measures`, `grant_outcomes`,
`grant_draft_jobs`) through `enable_tenant_rls()`, plus select-only
`grant_ref_funders` / `grant_ref_templates`. Manifest entry
`Module(flag="grants", label="Grant funding", feed_prefix="grants")`,
mirrored in `apps/web/lib/admin.ts`. `two_tenants` seeds a full chain through
all ten tables, and `test_grantwork_cross_module_link_does_not_widen_
visibility` covers the soft link both ways — including asserting the
FK-bypasses-RLS hazard outright, which is why step 2's routers must validate
every referenced id with an RLS-scoped existence check (#19's ruling).

Suites green: **API 244** (196 / 228 / 231 / 244 after steps 1–4),
**worker 61** (was 31), web 10; ruff + mypy clean.
**Local dev DB upgraded to 0013.** Staging DB is still at **0012** — 0013 goes
out with the Railway pre-deploy hook on the next api deploy.

**Step 2 shipped** (`e420de1`): **26 routes** under `/api/v1/grants` behind the
`grants` gate — funders + catalogue, applications (create seeds the spine),
stages/gates, tasks, document registry, conditions, reporting periods, the
tenant-wide reporting calendar, impact measures and outcomes. All models in
`app/grants/schemas.py` (#20). `app/grants/analytics.py` holds the §1.2
derived figures as pure functions with their own unit tests.

Rulings taken in step 2, worth not re-litigating:
- **Award conditions seed on first award, never at creation** — an
  application being written has no offer, so seeding obligations up front
  invents them. Idempotent, so re-recording an award cannot duplicate them.
- **`status` is not in `grant_applications`' `PATCHABLE_COLUMNS`** — the
  pipeline moves through `POST .../status`, which seeds those conditions and
  audits the transition; a bare PATCH would skip both.
- **The reporting calendar is top-level, not a subresource** — the exposure
  is the returns you forgot, across every application.
- The **template library** (`grant_ref_templates`, `app/grants/fixtures/`)
  landed here rather than in step 3 because application creation cannot be
  tested without it. It is our own product decision. The **funder catalogue**
  (`grant_ref_funders`) is still step 3: those rows are external fact and
  every one carries a `last_verified` date somebody has to earn.

**Step 3 shipped** (`2b10a6a`): 13 `grant_ref_funders` rows +
`seed_funder_catalogue()`. **Read ASSUMPTIONS #24 before touching this data.**
The rows were compiled from model knowledge and verified by nobody, so every
one ships `status='unverified'` with `next_review == last_verified` — stale on
load, by design. Both existing safety mechanisms then fire: the UI badges the
row, and any draft built from it gets the first-page warning block (the engine
already warns on `status != 'open'`). The upsert never touches `status` /
`last_verified` / `next_review`, and two tests guard the fixture file itself,
because the tempting fix for a catalogue full of warnings is to edit the dates.
**Promotion is an operator act**, not a code change: verify each field against
the funder's own guidance, then set `status='open'` and
`next_review = current_date + 90` in the database.

Run the seeder with the owner connection: `uv run python -m app.grants.seeds`
(templates + catalogue, idempotent). Dev DB is seeded; **staging is not**.

**Step 4 shipped** (`4cc0b13`): `worker/grants/` — one `DraftModule`, the
four skeletons, three data tables, the register, and the impact card. Nothing
in `worker/drafting/` changed, which is the module kit working as intended.
Worker jobs `grant_draft_document` + `generate_impact_card`; queue methods
`enqueue_grant_draft` / `enqueue_impact_card`; routes
`POST/GET .../drafts`, `GET /grants/drafts/{job_id}`, `POST .../impact-card`.

Decisions to know before touching the drafting layer:
- **Monitoring returns retrieve nothing from the vault.** No `QUERY_SETS`
  entry ⇒ the engine skips the embedding call. A return accounts for what the
  grant did, and those facts are module rows.
- **Figures never come from the model.** An unrecorded measure renders the
  words "not recorded", not a dash and not a zero — asserted in both the DOCX
  and the PDF.
- **An unverified catalogue row warns on page one** of any bid (only bids;
  on a return it is noise). This is #24 paying off.
- **`scope_weights` follows the project link** (#23): linked ⇒ boost that
  project's vault docs; standalone ⇒ whole vault, unweighted.
- **Monitoring returns get per-period registry rows** (#9 suffixing) carrying
  `reporting_period_id`, and registering one moves its period to 'drafting'.
  The other three version onto their seeded launcher rows.
- **The impact card is an export, not a `DraftIn` kind** — its own job kind
  and route. No LLM touches it, so every figure is a recorded row, which is
  what makes it safe to send to a funder when a draft is not.

**Step 5 shipped** (`5cb3437`) — the §6f sequence is complete.
`lib/grants.ts`, `/app/grants` (portfolio + reporting calendar),
`/app/grants/new`, and the application room with six tabs (stages & gates,
tasks, bid pack, conditions, reporting, impact). Sidebar entry + `GrantIcon`;
`GRANTS_DISABLED` in `module-gate.tsx`. Every page reads the flag from
workspace state before fetching, and a mid-session 404 falls back to the same
panel.

Three UI decisions that carry a backend guarantee — don't "simplify" them:
- The pipeline tile shows **weighted** value, not the sum of asks.
- A blank measure shows **"not recorded"**, never 0.
- An unverified/stale catalogue row **badges** on the application header and
  the create form, saying the drafted bid carries the same page-one warning.

### Grantwork: what is done, and what is not

**Done** — all five steps, on `main`, **not pushed**: migration 0013 + RLS +
isolation; 29 routes + schemas + analytics; template library + funder
catalogue; the drafting adapter + impact card; the web layer.
Suites: **API 244, worker 61, web 27**; ruff, mypy, typecheck, lint, build
all clean. Local dev DB at 0013 and seeded.

**Live smoke test run 3–4 Aug** (see §6h) — it found and fixed a serious
pre-existing bug in the shared drafting engine.

**Not done, in priority order:**
1. **`funding_application` has not completed end-to-end.** Its `budget`
   section (the only `reasoner`-alias section in the module) was the one that
   exposed the bug in §6h. The fix is verified at call level — the same
   section now returns 541 tokens of prose where it returned nothing — but a
   full run is still owed, blocked only by Groq's **daily** token quota,
   which this testing exhausted (198.7k of 200k TPD).
2. ~~**Staging has nothing.**~~ ✅ **Fully deployed 4 Aug** — all three
   services carry Grantwork:
   - **api**: pre-deploy hook took the DB to **0013** (12 grant tables, every
     one with RLS and a `tenant_isolation` policy); seeder run in-container
     (1 template, 13 catalogue rows, all correctly `unverified` + stale); 29
     grant routes live, 401 unauthenticated.
   - **worker**: 5 arq functions registered including `grant_draft_document`
     and `generate_impact_card`; carries the 3 Aug drafting fix
     (`MAX_OUTPUT_TOKENS` 4096, `REASONING_EFFORT` low); WeasyPrint present,
     so the impact card can render.
   - **web**: `/app/grants`, `/app/grants/[id]` and `/app/grants/new` all in
     the deployed production build.

   **Nothing is switched on yet**: no staging tenant has the `grants` flag
   (only `Struvers2`, with projects/contacts/web_search), so the module stays
   invisible until an operator enables it via
   `PATCH /admin/tenants/{id}/features`. Enabling it is now safe — the whole
   path is deployed — but see item 3: every catalogue row on staging is
   deliberately unverified, so any bid drafted from one carries the
   first-page warning.
3. **The funder catalogue is unverified** by design (#24). Until an operator
   promotes rows, every bid drafted from one carries a warning — correct, but
   it means the module does not look finished to a demo audience.
4. **No `grants` flag is enabled on any tenant.** Enable via
   `PATCH /admin/tenants/{id}/features` in the operator console.
5. Web coverage is the portfolio page + two lib helpers; the room's six tabs
   are verifiable only by running the app.

Two schema divergences from the PRD's §1 entity list, both argued in #23:
`grant_tasks` (the seeded library specifies standard tasks, which the listed
entities had nowhere to hold) and `grant_draft_jobs` (the shared engine takes
a per-module `job_table`).

---

## 6h. Live smoke test + a drafting-engine bug (3–4 Aug 2026)

First real Grantwork drafts, run against the local worker and the LiteLLM
gateway on tenant **S45 E2E** (`7888931f…`, disposable). It found a
**pre-existing bug in the shared engine that affected Groundwork too** —
fixed in `2bd3f05`.

### What the bug was

Both drafting aliases are now reasoning models that bill thinking against
`completion_tokens`; the pipeline was written when they were not.
`drafter` (gpt-oss-120b) spends 675–709 tokens thinking, so against the old
1024 ceiling every section of a data-heavy document hit
`finish_reason=length` — and the ones that reasoned longest returned **no
content at all**. `reasoner` (GLM-5.2) is worse: it thinks to fill whatever
budget it is given, and spent an entire 4096 on one real section, returning
zero prose.

**The consequence, not the cause, is the thing to remember.** An empty
section added no paragraphs, and the pipeline assembled, uploaded and
registered the document anyway. A monitoring return reached the registry
with **six of its nine sections missing**, marked `succeeded` with
`to_confirm_count: 0` — which reads as a clean draft. Nothing noticed.

### What changed

`MAX_OUTPUT_TOKENS` 1024 → 4096; `REASONING_EFFORT = "low"` on every call
(the ceiling alone cannot bound a model that thinks to fill it);
`EmptySectionError` fails the job rather than filing a document with a gap
(the outline call opts out via `allow_empty`, since it is designed to
degrade to `{}`); one retry per section before that failure; truncation
tracked on the ledger, marked `[TO CONFIRM]` in the document so it reaches
the UI count, and recorded as `truncated_sections` in the audit meta.

### What the smoke test proved works, live

| Path | Result |
| --- | --- |
| `monitoring_report` | **9/9 sections** after the fix (3/9 before). Impact table rendered real recorded figures, **"not recorded"** for the blank measure, 107% over-delivery uncapped. Conditions table correct. |
| `case_for_support` | 8/8 sections, vault retrieval + resolved citations, **0 stripped citations** |
| `impact_card` | PDF in 0.7s, **0 LLM calls** |
| Registry | per-period key `monitoring_report_<id8>` carrying `reporting_period_id`; one-offs versioned onto seeded rows |
| Side effects | period auto-moved to `drafting`; `usage_events` per call (drafter + reasoner + embed); audit meta carried to_confirm / stripped_citations |
| Failure paths | `EmptySectionError`, cancellation, `ReadTimeout` and a provider 429 all recorded cleanly, **no orphan rows, no partial documents** |

### Known gaps this surfaced (not fixed)

1. **A failed draft is unmetered.** `usage_events` are written only in
   `register()`, which runs on success, so a job that fails after nine model
   calls records **zero** cost. That contradicts CLAUDE.md's "cost telemetry
   on every LLM call" and understates real spend.
2. **The grounding contract is Groundwork-shaped.** It tells every module
   that "budget and funding figures are rendered as tables" — on a Grantwork
   monitoring return there is no budget table, and the model duly referred to
   "the accompanying financial table", which does not exist.
3. **Groq free tier is 200k tokens/day**, which one afternoon of drafting
   exhausts. A single draft is ~35k in / ~16k out.

### Test data left behind

Tenant **S45 E2E** has the `grants` flag on and one application, *Smoke test
— community garden* (`0e470acc…`), with its funder, 6 conditions, 3
measures, 1 reporting period, 2 outcomes and 5 draft jobs. Disposable —
`delete from grant_applications where id = '0e470acc-487a-4f65-b325-5ed932b941fb';`
clears the lot, and the flag comes off in the operator console.

## 6i. Drafting engine brief closed + a third bug of the same family (4 Aug 2026)

DRAFT-001 (`35fedcc`) and DRAFT-002 (`b7a93b9`) are both done, and a review
pass found a third instance of the 3 Aug reasoning-model bug (`0b19e07`).
Suites now **API 247, worker 82, web 27**; ruff, mypy, typecheck, lint, build,
`pip-audit` (api + worker) and `pnpm audit` all clean.

### DRAFT-001 — metering moved into the engine

`write_usage()` in the new `worker/drafting/usage.py` is now the only place a
draft's cost is recorded, called on the success path and inside
`_mark_failed()`; both `register_draft()`s lost their copy. The ledger is
hoisted above the `try` as the brief advised.

One decision the brief left open: `_mark_failed` writes the **failure status
and the usage rows in two separate transactions**, status first. Same-tx would
mean a usage-write failure rolls back the status — and since every call site
suppresses exceptions, the job would silently stay `running` and the UI would
poll it forever. An empty ledger skips the second transaction entirely, which
also keeps the cancellation path as short as it was.

Tested on both sides of the ASSUMPTIONS #13 line, because the API venv has no
`python-docx` and so cannot import the engine at all:

- `apps/worker/tests/test_drafting_usage.py` — drives `run_draft` against a
  fake pool for control flow: failure mid-draft, cancellation, cost guard,
  gather-level failure (bills nothing — no zero rows), success, embedding.
- `apps/api/tests/test_worker_drafting_usage.py` — `write_usage` against the
  migrated schema: column set, the `usage_events_kind_check` constraint, and
  RLS refusing a write aimed at another tenant.

### DRAFT-002 — and the same claim hiding in a pack note

The table instruction moved into `section_prompt()`, where `section.table` is
known, and the contract gained the prohibition instead. The generic label
(`section.table.replace("_", " ")`) reads fine for all five renderer keys, so
`Section` did not need a label field.

**Not in the brief:** `GrantPack.prompt_notes()` carried the *same* blanket
claim — "outcome figures are rendered as a table" — to all nine sections of a
monitoring return, including *Financial position*, the section that invented
the table. Fixing the contract alone would have left the bug live. It keeps
the figures discipline and drops the table claim. If a third module ever says
anything about tables outside `section_prompt()`, this is the failure to
expect.

### The third reasoning-model bug: document summaries (`0b19e07`)

`worker/summarize.py` was never touched by the 3 Aug fix and had **no tests**.
It asked `drafter` — gpt-oss-120b, 675–709 tokens of thinking before it writes
— for 512 output tokens, so the budget went entirely on reasoning. Three
silent failures followed: `content` is `None` on some gateways so `.strip()`
raised `AttributeError`; ingest catches summary failures by design, so the
document reached `ready` with no summary and no error; and where the gateway
returned `""` instead, an empty summary was stored **and embedded as a summary
chunk**, which is retrieval pollution rather than an absence.

Any document ingested since the aliases became reasoning models probably has
no usable summary — "what are the key messages of X?" is the feature that
quietly stopped working. **Worth re-ingesting the staging/dev vault to check.**
Now: `max_tokens` 1536, `reasoning_effort` low, an empty reply raises, and the
summary's `usage_events` row is written even if embedding it fails.

### Live confirmation, same day

Run on tenant S45 E2E, monitoring return on the smoke-test application.

**DRAFT-001 — proved by an accident.** The run died on a Groq **429** after
eight model calls (the free tier's daily budget, exhausted again). Before the
fix that is exactly the shape of job `4b09b714…`: `llm_calls 0, cost_usd 0`.
After it, the failed job wrote **eight `usage_events` rows, $0.0138** —
7 × `drafter` plus the `reasoner` section — while the job row's own counters
stayed zero, because those belong to `register()` and register never ran.
`usage_events` is the ledger of record and it is no longer blind.

**DRAFT-002 — confirmed without spending the rest of the quota.** The 429 hit
section 8, so no document was assembled; but the section that caused the bug,
*Financial position*, is the module's only `reasoner` section and `reasoner`
is DeepInfra, not Groq. Regenerating that one section (~4k tokens, no Groq)
returned:

> "The project budget has not yet been agreed [c: a2], and no budget
> breakdown is available in the data to compare planned versus actual
> spend. … [TO CONFIRM: the amount of grant income received in Year 1 …]"

against the old "…are presented in the accompanying financial table." No
table reference at all, and the gap is marked rather than papered over.
Checking the prompts on the same real pack: the `finance` section (no table)
contains **zero** standalone occurrences of the word — the only matches are
`charitable` and `timetable` inside the tenant's own records, which is why the
offline test asserts on the prompt rather than on a substring — and the
`outcomes` section (`table=impact`) contains exactly one.

Worth remembering: **a single section can be regenerated in isolation** for
about a tenth of a draft, and picking a section by its alias picks the
provider. That is the cheap way to confirm any future prompt change.

### Open, in priority order

1. ~~**`funding_application` end-to-end**~~ (from §6g item 1) — **done in
   §6j**: 11 calls, 35.1s, succeeded. It was blocked on the Groq quota, never
   on the kind itself.
2. **Re-ingest existing vault documents** — every document ingested since the
   aliases became reasoning models has no usable summary (`0b19e07`). The fix
   only helps new ingests; the back catalogue needs re-running.
3. **Chat is unmetered when a stream dies** — `app/routers/conversations.py`
   returns from the generator on a stream error before the `usage_events`
   write, and `StreamResult` only gets its numbers from the final usage chunk,
   so there is nothing measured to record. Same constraint-5 class as
   DRAFT-001 but on the busiest surface; the fix means billing an estimate,
   which is a product decision, not a bug fix.
4. ~~**Chat sends no `max_tokens` and no `reasoning_effort`**~~ — **done in
   §6j.** It turned out to be the largest single cause of felt chat latency,
   not just a cost and empty-message risk.
5. **Ingest is unmetered if the chunk write fails** — embedding is paid for
   before the transaction that records it.
6. **`packages/shared` is a README and nothing else** — no `types.ts`, no
   drift check in CI, no import from `apps/web`, despite CLAUDE.md's layout
   table. Either build it or correct the doc.

## 6j. LLM latency review, and the first six fixes (4 Aug 2026)

Prompted by a plain report of "the site is fine, the LLM is slow". Full
findings in `docs/performance-review-aug-2026.md`; this is what it concluded
and what has landed.

### There was no single bottleneck — there were three

| Symptom | Cause |
| --- | --- |
| Long pause before *any* text appears | Chat sent no `reasoning_effort` and no `max_tokens`. Every chat alias is a reasoning model, and `stream_chat` forwards only `delta.content` — so the entire thinking phase rendered as a spinner on an open, billing connection. This is §6i open item 4, promoted from "risk" to "this is the cause". |
| Text arrives, but the page stutters | Every token re-parsed the whole answer *and every prior answer* through `ReactMarkdown`, plus a forced scroll reflow. Quadratic over a reply; a ten-message conversation did eleven full parses per token. |
| Drafts run 30+ min or die | Groq free tier — 200k tokens/day against ~51k per draft. `~3 min/call` is rate-limit backoff, not generation. |

The third is a **billing change, not a code change**, and it is the reason the
obvious-looking fix is wrong: parallelising sections against a quota-limited
endpoint converts a slow job into a failing one, and `num_retries: 2`
multiplies every 429 by three. **Do not parallelise `drafting/engine.py` until
paid Groq is confirmed working.** If it is confirmed, expect ~3–4× on the
section phase and it becomes worth doing.

### What landed

- **`app/litellm.py`** — `max_tokens: 4096` and `reasoning_effort: "low"` on
  the chat completion. 4096 is deliberately generous: `reasoning_effort` is
  what bounds the wait, `max_tokens` is only the runaway guard behind it, and
  `report`/`analyse`/`slides` need the room. Plus `StreamResult.ttft_s`,
  pinned to the first *renderable* delta.
- **`app/routers/conversations.py`** — the query embedding and the Exa search
  now overlap instead of running back to back (`exa_search` alone allows 15s).
  `return_exceptions=True` then `.result()`, so one failure cannot orphan the
  other task and the embedding error still surfaces first. Plus one log line
  per message with the full phase split, on failures too.
- **`worker/drafting/llm.py`** — `LlmCall.elapsed_s` and a per-call line.
  Backoff and slow generation look different in the distribution; this is what
  settles whether the Groq diagnosis was right.
- **`web/app/app/chat.tsx`** — `AssistantMessage` memoised, and deltas
  coalesced to one `requestAnimationFrame` instead of one `setState` per
  token. **The memo needed `onExport` changed to take the message id**: it was
  an inline arrow recreated every render, which would have defeated the memo
  silently. Keep every prop on that component primitive or referentially
  stable or it quietly stops working again.

Logging is new to this repo — stdlib loggers (`app.chat.latency`,
`worker.drafting.latency`), ids and counts only per spec §9.5, safe to leave
on in production.

### Tested

`apps/api/tests/test_chat_latency.py`, 5 tests, API suite 247 → 252.
`test_chat.py` stubs `stream_chat` wholesale and so can never see the request
body, which is exactly how three reasoning-model bugs reached production; these
drive the real client over `httpx.MockTransport` instead. Both load-bearing
tests were **checked to fail without their fix** rather than passing
vacuously — worth knowing that the first attempt to prove the overlap test was
itself wrong (awaiting `create_task` results in a loop is still concurrent;
the tasks are scheduled at creation).

### The Groq quota, solved without a Groq account

Paid Groq upgrades were closed to new accounts, so the billing fix in the
review was unavailable. **`drafter` now routes through OpenRouter instead**
(`openrouter/openai/gpt-oss-120b`), which resells the same Groq capacity —
provider order `["Groq", "Together", "Nebius"]`, `allow_fallbacks: false`,
`data_collection: deny`, the same shape `longdoc` already used. No new
account: `OPENROUTER_API_KEY` was already wired through both compose files
and both env examples.

Three things worth keeping straight:

- **All three pinned providers bill $0.15/$0.60**, which is exactly what
  `ALIAS_PRICES_PER_MTOK` already claims `drafter` costs in *both*
  `app/litellm.py` and `worker/drafting/llm.py`. That is why this specific
  order was chosen: cost telemetry and the spec §11 5%-reconciliation stay
  correct with no code change. **Adding a provider without checking its rate
  silently breaks §11.** Cerebras is ~4x faster than Groq (1,963 t/s vs 479)
  but bills $0.35/$0.75 — a ~64% understatement per draft — so it needs both
  price tables updated before it goes in the order list.
- **Direct-Groq numbers no longer apply.** The `~3 min/call` note in
  `worker/main.py` was free-tier backoff. Expect roughly 40s for a full draft
  at Groq's 479 t/s; the new `worker.drafting.latency` line is how to confirm
  it. Only once that is confirmed is parallelising sections worth doing.
- **`GROQ_API_KEY` is now unused** by any alias but left wired in compose and
  the env examples, so reverting is a one-line change.

Retries were split at the same time: `router_settings.num_retries: 2` still
suits the worker, and the API now overrides it per request with
`x-litellm-num-retries: 1` (`CHAT_NUM_RETRIES`) on both chat and query
embedding. Per-request rather than per-alias because **`drafter` serves both
surfaces** — analyse/report/slides/research route to it from chat as well as
from the drafting engine — so there is no alias-level split to make.

A correction to the review itself: §4 suggested DeepInfra as the fallback host
for `drafter`, calling it "slower per token". It is **48 t/s against Groq's
479** — a 10x gap that would have made drafts ~6 min rather than ~40s. The
advice stands only as a last resort, not as the recommended swap.

### Measured live, and it worked (4 Aug 2026, staging)

Chat went from **30–40s to under 2s**. Two real messages on staging, straight
from `app.chat.latency`:

| | Vault-backed | Plain chat |
| --- | --- | --- |
| `prestream_ms` (our work) | 1,305 | 115 |
| `ttft_ms` (wait for first word) | **356** | **166** |
| `total_ms` | **1,801** | **399** |
| `tx1_ms` / `retrieval_ms` | 74 / 78 | 115 / 0 |

Three things this settles, so nobody re-litigates them:

1. **`reasoning_effort` *is* honoured by GLM-4.7-Flash via DeepInfra.** The
   review flagged, twice, that it might not be — it is an OpenAI-family
   parameter and chat's own alias had never been tested with it. A 356ms TTFT
   disproves that. **No GLM-shaped `chat_template_kwargs` workaround is
   needed**; do not add one speculatively.
2. **The gateway adds no meaningful overhead**, so the key-auth caching idea
   in review §3.7 — explicitly labelled a hypothesis — is not worth chasing.
   A chat request reaches its first token in 166ms through the same hop.
3. **The shape of the problem inverted.** On a vault question more time now
   goes on our side (1.3s) than waiting for the model (0.36s), and 1,151ms of
   that is the *single* query-embedding round trip. DB work is 74ms and the
   hybrid search 78ms — neither is worth touching. If chat latency is ever
   revisited, that one embedding call is the only target left.

### Instrumentation shipped blind first — read this before adding any

The latency line was deployed and **emitted nothing**. Uvicorn installs
handlers only for its own `uvicorn*` loggers and never calls `basicConfig`, so
the root logger keeps its WARNING default and every `logger.info()` under
`app.*` was dropped before reaching a handler. Uvicorn's own INFO access lines
kept appearing throughout, so the absence looked exactly like code that had
never run. `arq` has the same shape and would have silently swallowed the
drafting timings too.

Fixed in `app/main.py:configure_logging()` and `worker/main.py:startup()`,
with `tests/test_logging_config.py`. One of those tests asserts a record
actually lands in a handler — `isEnabledFor()` alone still passes when nothing
is attached, and a record reaching no handler is just as lost. The tests reset
logging to uvicorn's default first, because `conftest` builds the app and would
otherwise leave the state under test already applied.

### Drafting confirmed, and `funding_application` finally ran

Two real drafts on staging (tenant Struvers2, application *Care Home*) after
`litellm` and `worker` picked up the OpenRouter change:

| Kind | Calls | Wall clock | Cost | Result |
| --- | --- | --- | --- | --- |
| `case_for_support` | 9 | **21.3s** | $0.0068 | succeeded, 12 to confirm |
| `funding_application` | 11 | **35.1s** | $0.0131 | succeeded, 13 to confirm |

Against ~33 minutes before, or a 429 death partway. **Zero 429s, zero
retries, zero `finish=length`** across all 20 calls, and both documents
registered with a file and `versions` length 1.

**`funding_application` has now run end-to-end** — closing §6g item 1 / §6i
item 1, the only kind that had never completed. It was blocked on the Groq
quota, not on anything wrong with the kind.

The per-call spread is the actual proof, not the total: 0.9–3.1s, tight and
even. Backoff is bimodal with multi-minute stragglers, which is exactly what
the old `~3 min/call` figure was measuring. This is clean generation.

**Those totals were a lucky window — quote ~18–56s, not the best figure.**
Five `case_for_support` runs on one day, same code and prompt: 17.8s, 21.3s,
29.0s, 52.3s, 56.4s. The fast ones had Groq serve all nine calls; the slow
ones did not. Capacity recovered within the day, so a slow spell is a window
to wait out, not a state to re-tune against. The cause is provider luck on the `drafter` alias, not a
regression: Groq's capacity through OpenRouter is intermittent, and a request
that falls through to a stand-in is 3–5x slower. Measured that hour — Groq
337–403 tok/s, Nebius 113–152, Together 76–116 — which is why the order became
`["Groq", "Nebius", "Together"]` (ASSUMPTIONS #25).

Two things that diagnosis established, worth not re-deriving:

- **The gateway itself adds nothing.** Calls it routed to Groq matched
  direct-to-OpenRouter rates (337–403 tok/s). When a draft looks slow, suspect
  which provider served it, not the proxy.
- **`elapsed_ms` covers LiteLLM's retries, `served_by` names only the winner.**
  A call logged `served_by=Groq elapsed_ms=33652` for 487 tokens is not Groq
  running at 14 tok/s — it is a failed first attempt plus backoff, then a fast
  success. **Do not compute tokens/sec from `elapsed_ms` and conclude a
  provider is slow.**

**Parallelising draft sections (review item 10) is DEFERRED, not closed** —
founder decision, 5 Aug 2026. It remains a legitimate optimisation; it is
simply not worth its cost today. Two measurements argue against it now:

- At 21–35s the prize is small. Ten sequential `drafter` calls account for
  ~16s, so even perfect concurrency saves ~10s of a 35s job.
- It cannot touch the biggest piece. In the `funding_application` run call 8 —
  the single `reasoner` (GLM-5.2) section — took **17.5s of the 35.1s total**,
  while the other ten averaged 1.6s. That is one request and cannot be split,
  so it survives any amount of parallelism.

Against that it costs real complexity: concurrent in-flight requests, more
rate-limit exposure, and a cost guard (`MAX_LLM_CALLS`, per-call context
ceiling) that is harder to reason about when calls overlap.

**Revisit if any of these change:**

1. **The `reasoner` section gets faster first.** It is the dominant term;
   until it shrinks, parallelising around it is rearranging the small half.
   This is the higher-value piece of work of the two, and the right first move
   if drafting speed is ever raised again.
2. **Skeletons grow past ~15 sections**, or a module adds a kind with many
   more `drafter` calls — the sequential tail scales linearly, the reasoner
   term does not.
3. **Drafting becomes interactive** (a user waiting on-screen rather than a
   background job). 35s is fine to wait for asynchronously and poor to watch.

If it is built: use a `Semaphore(3)`, keep the outline call and anything
depending on it sequential, and re-check the provider's rate limits first —
the original recommendation to do this ranked it #1 while drafting was still
on Groq's free tier, where it would have turned a slow job into a failing one.

### Not done, in priority order

All of these are now **optional**. Chat is under 2s and drafting 21–35s, so
none of them is fixing a felt problem; treat them as available work, not a
backlog to burn down.

1. **Cap chat history** — `conversations.py` fetches it with no `LIMIT` and
   re-sends all of it every turn, so prompt cost grows without bound. Agreed
   approach: a ~8k token budget keeping recent turns whole, using
   `routing.estimate_tokens`. Cost control rather than latency now.
2. **Move retrieved excerpts off the prompt prefix.** They are concatenated
   into the *system* message, so ~4–5k tokens of volatile content sit in front
   of the stable part and no provider prefix cache can ever hit. Moving them
   onto the final user turn makes the prefix cacheable.
3. **The query embedding is the only latency target left in chat** — 1,151ms
   of a 1,801ms vault-backed message, against 74ms of DB work and 78ms of
   hybrid search. Caching repeat questions is the cheap way in. Nobody should
   be optimising the database or the retrieval SQL.
4. ~~**Speeding up the `reasoner` alias**~~ — **done 5 Aug 2026**
   (ASSUMPTIONS #27). GLM-5.2 moved to CoreWeave via OpenRouter: confirmed
   over two drafts, the section fell from **17.5s to 4.07s / 4.18s** and
   `funding_application` from **35.1s to 25.9s / 24.4s**. It was 50% of the
   draft's wall clock and is now ~16%.

   Read #27 before touching any alias: the change shipped *broken* first.
   LiteLLM rejected `reasoning_effort` for `openrouter/z-ai/*` and the spec §4
   `reasoner: [longdoc]` fallback swallowed the 400, so three drafts had their
   financial section written by deepseek-v4-flash and metered as `reasoner` —
   all with `succeeded` job rows and plausible prose. The fix is
   `allowed_openai_params`, and the reason it was findable at all is the
   `served_by` field now logged per call.
5. **Parallelise draft sections — DEFERRED**, not closed (founder decision,
   5 Aug 2026). See the drafting section above for the three conditions that
   should bring it back, and why item 4 comes first.
6. `--workers` on uvicorn (`apps/api/Dockerfile`) — single process today. Not
   a current bottleneck; it will become one under concurrent load.

**Answered by measurement — do not re-open:**

- **Gateway caching** (review §3.7) was the one item flagged as a hypothesis
  rather than a code-confirmed finding. Measured: the gateway adds no
  meaningful overhead (166ms to first token through the same hop). Not worth
  chasing.
- **Cutting embedder dimensions from 2048** — needs a full re-embed, a
  migration and a new index, degrades retrieval, and saves milliseconds on a
  path that is not the bottleneck.
- **A GLM-shaped `reasoning_effort` workaround** — unnecessary, the parameter
  is honoured as sent (ASSUMPTIONS #26).

## 6k. Claims register — built end to end (12 August 2026)

**Start here** — this is the feature everything current sits on. §6l is the
latest change to it.

### What it is, in one sentence

A workspace types its charity or company number and gets ~24 cited facts about
itself back from the public register; those facts then ground the drafting
sections that are *about the organisation*, and answer the identity questions on
a funder's form with no model call at all.

### Why it was built

`docs/claims-register-brief.md` had sat at "proposed, not approved" since 11
Aug. The user identified auto-populating organisation facts as the product's
key differentiator and its adoption lever — nobody should face a blank form of
fifty fields. Measured gap before the work: the product stored **one**
organisational fact (`tenants.name`), named 31 more across seed fixtures and
prompt skeletons, and grounded **none**. The four drafting sections about the
applicant organisation had no `uses_vault`, no data table and no pack field
behind them.

### Four commits, branch `claims-register` off `main`, all green

| Commit | What |
|---|---|
| `cef54ce` | Migration **0016** (`ref_claim_kinds`, `claims`, `claim_revisions` + RLS), claim-kind fixture + seeder, `app/claims/` (schemas, three register clients, service), `/api/v1/claims` + three import routes, `/app/claims`, settings section, isolation coverage |
| `9fea88c` | `Section.uses_claims`, `<organisation-claims>` block, `claims`/`claim_excerpts` on `DraftPackBase`, excerpt merge in the engine, stale-claim warning on page one |
| `be4e8e4` | `worker/drafting/prefill.py`, partition before `plan_calls`, `AnswerOut.origin`/`claim_ids`, "From your register" stamps |
| `0d85908` | Migration **0017** (`usage_events.kind = 'extract'`), `worker/claims/extract.py` + `harvest.py`, ingest hook, submit trigger, `disown_claims` |

Suite counts after: **api 331, worker 182, web 63**, plus web
lint/typecheck/build. Rulings in `docs/groundwork/ASSUMPTIONS.md` **#30–#43**.

### The five design rulings not to relitigate

1. **Claims are typed** — `kind` from a seeded catalogue, plus a machine `value`
   and a human `statement`. Free prose cannot be matched to a register field or
   a funder's question, and matching is the whole feature (#31).
2. **`kind` is validated in the router, never by a check constraint** — so a new
   fact type is a fixture row, and a retired one leaves its claims readable
   instead of breaking the register (#31).
3. **Identity is `(tenant_id, kind, subject, period)`**, and only *confirmed*
   rows are unique. A proposal contradicting a confirmed claim is how a changed
   figure surfaces, not a collision (#32).
4. **Nothing is asserted without a person.** Every import, extraction and
   harvest writes `proposed`. Confirming is the separate act that supersedes.
5. **Trustee/director data is name, role and appointment date only** — never the
   partial DOB, nationality and occupation the registers also return (#35).

### Three traps that were found and fixed (do not reintroduce)

- **The excerpt merge must sit outside the `if queries:` branch** in
  `engine.run_draft`. `retrieve_excerpts` *assigns* `pack.excerpts` and only
  runs when there is something to retrieve, so merging inside it silently drops
  every claim citation for any kind with no vault retrieval.
- **`plan_calls` must solo a `uses_claims` section**, as it already did for
  `uses_vault`. The batched prompt carries only shared project data, so a
  batched form question would answer "who are you" from nothing (#37).
- **Tier-A pre-fill is gated on the size of the funder's box** (120 chars), not
  merely on "does the answer fit". A 750-character prose question matched a
  one-line charity number, fit the box, passed every other check and answered a
  different question from the one asked (#36).

### Jurisdictions — verified 12 Aug 2026

Companies House, Charity Commission (England & Wales) and **OSCR (Scotland)**
are all live and all free, all under the Open Government Licence. Scotland was
added because the user named it critical, and it turned out to be the *richest*
of the three: OSCR's annual return carries a multi-year finance series (which is
what the `period` discriminator is for) and staff numbers, which no other UK
register publishes.

**Northern Ireland (CCNI) is deliberately not built** — no per-charity API, only
a CSV export, so it needs an operator-refreshed snapshot rather than a live
lookup. ~half a day. The UI says so rather than failing.

### Outstanding, and owned by the user

1. **Three API keys.** Companies House and the Charity Commission are self-serve
   and instant. **OSCR is issued on an approval request** and has lead time —
   this is the one dependency outside our control. Until it lands, the Scottish
   route 503s honestly and a Scottish charitable *company* can still use the
   Companies House route (its directors are its trustees; a SCIO has no such
   fallback).
2. **Confirm OSCR returns trustee names in the API payload.** The API predates
   the 9 Mar 2026 register change that published them. The client already treats
   trustees as an optional block; do not promise Scottish trustee auto-fill
   until a live response is checked.

### Next work: two follow-ups, planned but NOT built

Both are specified in **`docs/claims-register-brief.md` §14** — read it before
starting either.

- **§14.1 Surfacing overdue claims regularly. Step 1 is now built** — see §6l
  below. Steps 2 and 3 are not: an arq `cron_jobs` sweep writing
  `claims.review_due` to `audit_log` (note `FEED_PATTERNS` in `app/modules.py`
  must gain `claims.*` or the row is written and never shown), and email only if
  the first two are not enough. Re-verified 12 Aug 2026: still no scheduler and
  no email transport anywhere in the codebase, so neither is a small change.
- **§14.2 Telling people when a departing member's claims are released — now
  built.** See §6m below, and ASSUMPTIONS #45 for the owner question and how it
  was settled (no `owner_lost_at`).

---

## 6l. The register announces itself — §14.1 step 1 (12 August 2026)

Branch `claims-summary-badge` off `main`, one commit, green: **api 332, worker
182, web 69**, plus web lint/typecheck/build. Ruling: ASSUMPTIONS **#44**.

**The gap it closes.** A claim that had gone off was visible in exactly two
places, both of which needed somebody to already be looking: the register
screen, and page one of a draft leaning on it. A fact only gets updated if
somebody is told *before* they need it.

**What was built.** `GET /claims/summary` (member-level, one round trip,
counted in Postgres over `claims_review_idx` / `claims_tenant_status_idx`) →
`{needs_attention, stale, expired, proposals}`. Carried on the workspace
context beside projects and conversations, so it joins the tab-focus refetch.
Shown as a badge on the sidebar's "Your organisation" item, and refreshed by
`/app/claims` after every confirm, reject, check and import.

**Four decisions worth keeping:**

1. **Four numbers, not the brief's two.** `stale` and `expired` break
   `needs_attention` down (a claim can be both, so they do not sum). Two
   numbers cannot name *which* problem somebody has, and lapsed insurance
   sends them somewhere different from an overdue review.
2. **The badge counts `needs_attention + proposals`** — everything waiting on a
   person — but is warn-coloured only when `needs_attention > 0`. A pile of
   proposals is an opportunity, not a fault.
3. **The summary's predicates are `_row_out`'s two lines.** Keep them
   identical: a badge that disagrees with the screen it links to is worse than
   no badge. The API test asserts the two agree, on purpose.
4. **A failed summary fetch raises nothing** — the badge hides. It is a number
   on a nav item; a workspace-wide error banner over it would be absurd.

**One trap, the same family as the two in §6k:** `/claims/summary` must be
declared **before** `/claims/{claim_id}`, exactly as `/claims/kinds` is, or the
literal path is parsed as a claim id and 422s. The isolation half of the test
also covers it.

---

## 6m. Facts have owners now — §14.2 (12 August 2026)

Same branch `claims-summary-badge`, second commit, green: **api 334, web 82**.
Ruling: ASSUMPTIONS **#45**.

**Two findings before any code, and they changed the shape:**

1. **Ownership was unreachable from the UI.** `owner_membership_id` was settable
   only over the API and nothing in `apps/web` ever sent it — so every claim was
   unowned, and the brief's "unowned filter" would have matched everything.
2. **An owner could not be cleared.** `update_claim` tested
   `if body.owner_membership_id is not None`, so null read as "unchanged". The
   only owned→unowned path in the system was removing the person.

**The owner question, settled: no `owner_lost_at` column.** Finding 2 makes it
cheap, so cost is not the reason — meaning is. A claim that lost its owner is
not a fact that has gone off; its content is still true. It cannot join
`needs_attention` without wrecking a count that means "this may be false", and a
permanent number of its own is the badge nobody reads (#43). One person told at
the one moment they can act is a response body, not a column. Reversible:
`audit_log` holds every `member.remove` with its count, so the column can be
added and backfilled if a pilot user asks to be chased.

**What shipped:** an owner picker on every confirmed row; an opt-in
`?owner=none` view (a URL, because Settings links straight to it); the removal
notice naming the count with a link to reassign.

**Three things not to undo:**

- **`ClaimPatch.owner_membership_id` is the only field on any patch model in the
  codebase where an explicit null means "clear it"** — `update_claim` reads
  `model_fields_set` for that one field. Reverting it to the `is not None` test
  every neighbouring field uses silently removes the ability to hand a fact
  back, and no type error will tell you.
- **`DELETE /members/{membership_id}` answers 200 with `{claims_disowned: N}`**,
  not 204. One test asserted the 204 and was updated.
- **`_check_owned_membership`** — the fourth instance of the same hole as
  `_check_owned_document`: Postgres validates foreign keys with RLS bypassed, so
  the constraint alone accepts another workspace's membership id. Any future FK
  on a tenant table needs the same check, and the test for it is
  `test_a_fact_cannot_be_made_another_workspaces_problem`.

**Deliberately not done:** `member.*` is still not in `FEED_PATTERNS`. Putting
membership churn in every tenant's activity feed is a platform decision about
what that feed is for, and neither thing §14.2 asked for runs through it.

---

## 6n. The evaluation gaps, and what the live registers actually return (14 August 2026)

One commit, `82f1998`, green. Rulings: ASSUMPTIONS **#46–#50**.

**Where the gaps came from.** Walking the workspace as a Grantwork evaluator
would, five things the API could already do had no way in from the UI, and two
register clients were written against documentation rather than a live
response.

**The five UI gaps closed:** an "Add a fact" panel on `/app/claims` for
anything a public register does not publish (confirmed on arrival — #46);
bid-pack upload on the application's Bid Pack tab; editing a funder; editing an
application; and editing a tenant question set's questions, name, funder and
URL.

**The register findings are the durable part**, and both were only findable
against a live key:

- **Charity Commission V2 is the contract, not the portal's documentation
  (#49).** The documented `charitytrustees/{number}/{suffix}` operation 404s;
  trustee names ride on `allcharitydetailsV2.trustee_names`. Field names had
  drifted from what our fixtures encoded — `reg_status` is `R`/`RM`, not
  "Registered"/"Removed" — and objects and activities live on two further
  best-effort calls (`charitygoverningdocument`, `charityoverview`) that must
  not fail an import which already has a register entry.
- **OSCR still does not publish trustee names through its API (#50)**, even
  though the web register does. Checked against a real charity with nine
  trustees listed publicly. Do not scrape the register; a Scottish charitable
  company can import Companies House for its directors. The live payload is
  camelCase, `annualreturns` returns a JSON array encoded as a JSON *string*,
  and that call keys on a UUID `id`, not the `SCxxxxxx` number.

**Two contract changes worth knowing.** `ApplicationOut.harvest_queued` is set
only by `POST .../status` to `submitted`, and is null on every other read — the
submit-time harvest stays fire-and-forget (it must never fail the act of
recording a submission) but is no longer *silent*, so the room can send someone
to type the facts by hand when the queue is down (#48). And editing a question
set's questions returns it to unverified, because the tick was against a
different form; label-only edits do not (#47).

**The three register keys now have documented slots** in `apps/api/.env.example`
and `infra/.env.staging.example`. Empty key = that import route 503s. OSCR is
still the one with an approval lead time.

---

## 6o. Core projects get a plan (14 August 2026)

Three commits, `a363c8a` → `3c62879` → `438cad5`, green. Ruling: ASSUMPTIONS
**#51**.

**What it is.** A sidebar project can now start as either a documents-only
folder (the historic vault/chat container) or a thin plan: `POST /projects`
takes `kind: blank | planned`, and `planned` sets `projects.has_plan`, seeds a
primary "Project brief" markdown document so chat has something to ground on
from day one, and accepts an opening checklist. Migrations **0018**
(`project_plans`) and **0019** (`plan_task_details`). Nested CRUD at
`/projects/{id}/plan-tasks`, plus `POST /projects/{id}/plan` to add a plan to a
project that started as a folder.

**Why it is not Groundwork.** Groundwork's `proj_tasks` requires a CLH
`stage_key` and the `projects` feature flag, so folding general work into that
spine would either invent a fake stage or hide tasks from every tenant that
never bought development projects. `/app/projects/*` stays the development
room. Assignees are workspace members — not CRM contacts, not free-text owner
names — and a cross-tenant membership id 404s in app code, because foreign-key
checks bypass RLS (the same hole as `_check_owned_document`, now the fifth
instance).

**The trap `438cad5` fixes.** "Add a plan" was wired to `PATCH /projects/{id}`,
which is rename/archive only and silently drops unknown fields — so the button
returned `no_changes` and did nothing. Enabling a plan is a `POST` to
`/projects/{id}/plan`, and it is idempotent.

**Deliberately narrow:** `project_tasks.details` is a short note on the row, not
comments and not Groundwork tickets; the UI is a two-state checklist, and while
`doing` survives in the check constraint it is not a third column.

---

## 6p. Test-findings remediation sweep (15 August 2026)

Seven commits, `0b7546e` → `a474c92`, all green, from a 13-item external
test/UX report — every finding re-verified against the code first. Plan file:
`~/.claude/plans/i-ve-run-some-tests-sprightly-candle.md`.

| Commit | What |
|---|---|
| `0b7546e` | Decimal-as-string money (Pydantic v2 serialises `Decimal` → JSON string; only `grants/schemas.py` uses Decimal). `fmtMoney`/`achievedShare`/`fmtNum` coerce; grants "Secured" tile no longer string-concatenates; **`components/toast.tsx`** (ToastProvider/useToast) mounted in the app layout |
| `225cae6` | Claims: scroll wrapper (page must own scrolling — shell is `h-screen` + `min-h-0 flex-1`), dates in words in **three statement renderers that must not drift** (web `formatClaimValue`, api `format_value`, worker `render_statement` — "15 September 2026"), two-step Remove ("Remove for good"/"Keep") + undo toast, add-panel inline errors + success toast |
| `f92af99` | Citation regex hardening: uppercase `[C:`, escaped `\[c:…\]`, punctuation in bracket, dressed-up `[Ref c:…]` (prose-protected when nothing resolves). Three synced copies: api `conversations.py`, worker `assemble.py`, web `markdown.tsx` |
| `1531705` | `.stamp` contrast (`text-accent` → `text-accent-deep` on the tint), project-tab empty states, zero-variance neutral, versions-0 dash, forms cards expandable read-only (`QuestionDisplay`), usage-page alias labels, "Drafted from your whole vault" footer, Re-index→Refresh, "register" reserved for *public* registers |
| `17187ff` | Chat exports: Save to Vault (client-only, reuses the 3-call upload) + Download as PDF via **migration 0024 `conversation_export_jobs`** (RLS + isolation tests), `render_answer_pdf` worker task (markdown-it-py, MIT; WeasyPrint) |
| `3416460` | `done` event `coverage: "ok"|"none"|null`; `scope_used` suppressed when nothing cited (was claiming "whole vault" on zero-chunk answers). Recovery actions on `coverage:none` (`/app?view=vault&upload=1`, `/app/claims?add=1&topic=…`); suggestion chips built from real indexed doc titles — chips stay vault-groundable only, **chat does not read claims** |
| `a474c92` | **Playwright greenfield**: config on port 3100, fully mocked backend, `E2E_AUTH_BYPASS=1` env check in `proxy.ts` (set only by playwright.config.ts, never a real deployment); keyboard-nav spec proves no sidebar focus trap; `web-e2e` CI job |

**Findings that were already fixed / wrong:** chat already swaps stream text for
the resolved message on `done`; add-panel already guarded empty value/subject;
`_resolve_citations` handles plain `[c:<uuid>]` fine (the four adjacent shapes
above were the real bugs); BudgetTab already limited danger to overspend.

**Still manual:** axe re-run on `/app?view=vault` (contrast fix is
deterministic: `#98401f` on `#f7e8e0` ≈ 6.7:1) — needs the full dev stack,
which was not running this session.

---

## 6q. Public marketing website — built and verified (16 August 2026)

Committed on `main` as `de08412` (site + the PRD it implements) plus
follow-ups through `dc54cfd`, all **pushed**, and **live in Vercel
production** at https://ops-engine-staging-web.vercel.app — see "Deployed"
below. The rest of `output/marketing/` (one-pager PDFs, generator script,
messaging source) is deliberately left untracked — only `website-prd.md` was
committed, because this file cites it.

### What it is

The Flowgrid OS public marketing site, built into the existing Next.js app per
`output/marketing/website-prd.md` (PRD v1.0, 16 Aug — routes, conversion
model, copy spines, accessibility and performance budgets all come from it).
Delivery slices 1–3 plus the lead endpoint are done; analytics, scheduler/CRM
choice and legal sign-off are deliberately not.

**Design ruling:** the PRD says "Hearth palette" (§9, §13) but the user
explicitly supplied the **Huddle** style reference and said to follow it — and
the app itself had already moved to Huddle (`241e4cb`, after §6p; `c91699d`
was a Clearbit-inspired intermediate the same day). The marketing site uses
the Huddle tokens already in `apps/web/app/globals.css` (paper-white canvas,
Ink Black, hairlines, no shadows, burnt-amber `--accent` primary CTA,
deep-violet interactive, pastel status taxonomy). Treat the PRD's "Hearth"
wording as stale, not as an instruction.

### Structure

- **`app/(marketing)/`** route group. `app/page.tsx` (the old
  `getUser()` → redirect to `/app` or `/login`) is **deleted**; `/` is now the
  public homepage. `proxy.ts` needed **no change** — its matcher was already
  `/app/:path*`, so it never touched `/`. Authed users reach the app via the
  header's quiet "Sign in" link (PRD §3); the header does **no** server auth
  check, deliberately, so every marketing page stays statically prerendered.
- Routes (all static): `/`, `/platform`, `/solutions/groundwork`,
  `/solutions/grantwork`, `/security-and-data`, `/about`, `/contact`, plus
  `/privacy` / `/terms` / `/cookies` (drafts, each page says "pending legal
  review", `robots: noindex`). Also `app/sitemap.ts`, `app/robots.ts`
  (disallows `/app/`, `/admin/`, `/api/`) and a styled root `app/not-found.tsx`.
- Shared pieces in the group: `ui.tsx` (Kicker, Section, CTA class strings,
  TagPill, `StatusCard` with the pastel taxonomy + a `neutral`/bone tone),
  `site-header.tsx` (client; mobile menu with focus trap + Escape per PRD §5),
  `site-footer.tsx`, `hero-visual.tsx` (CSS-composed "representative product
  view — example data": cited answer, source excerpt, confirmed claim, PDF
  export cue — no fabricated customer data), `legal.tsx`.
- **Both solution pages share `solutions/solution-page.tsx`**, the PRD §6
  eight-step decision path, fed by a typed `SolutionContent` object per page —
  this is the PRD §8 "typed content files" requirement; capability claims live
  in those objects, keep them reviewable and true.
- Nav divergence from PRD §5: flat links (Platform, Groundwork, Grantwork,
  Security & data, About) instead of a "Solutions" dropdown — simpler and
  keyboard-friendly. Tenderhouse/Assurance are **not** mentioned anywhere
  (PRD §5 forbids "coming soon" without an owner).

### Lead flow — the repo's first Next route handler

- `app/api/leads/route.ts` (`POST`, node runtime): server-side validation
  (kind `demo|pilot`, email regex, workflow/team-size allowlists, length
  caps), honeypot `website` field answered with a fake 202, per-IP rate limit
  (5/min), `Idempotency-Key` dedupe (1h TTL), consent version constant
  `2026-08-16`. Free text is capped at 500 chars; nothing is sent to
  analytics (there is no analytics).
- `lib/leads.ts` — `LeadAdapter` interface; the default adapter POSTs to
  **`LEAD_WEBHOOK_URL`** or, unset, logs to the server with the email masked.
  Swap the adapter when the CRM/email destination is chosen; the route
  handler shouldn't change.
- Forms: `contact/demo-form.tsx` (PRD §7's exact field set, inline
  errors, success state, mailto fallback) and `pilot-form.tsx` (email +
  workflow, inline on the homepage). Both use `lead-client.ts::submitLead`,
  which attaches sourcePage + UTM params and a per-mount `crypto.randomUUID()`
  idempotency key.
- ⚠️ **The rate limiter and idempotency store are in-memory Maps.** Fine on a
  single long-lived instance; the web app deploys to **Vercel**
  (`docs/staging-deploy-checklist.md`), where serverless instances make them
  best-effort. Move to Redis if lead abuse ever matters; the handler comment
  says the same.

### Verification (all green at handoff)

`pnpm lint`, `pnpm typecheck`, `pnpm build` (29 routes, all public pages
static), `pnpm test` (103 unit tests — none touch the marketing pages;
coverage there is zero). Visual QA done via Playwright screenshots against
the running dev server (:3000): `/`, `/contact`, `/solutions/groundwork`,
and the 375px mobile menu — all render correctly. Note: deleting
`app/page.tsx` leaves stale `.next/types` that fail `tsc` until the next
`pnpm build` regenerates them — build first if typecheck fails oddly.

### Deployed (16 August 2026, same day)

Live in **Vercel production**, project `ops-engine-staging-web`, deployment
`dpl_2RssuSx2XEL5BqtA9uaTFJeAGRVp` from `dc54cfd`, aliased to
https://ops-engine-staging-web.vercel.app. Smoke-checked: `/`, `/contact`,
`/solutions/groundwork`, `/robots.txt` all 200 with correct titles; `/app`
still 307s unauthenticated visitors to `/login`; a test POST to `/api/leads`
returned `{"ok":true}` (Idempotency-Key `deploy-check-dc54cfd`,
`deploy-check@flowgridos.co.uk` — ignore it if it turns up in lead logs).

- **Deploy command gotcha, now in the checklist** (`ef0e599`): the Vercel
  project's Root Directory is `apps/web/`, so `pnpm dlx vercel@latest --prod`
  must run from the **repo root** — from `apps/web` it fails. `.vercel/` links
  exist at both root and `apps/web`, both gitignored. The CLI is not installed
  globally.
- **Leads log to the server, deliberately** (founder decision, 16 Aug):
  `LEAD_WEBHOOK_URL` is unset and `dc54cfd` changed the fallback to log the
  **complete** lead (email unmasked) — with no webhook the log line is the
  only record, and a masked email meant an uncontactable lead. Consequences:
  personal data sits in Vercel runtime logs (short retention — roughly an
  hour to a day), so check `vercel logs` / dashboard Logs (filter `[leads]`)
  for real submissions, and set `LEAD_WEBHOOK_URL` before relying on the form
  for real volume — setting it switches the logging path off automatically.
- **`NEXT_PUBLIC_SITE_URL` is also unset** — canonical/sitemap/OG URLs point
  at `https://flowgridos.co.uk` (the intended final domain), not the staging
  alias. Fine until the domain cutover; set it only if that ever matters.

### Open items, in order

1. **Choose the lead destination** and set `LEAD_WEBHOOK_URL` in Vercel —
   until then leads live only in short-retention runtime logs (see above).
2. PRD "remaining inputs" still owed by the user: lead-response owner,
   scheduler/CRM/analytics choices, approved legal wording + processor list,
   real product screenshots (the CSS hero mock is a stand-in), and the
   **`hello@flowgridos.co.uk` mailbox** — it appears as the form-failure
   fallback and contact address; confirm it exists before launch.
3. Analytics events (PRD §8) and consent banner: not built, pending the
   consent decision. The cookies page currently truthfully says "no trackers".
4. ~~PRD §11 launch checks~~ — **run 16 Aug against deployment `8d1963b`**
   (after that commit fixed the axe findings: mist-gray-on-white contrast and
   colour-only prose links). Results: Lighthouse mobile `/` 96/100/100/100,
   `/solutions/groundwork` 98/100/100/100, `/solutions/grantwork`
   96/100/100/100 (perf/a11y/BP/SEO); LCP 2.2s, CLS 0 on all three; JS 158KB
   transferred (budget <170KB). Axe WCAG 2.2 AA: **0 violations across all 8
   public pages**. Keyboard journey: skip link first, menu opens/traps/
   Escape-closes with focus return. Metadata/sitemap/robots/canonical/404 all
   verified in production. **Still open from §11:** the human five-second
   exposure test and real-user monitoring. ~~og:image share cards~~ — built
   and deployed later the same day, see below.
5. ~~E2E coverage~~ — `e2e/marketing.spec.ts` written 16 Aug (4 tests):
   homepage public + skip link first tab stop; mobile-menu keyboard journey
   (open, focus trap wrap, Escape returns focus); demo form submits one lead
   with a UUID `Idempotency-Key` and empty honeypot; pilot form fails
   recoverably on a 502 and **retries with the same key**. Local gotcha: the
   §6p webServer (`pnpm dev --port 3100`) cannot start while another dev
   server holds Next 16's per-directory dev lock — run
   `pnpm exec next start --port 3100` against a fresh build instead
   (`reuseExistingServer` picks it up); CI is unaffected.

### Share cards (og:image) — built and live (16 Aug, evening)

`6920cdd`, deployed as `dpl_2g4eigmBMeanXHpS8mzEY8juf11B`. Seven 1200×630
cards generated **at build time** with `next/og` `ImageResponse` — no binary
assets in the repo. `app/(marketing)/og-card.tsx` is the shared renderer
(Huddle system: paper white, bone hairline frame, wordmark, three pastel
tiles, kicker + weight-300 headline, burnt-amber domain pill); Inter is
subset-fetched from Google Fonts **during build**, so `next build` needs
network. One default `opengraph-image.tsx` on the group (homepage + legal
pages inherit it) plus per-page cards for platform, both solutions,
security-and-data, about and contact. Verified live: every public page's
`og:image` tag serves a real PNG (200, ~38–51KB) on the staging host.

**Caveat (same as canonicals):** the `og:image` URLs are absolute against
`metadataBase` = `https://flowgridos.co.uk`, so scrapers of staging links
won't resolve the card until the domain is live — or until
`NEXT_PUBLIC_SITE_URL` is set to the staging URL in Vercel (founder chose to
leave it unset). Both Lighthouse cleanup EPERM errors on Windows
(`chrome-launcher` temp-dir removal) are noise — the report JSON is written
before the failure.

---

## 7. Read first in a new session

**Active work: the marketing site (§6q) is pushed and LIVE in Vercel
production** (https://ops-engine-staging-web.vercel.app, from `dc54cfd`) —
its open items are next (lead destination, analytics/consent, legal
sign-off, launch checks). The other open brief is `docs/claims-register-brief.md`
**§14** — only §14.1 steps 2–3 (the arq cron sweep, then email) remain
unbuilt, and both are blocked on infrastructure that does not exist.

**Suites as of 16 Aug 2026, all green:** api **390**, worker **196**, web
**103** (+1 Playwright e2e).

0. **§6q** if touching the public site, `/` routing, or lead capture — it
   also records why the marketing pages follow Huddle, not the PRD's "Hearth".
1. This file — **§6k** first (the claims register: what was built, the five
   rulings not to relitigate, the three traps not to reintroduce, and what the
   user still owes), then **§6l** (the summary badge) and **§6m** (ownership, and
   the two contract changes in it), then **§6n** (what the live Charity
   Commission and OSCR payloads actually return) and **§6o** (plans on core
   projects). Then **§6j** if touching latency, **§6g** for Grantwork.
2. `docs/claims-register-brief.md` — **§13** for what shipped, **§14** for the
   two proposed follow-ups with their recommended shapes and the decisions to
   settle first.
3. `docs/groundwork/ASSUMPTIONS.md` — **#30–#45** are the claims-register
   rulings, **#46–#50** the evaluation-gap and live-register findings, and
   **#51** core project plans. #36, #37, #43, #44, #45, #49 and #50 each record
   a specific failure and are easy to undo by accident.
4. `CLAUDE.md` (unchanged conventions: RLS with an isolation test per table,
   LiteLLM-only for models, cost telemetry on every LLM call, commit-on-green).
5. `docs/vertical-module-roadmap.md` if the next move is a new module.
   **Tenderhouse is now cheaper than the roadmap assumes** — it was to build its
   own answer library, and the claims register is that spine already built and
   unflagged. `bid_*` questions should *reference* claims via `claim_ids`, not
   be claims (brief §12.5, settled).

Grantwork (§6f, §6g) and the drafting engine (§6i) are background — done.

