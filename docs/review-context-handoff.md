# Session Context Handoff

**Project:** Flowgrid OS (codename "Operations Engine" until 2 Aug 2026)
**Handoff date:** 2026-08-04 (**§6h is the latest state**; §1–6g are history,
oldest first)
**Prepared by:** the UI-overhaul session, extended through the 1–4 Aug QA,
rename, module-kit, Grantwork and smoke-test sessions
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

### Open, in priority order

1. **Live confirmation of DRAFT-002** — one monitoring return whose prose no
   longer refers to a financial table. Recipe in §6h; costs Groq quota.
2. **`funding_application` end-to-end** (from §6g item 1) — still owed.
3. **Chat is unmetered when a stream dies** — `app/routers/conversations.py`
   returns from the generator on a stream error before the `usage_events`
   write, and `StreamResult` only gets its numbers from the final usage chunk,
   so there is nothing measured to record. Same constraint-5 class as
   DRAFT-001 but on the busiest surface; the fix means billing an estimate,
   which is a product decision, not a bug fix.
4. **Chat sends no `max_tokens` and no `reasoning_effort`** — `workhorse` is
   GLM-4.7-Flash and a reply that thinks its way through the provider default
   is both expensive and, if it streams nothing, stored as an empty assistant
   message. Drafting bounds both; chat does not.
5. **Ingest is unmetered if the chunk write fails** — embedding is paid for
   before the transaction that records it.
6. **`packages/shared` is a README and nothing else** — no `types.ts`, no
   drift check in CI, no import from `apps/web`, despite CLAUDE.md's layout
   table. Either build it or correct the doc.

## 7. Read first in a new session

**There is no active work brief.** `docs/drafting-engine-brief.md` closed on
4 Aug 2026 with both its items fixed.

1. This file — **§6i** first (what just landed, and the six open items in
   priority order), then **§6g** for where Grantwork stands overall.
2. `docs/groundwork/ASSUMPTIONS.md` (items 20–24 are the newest rulings; #24
   governs the funder catalogue and is easy to break by accident).
3. `CLAUDE.md` (unchanged conventions: RLS, LiteLLM-only, commit-on-green).
4. `docs/vertical-module-roadmap.md` if the next move is a new module rather
   than the open items — Tenderhouse and Assurance are the researched
   candidates (`docs/modules/`).

Grantwork itself (§6f, `docs/modules/grantwork-prd.md`,
`docs/vertical-module-roadmap.md` §1) is background now — all five of its
build steps are done. Its own remaining items are listed at the end of §6g.
