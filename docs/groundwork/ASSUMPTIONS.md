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

## Recorded during vertical-module research (2 Aug 2026)

20. **Module schemas live in `app/<mod>/schemas.py`, not core
    `app/schemas.py`.** Groundwork currently splits them — setup and
    portfolio models sit in the core `app/schemas.py` (`GroundworkSetup`,
    `PortfolioRow`, `RagOut`, …) while room models sit in
    `app/groundwork/schemas.py`. That split was incidental, not
    designed. The rule going forward: **all module Pydantic models
    belong in the module's own `schemas.py`**; core `app/schemas.py`
    holds only core-surface models. Groundwork's existing split is left
    in place (moving it churns imports across 13 routers for no
    behavioural gain) but is not a precedent — new modules must not
    copy it. Recorded before module #3 so the ruling exists ahead of the
    decision rather than after it.

21. **Module registration is a manifest, not scattered constants**
    (3 Aug 2026, implemented). Adding a feature flag used to mean
    hand-editing six independent places: `FEATURE_FLAGS`
    (`app/schemas.py`), `apps/web/lib/admin.ts`, a copy-pasted
    `require_<flag>()` gate, the sidebar JSX, `ALLOWED_ACTIONS`
    (`app/routers/activity.py`) and `TENANT_TABLES`
    (`tests/test_isolation.py`). Nothing enforced consistency, and the
    RLS block in migrations was likewise copy-pasted — the one place
    where a slip fails silently rather than turning a test red.
    `app/modules.py` now holds one `Module(flag, label, tables,
    feed_prefix)` per entitlement; `FEATURE_FLAGS`, the
    `make_feature_gate()` dependencies and the feed's namespace patterns
    derive from it. `require_projects` / `require_contacts` are kept as
    aliases at their old import paths, so no router changed.
    `migrations/rls.py::enable_tenant_rls()` is the blessed policy
    helper — migrations-local, not imported from `app`, so schema
    history cannot shift when application code is refactored; 0003,
    0005 and 0009 now call it and emit byte-identical SQL. The real
    enforcement is `test_every_module_table_has_rls`, which asserts
    every declared table has RLS plus a `tenant_isolation` policy with
    both USING and WITH CHECK keyed on `app_current_tenant()`.
    `TENANT_TABLES` in the isolation suite stays a hand-written list —
    it drives per-table row assertions that need the `two_tenants`
    fixture to have seeded rows, which module tables do not.
    `web_search` is declared as a module with no tables: it is
    cross-cutting chat enrichment (400 `feature_disabled`, not a 404
    router) but is still an entitlement the operator console must offer.

22. **Feature flags have an update path** (3 Aug 2026, implemented).
    `POST /admin/tenants` was the only write path for
    `tenants.features` (`PATCH /tenants/me` takes `name` and `brand`
    only), so enabling a module on a live tenant needed raw SQL — which
    made modules-as-upsell, the packaging lever for the plan tiers,
    inoperable by ops. `PATCH /admin/tenants/{id}/features` is platform
    admin only and audited as `tenant.features_change`. Two rulings
    worth keeping: it **merges** rather than replaces, so naming one
    module cannot silently drop another, and withdrawal is
    `{"flag": false}` (the gates test `= 'true'`) which hides the module
    without deleting its rows. It runs in `db.tenant_tx()` scoped to the
    target tenant — as tenant creation does — because the `tenant_update`
    policy accepts `id = app_current_tenant()`; **`db.platform_tx()` was
    deliberately not used**, keeping that fenced connection read-only as
    its docstring promises. `tenant.features_change` was added to the
    activity feed's `ALLOWED_ACTIONS`: a module appearing is
    team-relevant and the meta is flag names only.

## Recorded during Grantwork build (3 Aug 2026)

23. **Grantwork sits beside Groundwork, not inside it** (3 Aug 2026,
    founder decision — the ruling `docs/modules/grantwork-prd.md` §4
    requires before build, and the first real cross-module design
    question the codebase has faced). Three parts:

    - **Two funding surfaces, deliberately.** A tenant with both
      `projects` and `grants` enabled sees Groundwork's funding tab
      (the funding *stack* for one development project: sources,
      drawdowns, match) and Grantwork's application portfolio (the
      tenant-wide pipeline of bids and the multi-year reporting
      obligations they create) as separate surfaces. Grantwork does
      **not** absorb `proj_funding_sources`. Rationale: subsuming it
      would mean editing Groundwork routes and UI plus a data
      migration, breaking the additive-only rule that makes a module
      cheap; the two answer different questions and only look alike
      from a distance.
    - **`grant_applications.project_id` is a nullable soft link** to
      the **core** `projects` row (not `proj_projects`), matching the
      CRM's choice in #19. That is what stops the acknowledged overlap
      from being unmanaged: a CLT's NLHF bid and the development
      project it funds can be joined without either module owning the
      other, and the link gives Grantwork drafts vault scope-weighting
      for free (`project_scope_weights` already takes a project id).
    - **Applications are standalone rows, not core-project
      extensions** — the opposite of #1's ruling for `proj_projects`.
      A charity runs a rolling portfolio of twenty-plus applications;
      making each a core `projects` row would flood the sidebar and
      split the vault into twenty partitions, defeating the chat
      scoping that extension pattern exists to provide. Groundwork
      projects are few and long-lived; grant applications are many and
      churn.

    Two schema divergences from the PRD's §1 entity list, recorded
    here rather than argued in code: `grant_tasks` is added (the
    seeded library specifies "standard tasks" per application type,
    which the listed entities have nowhere to live) and
    `grant_draft_jobs` is added (the shared drafting engine takes a
    per-module `job_table`, and #12's polling rationale is unchanged).
    Migration 0013 therefore creates 10 tenant tables plus
    `grant_ref_funders` / `grant_ref_templates`, the latter two
    select-only per #5. `grant_ref_funders` extends the
    `proj_ref_programmes` shape with `funder_type`, `deadlines`,
    `typical_award` and `reporting_note` — the last matters most,
    because what a funder demands back is the thing Grantwork
    automates.

24. **Seeded funder-catalogue rows ship unverified and stale** (3 Aug
    2026, Grantwork step 3). `grant_ref_funders` is the first reference
    table whose rows are **external fact about third parties** rather
    than our own product decision. `proj_ref_programmes` had the same
    property and the same `last_verified` / `next_review` contract, but
    the point was never written down: **`last_verified` is only
    meaningful if it records something a person actually did.** Typing a
    recent date into a fixture is not verification, and a catalogue row
    asserting a funder's eligibility criteria is exactly the kind of
    claim a charity would act on.

    So `app/grants/fixtures/funders.json` was compiled from model
    knowledge (training boundary around May 2026, never checked by a
    person) and every one of its 13 rows ships `status='unverified'`
    with `next_review` equal to `last_verified`. That is deliberate, not
    an oversight: it makes both pre-existing safety mechanisms fire on
    day one — the catalogue badges the row (`stale` is derived in
    `routers/grants/funders.py`, never stored) and any draft
    parameterised by it carries the first-page warning block, because
    the drafting engine already warns whenever `status != 'open'`
    (`worker/drafts/context.py::warning_block`). Field text is
    deliberately hedged toward "confirm with the funder" over asserted
    specifics, and every row carries its own provenance in `notes`.

    Two mechanical consequences worth keeping:

    - **The upsert is narrow.** `seed_funder_catalogue()` refreshes
      descriptive columns on conflict but never touches `status`,
      `last_verified` or `next_review`. Correcting seed content is safe;
      silently demoting a row an operator verified is not.
    - **Two tests guard the data file itself**, not just the database:
      one asserts every fixture row ships unverified with
      `next_review == last_verified` and declares its provenance, the
      other asserts re-seeding cannot reset a promoted row. They exist
      because the tempting "fix" for a catalogue full of warnings is to
      edit the dates.

    Promotion is an operator act: check every field against the funder's
    own current guidance, then set `status='open'` and `next_review =
    current_date + 90` in the database. `local_community_foundation` is
    a deliberate placeholder rather than a real programme — a local
    community foundation is often a small charity's best first
    application, so the row exists to prompt the question.

## Recorded during the latency review (4–5 Aug 2026)

25. **`drafter` reaches Groq through OpenRouter, not the Groq provider
    directly** (4 Aug 2026, founder-approved). Spec §4 pins
    `groq/openai/gpt-oss-120b` with `GROQ_API_KEY`; `infra/litellm/config.yaml`
    now uses `openrouter/openai/gpt-oss-120b` with provider order
    `["Groq", "Together", "Nebius"]`, `allow_fallbacks: false` and
    `data_collection: deny`.

    **Why:** Groq's free tier is 200k tokens/day against ~51k per draft, and
    paid upgrades were closed to new accounts. The measured "~3 min/call" was
    rate-limit backoff, not generation — a full draft ran ~33 minutes or died
    on a 429 partway. OpenRouter resells the same Groq capacity with no new
    account, since `OPENROUTER_API_KEY` was already wired for `longdoc`.
    Confirmed live: `case_for_support` 9 calls / 21.3s, `funding_application`
    11 calls / 35.1s, zero 429s.

    **The constraint to preserve:** all three pinned providers bill
    $0.15/$0.60, which is exactly what `ALIAS_PRICES_PER_MTOK` claims `drafter`
    costs in *both* `app/litellm.py` and `worker/drafting/llm.py`. That is why
    this order was chosen over faster options. **Adding a provider without
    checking its rate silently breaks the spec §11 5% reconciliation** —
    Cerebras is ~4x faster but bills $0.35/$0.75, a ~64% understatement per
    draft, and would need both price tables updated first. `allow_fallbacks:
    false` keeps a request on one of the three vetted Western hosts (hard
    constraint 4). `GROQ_API_KEY` stays wired but unused, so reverting is one
    line.

26. **Chat bounds the model's output and thinking, and overrides the gateway
    retry budget per request** (4 Aug 2026). Spec §4 describes one
    `num_retries` for the gateway and says nothing about per-call output
    limits; `app/litellm.py` now sends `max_tokens`, `reasoning_effort: "low"`
    and `x-litellm-num-retries: 1` on chat and query-embedding calls.

    **Why:** every chat alias is a reasoning model that bills thinking against
    `completion_tokens`, and `stream_chat` forwards only `delta.content` — so
    an unbounded think rendered as a spinner on an open, billing connection.
    Chat was 30–40s; it is now under 2s (`ttft_ms` 166–356). The retry
    override is per request rather than per alias because **`drafter` serves
    both surfaces** — analyse/report/slides/research route to it from chat as
    well as from the drafting engine — so there is no alias-level split to
    make. Two retries at a 120s timeout suits the worker, not someone watching
    a spinner.

    Measurement settled two open worries: `reasoning_effort` **is** honoured
    by GLM-4.7-Flash via DeepInfra (no GLM-shaped `chat_template_kwargs`
    workaround is needed — do not add one speculatively), and the gateway adds
    no meaningful overhead (so the key-auth caching idea in
    `docs/performance-review-aug-2026.md` §3.7 is not worth chasing).

27. **`reasoner` runs GLM-5.2 on CoreWeave via OpenRouter, and its price
    table diverges from spec §4** (5 Aug 2026). Spec §4 pins
    `deepinfra/zai-org/GLM-5.2` at $0.93/$3.00; the repo uses
    `openrouter/z-ai/glm-5.2` with provider order `["CoreWeave", "DeepInfra"]`
    and prices it at **$0.76/$2.42** in both `app/litellm.py` and
    `worker/drafting/llm.py`.

    **Why (speed):** the same model, a faster host. One `reasoner` section was
    17.5s of a 35.1s draft while ten `drafter` calls averaged 1.6s. Measured
    over four identical section-shaped calls each: DeepInfra 15.2/30.4/34.8/
    42.5s at 30–74 tok/s, CoreWeave 6.2/7.1/7.5/8.3s at 159–196 tok/s, with
    equal or more prose. ~4x faster and far steadier, with no quality trade,
    because the weights are identical.

    **Why (price):** spec §4's $0.93/$3.00 is ~24% above the live rate, which
    would break the spec's *own* §11 5% reconciliation. CoreWeave ($0.76/
    $2.42) and DeepInfra ($0.75/$2.40) agree within 1%, so one figure is
    correct whichever the order serves. `test_alias_prices_match_the_api_side_
    table` pins the worker's copy — the two tables are separate by
    ASSUMPTIONS #13 and drift silently otherwise.

    **The order is a correctness ranking, not just a speed one.
    DigitalOcean and Novita must never be added to it.** Both ignore
    `reasoning_effort` and returned `finish=length` with **zero prose**,
    spending the entire 4096-token budget thinking — exactly the 3 Aug failure
    (§6h) that filed documents with missing sections. GMICloud honours it but
    spent 2,516 tokens to produce 822 characters. DeepInfra stays as the
    fallback: slow, but proven correct. **Benchmark any new provider for empty
    prose before adding it, not just for speed** — the failure is silent, and
    on this alias it lands in a document a funder reads.
