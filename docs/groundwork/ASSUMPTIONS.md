# Groundwork Module — Assumptions & divergences log

Per PRD §0.2: where the repo's conventions differ from the spec, the repo wins,
and every divergence is recorded here.

## Recorded at orientation (30 Jul 2026, approved by founder)

1. **Unified project concept.** The core gained a `projects` table (Slice 4.5:
   vault partitioning + chat scoping) after the PRD was written. `proj_projects`
   is therefore a **1:1 extension** of `projects`
   (`id uuid primary key references projects(id) on delete cascade`) rather than
   a standalone table. `name`, `created_by`, `created_at` live on the core row;
   the extension holds the development-specific fields. Groundwork projects
   automatically appear in the core sidebar, partition the vault, and scope chat
   retrieval — the feasibility workflow depends on that scoping.
2. **Route collisions with core.** `/api/v1/projects` (POST + GET) already
   exists in the core (container CRUD). Module routes therefore are:
   - `POST /projects/{id}/setup` — attach the Groundwork extension to an
     existing core project and seed the spine (the UI's "New development
     project" form calls core create + setup in sequence).
   - `GET /projects/portfolio` — the module portfolio list.
   - `GET`/`PATCH /projects/{id}/groundwork` — module detail/update (the core
     owns `PATCH /projects/{id}` for container rename/archive, and wins by
     registration order; discovered in W2).
   - All other PRD routes are `/projects/{id}/…` subresources as specified (no
     collisions).
3. **`usage_events.kind`** is CHECK-constrained in the core schema; migration
   0003 extends it with `draft`.
4. **Vault excerpt format.** Core prompts wrap chunks as
   `[c:<id>] (from "title", p.x)` inside `<vault-excerpts>`, not
   `<vault_chunk id=…>`. Drafting pipelines reuse the core format and its
   citation-resolution rules (unresolvable ids stripped and logged).
5. **RLS pattern.** Core policies use the `app_current_tenant()` helper with
   `for all … using … with check`, not the PRD's literal snippet. Module tables
   follow the core pattern. Reference tables get a select-only policy
   (`using (true)`) — with no write policies, the non-owner runtime role cannot
   write them; only the owner (migrations/seed) can.
6. **Frontend client.** No OpenAPI→TS generation exists (`packages/shared` is a
   stub); the web app uses a hand-rolled `apps/web/lib/api.ts`. Module UI
   follows that.
7. **Core prerequisite caveats.** Stripe billing is not built (re-sequenced
   after this module; pilot invoiced manually per PRD §6 — no impact).
   Production R2 is not yet provisioned (dev uses MinIO) — required before the
   W4 staging/pilot step.
8. **Worker upload helper.** ~~The worker currently only downloads from
   storage~~ — added in W3 (`worker/storage.py: upload_bytes`).

## Recorded during W3 (31 Jul 2026)

9. **Draft instance registry rows.** `proj_documents` has
   `unique (project_id, doc_type_key)`, so the PRD's per-instance rows for
   monthly reports and funding bids get suffixed keys
   (`monthly_report_2026_07`, `funding_bid_<first-8-of-source-id>`) with the
   month / source name in the title. The seeded generic rows stay as the
   "Draft with AI" launchers (`ai_draftable=true`); instance rows are created
   `ai_draftable=false`. Feasibility studies version onto their single seeded
   row.
10. **Draft storage keys.** PRD §5 says `tenants/{tenant_id}/...`; the repo's
    established convention has no `tenants/` prefix, so drafts land at
    `{tenant_id}/projects/{project_id}/drafts/{job_id}.docx`.
11. **Citation rendering.** python-docx has no first-class footnote API;
    `[c:<id>]` markers render as numbered inline references `[n]` with a
    References section (title + pages) before the Data sources appendix.
    Unresolvable markers are stripped and counted in the audit meta, per the
    PRD's no-fake-references rule.
12. **Draft job polling.** No arq result polling (worker keeps
    `keep_result=0`); jobs are tracked in a tenth tenant table
    `proj_draft_jobs` (migration 0005) written by API + worker, so polling
    inherits tenant isolation from RLS.
13. **Worker retrieval/gather duplication.** `app/retrieval.py` is not
    importable from the worker, so `worker/drafts/retrieval.py` mirrors its
    SQL and fusion constants (as `worker/embed.py` mirrors the LiteLLM
    client) — keep them in step. The worker's DB-touching drafts modules stay
    asyncpg+pydantic-only so the **API** test suite imports and exercises
    them against its migrated database (worker CI has no Postgres).

## Recorded during UI overhaul (1 Aug 2026)

14. **Task modes diverge from spec §10.** The composer exposes `task_kind`
    (chat/analyse/report/financial) plus two additions the Phase-1 spec parks
    as P2 non-goals, added at founder request:
    - **`slides`** — routes to `drafter` with a structured-outline system
      prompt (`app/prompts.py`). Outlines export to native PPTX via
      `POST …/messages/{id}/slides` (`app/slides.py`, python-pptx, MIT):
      synchronous render — deterministic and sub-second, so deliberately
      *not* on the draft-job queue; deck is themed from `brand.accent` +
      logo and stored at `{tenant_id}/slides/{message_id}.pptx`. Tenants
      may upload a corporate `.pptx` master (`brand.slides_template_key`,
      Settings → Brand); exports then build on its layouts/placeholders,
      with silent fallback to the generated theme when the template is
      unreadable (presigned PUTs mean the API can't validate at upload).
      Slides whose bullets all parse as "Label: number" (≥3 rows, not
      year-only timelines) render as native column charts instead of
      lists — theme-coloured on templates, accent-coloured otherwise.
    - **`research`** — Exa web search injected as pseudo-vault excerpts with
      the core citation format (item 4 unchanged), so web sources ride the
      existing evidence-panel pipeline with a `url`/`source_type` extension
      on the citation payload. Gated per tenant via
      `tenants.features->>'web_search'` (default **off**): research prompts
      leave the trust boundary to Exa, whose retention terms are a per-tenant
      data-processing decision. `EXA_API_KEY` unset ⇒ 503, matching the
      LiteLLM/storage disabled-service convention. Search calls are metered
      as `usage_events.kind='search'` (migration 0007 widens the CHECK).
    - **Image creation is deferred** — no image model behind the LiteLLM
      gateway.
15. **Development projects presentation.** The sidebar now lists Groundwork
    projects under their own "Development projects" heading and excludes them
    from the core "Projects" list (`GET /projects` gained `is_development`
    via a `proj_projects` left join). Item 1's substance is unchanged: they
    remain core `projects` rows and still scope chat/vault.
16. **Member emails.** `memberships.email` (migration 0007) caches the JWT
    email claim for the settings members list — the app DB cannot reach
    Supabase's `auth.users`. Written at bootstrap/invite-accept, self-healed
    on tenant resolution; nullable end-to-end.
17. **Hearth UI system: chrome is no longer tenant-themed** (1 Aug 2026,
    diverges from core spec §7 "brand: logo + colours → CSS variables" and
    the original Slice 5 white-label hook). The app chrome now uses the
    fixed Hearth palette (`docs/concept-01-hearth-warm-approachable.html`;
    terracotta #B14E2E on cream, Fraunces + Plus Jakarta Sans, sage green
    scoped to grounded/trust states). The tenant `brand.accent` colour is
    applied only to exported artefacts (slide decks, health-card PDFs) and
    the tenant logo still shows in the sidebar. Rationale: Hearth's
    AA-verified pairings hold only for its own palette; user decision on
    1 Aug 2026 chose "Hearth for platform, accent only in content" over
    per-tenant chrome tinting. Legacy token names (`paper`, `surface`,
    `line`, `ink-muted`, `ink-faint`, `accent-soft`) alias the Hearth
    palette in `globals.css`. The evidence side panel was replaced by
    inline source-passage cards in answers; chat pin/rename was
    deliberately not built.

## Recorded during team-visibility work (2 Aug 2026)

18. **Chat visibility model** (2 Aug 2026, founder decision; the Phase-1
    spec doesn't address intra-tenant chat privacy). Conversations are
    **private to their owner by default — including from admins/owners**:
    the previous elevated-role read override in
    `routers/conversations.py::_get_owned_conversation` was removed
    (migration 0008 adds `conversations.visibility`,
    `'private'|'tenant'`). Owners may share a chat with the team
    (`PATCH /conversations/{id}`), which grants every tenant member
    **read-only** access — list/⌘K/messages, but not post, delete,
    re-share or pptx export (messages carry no per-author attribution, so
    collaborative shared chats are deliberately out of scope). Share and
    unshare are audited (`conversation.share`/`.unshare`) with the chat
    title in `meta` — the owner is knowingly publishing it. Everything
    else (vault, projects, Groundwork) stays tenant-visible; the model is
    "chats personal unless shared, all else shared". A tenant-wide
    activity feed (`GET /activity`) exposes a curated **allowlist** of
    audit actions so private-chat events can never surface.

## Recorded during CRM work (2 Aug 2026)

19. **CRM contacts vs `proj_stakeholders`** (2 Aug 2026, founder-approved
    plan). The CRM module (migration 0009: `crm_companies`,
    `crm_contacts`, `crm_contact_projects`; routes `/contacts`,
    `/companies` behind `tenants.features->>'contacts'`) is a
    tenant-wide contact book and deliberately does **not** absorb or link
    to the project-scoped `proj_stakeholders` table — the overlap is
    acknowledged and unification deferred (it would need a data migration
    plus Groundwork UI changes). Contact↔project association is a join
    table against the **core** `projects` table (not `proj_projects`),
    chosen over a `uuid[]` column so deleted projects cascade instead of
    leaving dangling ids. Per-tenant unique `lower(email)` on contacts is
    the dedupe anchor (409 `duplicate_email`); companies are first-class
    with the structured address, contacts carry only a free-text one.
    Because FK checks bypass RLS, cross-tenant `company_id`/`project_id`
    references are rejected by RLS-scoped existence checks in the
    routers, covered by `tests/test_crm.py`.
