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

    **Order revised 5 Aug 2026 to `["Groq", "Nebius", "Together"]`.** Groq's
    capacity through OpenRouter is intermittent, and the stand-ins are much
    slower — measured the same hour, Groq 337–403 tok/s against Nebius
    113–152 and Together 76–116. Nebius goes first of the two on that
    evidence (four samples each, ranges overlapping slightly). Both bill
    identically, so the swap carries no telemetry consequence.

    **What that means for expectations:** a draft's wall clock is set largely
    by how many calls Groq happens to serve. Five `case_for_support` runs on
    one day, same code and same prompt: **17.8s, 21.3s, 29.0s, 52.3s, 56.4s**.
    The fast ones had Groq serve all nine calls; the slow ones did not. Quote
    drafting as **~18–56s**, never the best figure. Groq's capacity visibly
    recovered within the day, so a slow spell is a window to wait out rather
    than a state to re-tune against.

    **The reorder is inferred, not observed.** It only pays out when Groq is
    unavailable, and all 18 calls across the two runs after deploying it went
    to Groq — Nebius has never actually served a drafting request. What *is*
    observed: under the previous order fall-through landed on **Together at
    position 2**, so the mechanism works and respects order position, and
    Nebius is independently functional (113–152 tok/s offline). Treat it as
    sound but unwitnessed. Confirm by finding `served_by=Nebius` in
    `worker.drafting.latency` — a fast draft showing `served_by=Groq`
    throughout proves only that Groq had capacity.

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

    **`allowed_openai_params: ["reasoning_effort"]` is mandatory on this
    route, and omitting it fails silently.** LiteLLM's own parameter
    validation rejects `reasoning_effort` for `openrouter/z-ai/*` before the
    request leaves the proxy — OpenRouter itself accepts it — and the
    resulting 400 was swallowed whole by the spec §4 `reasoner: [longdoc]`
    fallback. For three drafts every financial section was written by
    **deepseek-v4-flash** and metered at `reasoner` rates, with `succeeded`
    job rows and plausible prose. Nothing looked wrong. **Never "fix" the
    error with `drop_params: true`:** that discards the effort bound instead,
    and an unbounded GLM-5.2 spends its whole budget thinking and returns an
    empty section (§6h).

    Two general lessons, both cheap to re-learn the hard way:

    - **A fallback between models of different capability degrades output
      silently.** It converts a hard 400 into a wrong-model success. This is
      why `worker/drafting/llm.py` logs `served_by` — without it a slow or
      wrong call is unattributable.
    - **Verify a provider change end-to-end, not just at the config.** The
      deployed `config.yaml` was correct, the alias resolved, and drafts
      succeeded — while every reasoner call was going somewhere else entirely.

    **Why (speed):** the same model, a faster host. Measured in production
    once the route actually worked, over two `funding_application` drafts: the
    `reasoner` section fell from **17.5s to 4.07s / 4.18s** (780 and 666
    output tokens, both `served_by=CoreWeave`), taking the draft from **35.1s
    to 25.9s / 24.4s**. That section was 50% of the draft's wall clock and is
    now ~16%, so it is no longer the dominant term.

    Production is *steadier* than the offline benchmark below — 4.0–4.2s
    against 6.2–17.0s — because the real section emits 666–780 output tokens
    where the synthetic prompt forced 1,100–1,900. **Output length, not the
    provider, is what moves this call.** A benchmark that over-generates reads
    as provider variance when it is really prompt shape, which is why the
    offline spread overstated the risk here.

    Offline, across six identical section-shaped calls per provider, CoreWeave
    averaged **9.9s (range 6.2–17.0)** against DeepInfra's **31.8s (range
    12.6–55.4)**. **Read the range, not the mean.** An initial four-run sample
    put CoreWeave at 6.2–8.3s and was written up here as "~4x faster and far
    steadier"; a second sample the same hour returned 13.4–17.0s. Both
    providers vary 3–4x run to run, so expect a distribution shift rather than
    a reliable per-draft saving, and do not re-tune this alias off one sample.

    **Read that range, not the mean.** An initial four-run sample put
    CoreWeave at 6.2–8.3s and was written up here as "~4x faster and far
    steadier"; a second sample the same hour returned 13.4–17.0s. **Both
    providers vary by 3–4x run to run**, and the variance swamps the
    difference on any single call. Expect a *distribution* shift, not a
    reliable per-draft saving, and do not re-tune this alias off one sample
    — that is the mistake this paragraph exists to record.

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

## Recorded during question-set work (11 Aug 2026)

28. **`db.platform_tx()` now writes as well as reads, and that is the only
    way the platform question-set catalogue can be edited.**

    **What the docs said:** `platform_tx` was described as "a read connection
    … used ONLY by the operator console's fleet listing", and
    `admin_update_features` explicitly notes it kept "platform_tx read-only"
    by running in `tenant_tx` instead.

    **What the repo does now:** publishing a workspace's transcribed funder
    form into `ref_question_sets` writes on that connection.

    **Why there is no alternative.** The reference catalogues carry no
    `tenant_id`, so there is nothing for `app_current_tenant()` to match and
    the `tenant_tx` trick that saved `features` cannot work here. Their RLS
    is `for select using (true)` and the runtime role has no write grant at
    all — deliberately, since a tenant able to edit the shared catalogue
    could change what every other workspace tells a funder. The owner role is
    the only one that can, and `platform_tx` behind `require_platform_admin`
    is the sanctioned way to reach it.

    **What keeps it fenced.** The write lives in `app/refdata/promote.py`,
    reachable only from `app/routers/admin.py`; every tenant-facing path
    still reads the catalogue through RLS. `list_platform_sets` exists
    precisely because the console must *not* reuse the tenant-facing lister —
    on the owner connection that would return every workspace's private forms
    as though they were ours, and there is a test for it.

29. **A form is published on two separate confirmations, not one.**

    A workspace confirming a transcribed form against a funder's guidance
    clears the warning *for that workspace*. Publishing it to the catalogue
    clears the warning for everyone, so the operator must also affirm
    (`confirmed_against_source`) that they read it against the funder's own
    form, and the API refuses without it.

    **Why:** ASSUMPTIONS #24 established that seeded rows must ship
    unverified because "verification is an act somebody performs, not a value
    somebody types". Promotion is the door that rule could be walked around —
    an unchecked set becomes everybody's with one click and no fixture in
    sight. Two further gates back it up: the source must be verified and in
    date, and **no question may be missing its limit**. A blank limit is
    honest in a workspace's own copy, where whoever left it blank knows it is
    blank; published, it is a silent gap in a stranger's draft.

30. **The claims register's tables are `claims`, `claim_revisions` and
    `ref_claim_kinds` — not the brief's `claim_*` prefix.**

    `docs/claims-register-brief.md` §0.1 says "New tables prefixed `claim_`",
    following the module convention (`proj_*`, `grant_*`, `bid_*`).

    **Why the repo wins.** In this codebase a table prefix *means* "belongs to
    a feature-flagged module", and the brief's own §6 insists this is not a
    module: it carries no flag, every vertical reads it, and a workspace with
    no vertical modules still benefits. `claims` sits beside `documents` and
    `projects` as core, and `ref_claim_kinds` follows the `ref_*` platform
    catalogue convention already set by `ref_question_sets`. `claim_revisions`
    keeps the prefix because it genuinely is a child of `claims`.

31. **Claims are typed against a seeded catalogue, and `kind` is validated in
    the router rather than by a check constraint.**

    A claim carries `kind` (a `ref_claim_kinds` key), a machine-readable
    `value` and a human-readable `statement` — all three, not one.

    **Why:** the feature's whole promise is that facts arrive filled in. That
    only works if a fact can be matched to the thing that wants it — a
    register field to import it from, a funder's question to pre-fill, a
    review rule to age it. Matching free prose is guesswork, and a wrongly
    auto-filled answer on a funder's form is worse than a blank box.

    **Why not a check constraint:** the same reasoning `0014` records for
    `tenant_question_sets.ref_key`. A hard constraint means a migration every
    time we learn a new fact type, and each vertical brings a dozen —
    Tenderhouse alone adds contract values, framework memberships and TUPE
    positions. Validating at the edge (422 `unknown_claim_kind`) means new
    kinds ship as fixture rows, and a *retired* kind leaves its claims
    readable-but-unmatched rather than breaking the register screen for every
    workspace that already holds one.

32. **A claim's identity is `(tenant_id, kind, subject, period)`, and only
    confirmed rows are unique.**

    `subject` names which instance of a multi-valued kind (a trustee, a named
    policy, "Public liability"); `period` names which slice of a series
    ("2024/25"). Both are null for the ordinary standing fact.

    **Why both exist from day one:** the brief's §7 payoff — the July
    monitoring report using the *current* beneficiary number rather than
    January's — requires exactly one row a consumer reads with no
    period-selection logic. But "income for each of the last three years" is a
    real funder question, and OSCR returns exactly that. Retrofitting either
    column under live tenant data is precisely the migration §9 warns the
    window closes on, so they are cheap now and expensive later.

    **Why uniqueness binds `status = 'confirmed'` only:** a proposal that
    duplicates a confirmed claim is not a collision to reject — it is how a
    changed figure gets noticed ("the register now says £912,000; you hold
    £847,000"). Confirming supersedes the old row rather than deleting it, so
    "what did we tell the funder in January" stays answerable.

33. **Value history lives in `claim_revisions`, not in `audit_log`, and
    re-verifying a claim writes no revision.**

    **Why not `audit_log`:** those rows are activity-feed material and are
    already scrubbed in place (see `0011_scrub_unshare_audit_titles.py`), so
    their `meta` is not a contract anything may query. The value that answers
    "what did we assert last spring" has to be a first-class row.

    **Why re-verification writes nothing:** moving `last_verified` means
    "still true"; writing a revision means "now different". Conflating them
    would fill the history with non-events and bury the changes, which are the
    only reason the table exists.

34. **Public-register lookups are the second sanctioned third-party HTTP
    client, and their API keys are platform-level rather than per-tenant.**

    `app/claims/registers.py` follows `app/search.py` exactly — plain `httpx`,
    one timeout, no retry, a missing key is a 503 naming the register, an
    upstream failure is a 502, and the client is injectable so tests never
    touch the network. Hard constraint 3 (LiteLLM only) does not bind, for the
    reason `search.py` already records: a register is not a model provider.

    **Why platform keys:** Companies House, the Charity Commission and OSCR
    all issue one key per *application*, not per end user, and the data is
    public and OGL-licensed either way. The cost is that one workspace's
    lookups spend an allowance every workspace shares — Companies House caps
    at 600 requests per five minutes and suspends applications that habitually
    exceed it. Hence `register_lookup_rate_limit_per_hour`, the one rate limit
    in the codebase whose job is to protect *other tenants* rather than us.

    **Why no SSRF defence in the client:** the identifiers are validated
    against fixed patterns in the router before any URL is built, and a value
    matching `^[A-Z0-9]{8}$`, `^\d{6,8}$` or `^SC\d{6}$` cannot express a path
    segment or a host. The URL-supplied-by-user hazard in
    `docs/modules/form-fetch-prd.md` §4 does not arise here.

35. **Trustee and director claims store name, role and appointment date only.**

    Companies House also returns a partial date of birth, nationality and
    occupation for every officer; `registers.py` reads past all three.

    **Why:** it is all public data, so this is a choice rather than a
    requirement — but the cheapest place to not hold personal data is before
    it arrives, and nothing downstream wants it. No funder form asks for a
    trustee's date of birth. Holding one for every client's whole board, in
    every workspace, would be a data-protection surface bought for nothing.

    **Scotland note:** trustee names have appeared on the Scottish Charity
    Register only since 9 March 2026 (Charities (Regulation and
    Administration) (Scotland) Act 2023), and a trustee may hold an exemption
    where publication would put them at risk. So an OSCR import returning no
    trustees is normal and must never be surfaced as a failure.

36. **A funder's question is answered from the register only when the size of
    the field says it is a lookup.**

    Pre-fill has two tiers. Tier A returns the claim as the answer with no
    model call; tier B marks the section `uses_claims` so a model drafts it
    *with* the facts. The line between them is `PREFILL_MAX_LIMIT` (120
    characters), plus: exactly one claim matched, a scalar value kind, single
    cardinality, not expired, not a vault question, and the text fits.

    **Why the field size and not just "does it fit":** "Who is the applicant
    organisation, and what is its legal form?" at 750 characters matched a
    single charity-number claim in an early build, and the one-line answer fit
    the box and passed every other check — while answering a different question
    from the one asked. The funder chose that box size, and a large one is the
    clearest statement we have that they want prose. Caught by a test before it
    reached anything real, and the test is still there.

    **Why so conservative overall:** every condition is a way an answer could
    be wrong in a field somebody then submits over their own name. A blank the
    consultant fills is a far cheaper failure than a confident wrong one.

37. **`uses_claims` forces a solo model call, exactly as `uses_vault` does.**

    `plan_calls` batches small, self-contained questions to save calls, and the
    batched prompt carries only the shared project data — no vault excerpts and
    no claims block.

    **Why:** a 750-character "Who is the applicant organisation?" is precisely
    the shape `plan_calls` likes to batch, and batched it would answer from
    nothing, which is the failure claims exist to fix. Skeleton sections were
    never at risk (no limit means always solo); form questions are, and phase 3
    is what starts setting the flag on them.

38. **An answer sheet records where each answer came from, in three states.**

    `AnswerOut.origin` is `claim` (the register answered it outright),
    `claim_assisted` (a model wrote it with the register's facts) or `drafted`.
    `from_register` on the sheet counts only the first.

    **Why three and not two:** rounding `claim_assisted` up to "from your
    register" would tell a user a paragraph of model prose needs no checking.
    Rounding it down to "drafted" would hide the thing that makes keeping the
    register current worth doing. Both fields carry defaults and must keep
    them — stored sheets are jsonb read back through `AnswerOut(**a)`, so a
    required field would 500 every sheet written before this shipped.

    `claim_ids` is on each answer for Tenderhouse (brief §12.5): a bid question
    references claims rather than being one, so re-verifying a claim can later
    flag every stored answer that leaned on it.

39. **Extraction and harvesting are gated on a keyword score, not run on
    everything.**

    A document proposes claims only if some chunk mentions at least
    `MIN_CHUNK_SCORE` (2) distinct fact kinds, whole-word. Below that the
    upload makes **zero** model calls.

    **Why:** most uploads are site plans, meeting notes and photographs of
    noticeboards, not annual accounts. Running a model over every one would put
    a per-upload charge on the whole vault to find facts in a tenth of it —
    which is the difference between a feature and a tax on uploading. One hint
    is too loose ("income" appears in a tenancy note about somebody else);
    three would miss a clean table of registered details.

    **Corollary:** the `extract` usage kind is separate from `summary` even
    though both fire on upload and use the same alias, because the whole cost
    argument rests on being able to see the difference on the usage screen.

40. **A proposal's quote must appear in the text it claims to come from, and
    the parser enforces it.**

    Every extracted or harvested fact carries a `locator` — a `doc_chunks` id
    when reading an upload, a question id when harvesting a submitted draft —
    and a verbatim quote. Four things are dropped silently: an unknown kind, an
    unquotable fact, a locator we never supplied, and a quote that does not
    appear at that locator (compared whitespace- and case-insensitively,
    because models reflow quotes out of PDF tables).

    **Why in the parser and not the prompt:** a rule the parser applies is a
    rule; a rule the prompt states is a request. The failure that matters is a
    plausible figure pinned to a *real* chunk it did not come from — hardest to
    notice, worst to submit, and the one no prompt instruction reliably stops.

41. **A harvested claim carries no citation, and says where it came from.**

    Claims harvested from a submitted application land `source='draft'` with no
    `source_chunk_id` and no `source_document_id`: the generated document is
    not a chunked vault upload, so there is nothing citable to point at. That
    puts a harvested fact in the same position as a register fact — usable,
    attributable in prose, never given a `[c:]` marker.

    The distinction is kept on the row rather than flattened to "document"
    because it is real: an uploaded certificate is evidence, while a bid is the
    organisation repeating a claim it made somewhere else. Worth keeping, worth
    checking a little harder.

42. **Harvesting is fire-and-forget, and failing at it is invisible.**

    Marking an application submitted enqueues `harvest_claims_from_application`
    inside `contextlib.suppress`, and the job itself never raises into arq.

    **Why:** harvesting is a by-product of work somebody has already finished.
    No Redis, no worker, or a model that returns nonsense must not be able to
    stop somebody recording that they submitted their application — that is the
    thing that mattered, and it has already happened.

43. **Removing a member releases their claims explicitly, and counts them.**

    `owner_membership_id … on delete set null` means the foreign key would do
    this anyway and nothing would break. `disown_claims` does it first so the
    count can go into the `member.remove` audit meta.

    **Why:** "nothing breaks" is how a register quietly stops being anybody's
    job. Removing somebody is the one moment an admin could reassign what they
    owned, so it is the moment worth recording.

    **What is deliberately not done:** unowned claims are *not* counted as
    needing attention. Ownership is optional and most claims never have an
    owner, so counting them would put a permanent warning on every workspace —
    and a warning that is always there is not read, which is the same rule the
    drafting warning follows.

## Recorded while surfacing overdue claims (12 Aug 2026)

44. **`/claims/summary` returns four numbers, not the brief's two, and the
    sidebar badge adds two of them together.**

    `docs/claims-register-brief.md` §14.1 step 1 specifies
    `{needs_attention, proposals}`. The endpoint also returns `stale` and
    `expired`, which break `needs_attention` down rather than adding to it —
    one claim can be both, so the three do not sum.

    **Why the repo wins.** The rule the brief itself sets is that whatever
    surfaces this must name the problem, not gesture at staleness
    (`claims_warning`, #43). Two numbers cannot: "3" cannot tell lapsed
    insurance apart from an overdue review, and those send somebody to
    different places. With the breakdown the badge's own label reads "1 lapsed,
    1 past review, 3 to check".

    **The badge counts `needs_attention + proposals`** — everything waiting on
    a person, the way an inbox counts unread — but it is only warn-coloured
    when `needs_attention > 0`. A pile of proposals is an opportunity, not a
    fault, and colouring the two alike is how a warning stops being read.

    **The trap:** the summary's two predicates are the same two lines as
    `_row_out`'s `stale`/`expired`, and must stay that way. A badge that
    disagrees with the screen it links to is worse than no badge. It counts in
    Postgres (`claims_review_idx`, `claims_tenant_status_idx`) rather than
    pulling every claim back, because it is read on every workspace load.

    **Steps 2 and 3 of §14.1 are still unbuilt** — the arq `cron_jobs` sweep
    and email. Verified again on 12 Aug 2026: there is still no scheduler and
    no email transport in the codebase, so neither is a small change.

45. **A claim does not learn when it lost its owner. Unowned stays a view
    somebody opts into, and the person who removed the member is told at the
    moment of removal instead.**

    `docs/claims-register-brief.md` §14.2 asks this to be settled before
    building either half: the schema cannot tell "never had an owner" from
    "lost its owner", and `on delete set null` erases the difference.

    **Two things found first, neither of which the brief knew.** Ownership was
    *unreachable from the UI* — `owner_membership_id` was settable only over the
    API and nothing in `apps/web` sent it, so every claim was unowned and the
    filter as specified would have matched everything. And an owner could not be
    *cleared*: `update_claim` tested `if body.owner_membership_id is not None`,
    so the only owned→unowned path in the whole system was removing the person.

    **Why no `owner_lost_at`.** Not cost — the second finding makes it cheap,
    one write site and one clear site. Meaning: a claim that lost its owner is
    **not a fact that has gone off**. Its content is still true. It cannot join
    `needs_attention` (#44) without wrecking a count that means "this may be
    false", and giving it a permanent number of its own is precisely the badge
    nobody reads (#43). What it needs is one person told at the one moment they
    can act, and that is a response body, not a column. The decision stays
    reversible: `audit_log` holds every `member.remove` with its
    `claims_disowned` count, so the column can be added later and backfilled if
    a pilot user asks to be chased about it.

    **So three changes, and two are contracts:**

    - `ClaimPatch.owner_membership_id` is **the only field on any patch model in
      this codebase where an explicit null means "clear it"**. `update_claim`
      reads `model_fields_set` for that one field; every other field keeps the
      `is not None` test, because a fact with no statement is not a fact.
      Handing something back to nobody is a real act.
    - `DELETE /members/{membership_id}` answers **200 with
      `{claims_disowned: N}`**, not 204. 204 is honest about the membership and
      silent about everything the person was responsible for.
    - `owner_membership_id` needed `_check_owned_membership`, the same hole as
      `_check_owned_document`: Postgres validates foreign keys with RLS
      bypassed, so the constraint alone would accept another workspace's
      membership id and quietly make one of their people responsible for one of
      our facts. Any future FK on a tenant table needs the same check.

    **Deliberately not done:** `member.*` is still absent from `FEED_PATTERNS`.
    Putting membership churn into every tenant's activity feed is a platform
    decision about what that feed is for, and §14.2 does not need it — the two
    things it asked for are a findable view and the admin being told, and
    neither runs through the feed.

46. **Typed claims from the register screen are confirmed on arrival** (14 Aug
    2026). The API already did this (`create_claim`); the UI now has an "Add a
    fact" panel for anything a public register does not publish. Asking someone
    to type a fact and then tick it would be theatre. Machine-found claims
    still arrive `proposed`.

47. **Editing a tenant question set's questions returns it to unverified**
    (14 Aug 2026). The tick was against a different form. Name/funder/URL-only
    edits do not, because those are labels on the same questions. Verify in the
    same PATCH still wins.

48. **Submit harvest is no longer silent** (14 Aug 2026). Enqueue failures
    still cannot fail the status change. `ApplicationOut.harvest_queued` is set
    only on POST `.../status` to `submitted`, so the Grantwork room can say
    whether the scan was queued or send the person to type the facts by hand.

49. **Charity Commission V2 is the live contract** (14 Aug 2026). The Azure
    APIM product still documents `charitytrustees/{number}/{suffix}`, but that
    operation 404s; trustee names ride on `allcharitydetailsV2.trustee_names`.
    Field names also drifted from the older docs our fixtures first encoded
    (`reg_status` is `R`/`RM` not "Registered"/"Removed",
    `charity_co_reg_number`, `address_line_one`,
    `latest_acc_fin_year_end_date`). Charitable objects and activities are on
    `charitygoverningdocument` and `charityoverview`. Those secondary calls
    are best-effort, same posture as OSCR annual returns — a 404 there must
    not fail an import that already has a register entry. Email, phone and
    web are still unread.

50. **OSCR's public API still does not return trustee names** (14 Aug 2026).
    The Scottish Charity Register web entry for Sanday Development Trust
    (SC035495) lists nine trustees. `GET all_charities` has no trustee field,
    there is no trustees operation (those paths 404), and annual returns carry
    only `TotalNumberofCharityTrustees` (a count). Official docs still list
    two calls. Do not scrape the HTML register; a Scottish charitable company
    can import Companies House for directors. The live payload is camelCase
    (`charityName`, `currentConstitutionalForm`, `principalContactAddress`);
    `annualreturns` returns a JSON array encoded as a JSON string; the charity
    id for that call is `id` (a UUID), not the `SCxxxxxx` number.

## Recorded during core project plans (14 Aug 2026)

51. **Sidebar "Projects" may be documents-only or a thin plan; that plan is
    not Groundwork.**

    `POST /projects` accepts `kind: blank | planned`. Blank is the historic
    vault/chat container. Planned sets `projects.has_plan`, seeds a primary
    "Project brief" markdown document (DB row + keyword chunk, no object
    storage — CI has storage off) and optional `project_tasks` (title, due
    date, `assignee_membership_id`). Nested CRUD lives at
    `/projects/{id}/plan-tasks` so it never collides with Groundwork
    `/projects/{id}/tasks`.

    **Why the repo wins.** Groundwork `proj_tasks` requires a CLH `stage_key`
    and the `projects` feature flag. Folding general work into that spine
    would either invent a fake stage or hide tasks from tenants that never
    bought development projects. The two products stay distinct: `/app/projects/*`
    remains the development room.

    Assignees are workspace members, not CRM contacts and not free-text
    `owner_name`. Cross-tenant membership ids 404 in app code (FK checks
    bypass RLS).

    A documents-only project can grow a plan via `POST /projects/{id}/plan`
    (idempotent). `PATCH /projects/{id}` is rename/archive; extra fields are
    dropped, which is why "Add a plan" previously returned `no_changes`.
    `project_tasks.details` is a short note on the row — not comments, not
    Groundwork tickets. The UI is a checklist (todo/done);
    `doing` remains in the check constraint but is not a third column.




## Recorded during the ECCTA readiness panel (14 Aug 2026)

52. **Director identity verification is read from the officers payload's
    `identity_verification_details`, defensively, and the value prefix is a
    contract.**

    The field ships in two shapes (CH developer forum, Aug 2026): a record
    with the verified date and the ACSP that carried out the check, or a bare
    completion statement — and it is absent entirely on an unverified
    officer. `_idv_value()` normalises all three; every value begins
    `verified` or `not yet verified`, and the web readiness strip keys off
    that prefix rather than parsing prose. Any change to the prefix breaks
    the panel silently, which is why the register test pins all three shapes.

    Three new kinds: `director_idv` (multi, per director, ages with the
    confirmation statement like the other identity facts) and the two filing
    deadlines `confirmation_statement_due` / `accounts_due`, whose
    `next_review` IS the due date — a passed deadline surfaces through the
    ordinary staleness machinery (badge, sweep, digest), not a bespoke alarm.
    The panel itself is derived in the web page from loaded claims
    (proposed + confirmed), never stored. The 18 Nov 2026 transition end is
    hard-coded copy in one place (`EcctaStrip`); after that date the line
    should change from a deadline warning to a standing compliance state.

## Recorded during the Hearth design review (16 Aug 2026)

53. **Hearth stays. The Clearbit visual language in the `design` skill does
    not apply to this product.**

    The skill's own precedence puts project brand above its defaults and says
    not to restyle a product to look like Clearbit. Hearth is a real brand —
    tokens in `globals.css`, two documented HTML specs, AA-verified pairings —
    so the review applied the skill's *principles* (states, spacing discipline,
    contrast, tabular figures, empty states) and kept terracotta, cream,
    Fraunces and Plus Jakarta Sans.

    The flatness the review was asked to fix was never the palette: it was the
    app under-using it. Hearth's second surface existed only in the sidebar,
    Fraunces appeared on exactly one screen (the chat greeting), and the
    dashboards spent none of the three-per-view accent budget. `--color-band`,
    the `Section` component's serif heading and the `.figure` voice exist to
    spend that range on screens that already had it available.

54. **Control styling is centralised in `apps/web/components/ui`. The
    module-local style constants now re-export from it.**

    `grants/ui.ts` previously documented the opposite rule — module-local
    copies so one vertical's UI could not silently restyle another. Reversed:
    fourteen screens each kept their own `btn` / `input` / `card`, and the
    copies drifted rather than protecting anything (Grantwork on `bg-surface`
    and `border-line`, claims on `bg-card` and `border-edge` — the same colours
    under two names, plus `rounded-[10px]` hand-written everywhere despite
    `--radius-btn` being 10px). Deliberate divergence should be an override at
    the call site, not five near-identical constants nobody can diff by eye.

    `contacts/ui.ts`, `grants/ui.ts` and `projects/[id]/tabs/ui.ts` keep their
    import paths and now re-export the shared definitions.

55. **Three Hearth values are extended where the spec fails WCAG 2.2 AA or is
    silent. Access wins over the kit; the divergence is here.**

    - `--edge-input: #a2907a` for control outlines. Hearth's `--edge-strong`
      is 1.58:1 against a white card, which fails 1.4.11's 3:1 floor for the
      border that identifies an input. This is the nearest warm tone that
      passes, at 3.09:1.
    - Disabled buttons use `text-subtle`, not the kit's `text-faint`. On
      `--edge` that pairing measures 4.42:1, short of AA for 13.5px text;
      `--subtle` is 5.64:1.
    - `--text-hearth-page: 26px` records the page-title step the screens had
      already settled on as `text-[26px]`. Hearth documents only 42px
      (greeting) and 22px (section), and a dashboard `h1` needs something
      between. Naming what the repo does beats inventing a fourth size or
      leaving it as an arbitrary value. `--radius-chip: 9px` and
      `--radius-inset: 11px` name Hearth's two intermediate radii for the same
      reason. The serif floor of 22px is unchanged.

56. **`window.prompt` / `window.confirm` are replaced by `useAsk()`. No new
    code may use the native ones.**

    Nine call sites used browser dialogs for real data entry — a dormancy
    reason, a gate sign-off exception, an award amount, an owner invite email
    and the typed workspace-purge confirmation. A native prompt cannot be
    labelled, hinted, validated or styled, and it drops the user into browser
    chrome with no relationship to the workspace. `DialogProvider` /
    `useAsk()` (`components/ui/dialog.tsx`) keeps the promise-based shape of
    the calls it replaced, and adds focus return, Escape, a contained tab
    order, and a confirm button that stays inert until a typed confirmation
    matches. `/admin` mounts its own provider because it sits outside the app
    layout.

    Consequence: the purge flow now gates client-side on the exact workspace
    name *and* still sends it for the API to check. The API remains the real
    gate.

57. **The community profile is a module, not claims-register kinds alone**
    (27 Aug 2026). Facts about the place a tenant covers — the ferry, the
    school roll, households — are not "what the tenant asserts about itself"
    (claims brief §10), and a school with a roll, an age range and a nursery
    is one entity with several attributes, which the register's flat rows
    cannot hold. So: `community` flag, tables `community_profile` /
    `community_assets` / `community_statistics` (migration 0025), one asset
    table for every facility category with scalar `attributes` jsonb rather
    than per-domain tables, and one profile row per tenant with settlements
    as tags rather than a places table.

58. **`ref_claim_kinds.category` gains `'community'`; `claims.source` gains
    `'module'`** (both CHECK widenings in 0025). A `'module'` claim is a fact
    maintained in a module's own register and asserted on save; `source_ref`
    carries the stat's public source URL. `'typed'` would lose that
    provenance and `'register'` would claim a public-register lookup that
    never happened. The drafting worker needs no change: a non-register
    source with no chunk already renders as "recorded by the organisation —
    do not cite".

59. **Community-fed claims are confirmed on save, not proposed.** The same
    reasoning as typed claims (`create_claim`): the person saving the figure
    is the assertion, and a second confirm screen would be theatre.
    `assert_module_claim` (`app/claims/service.py`) supersedes the previous
    confirmed row and writes a revision, exactly as a typed edit would. The
    claim is *not* retracted when the stat is deleted or re-pointed at a
    different kind — a claim is what the workspace asserts until superseded
    or managed in the register; the module feeding it does not own it.

60. **Operator initial data entry happens inside the tenant workspace.**
    `admin_create_tenant` deliberately gives the operator no membership, so
    at setup the operator is either invited as a member for the data-entry
    session, or creates the workspace as owner, enters the data, and then
    reissues the owner invite to the client. No admin-side duplicate editor
    is built; `/admin` stays a console, not a second app.

61. **The community DOR isolation checks live in `test_community.py`, not
    `test_isolation.py`.** The isolation suite's community routes sit behind
    the feature gate, so under a tenant that has not bought the module a
    cross-tenant id 404s at the gate and the check proves nothing. The
    header-attack list and SQL-level per-table checks stay in the isolation
    suite (they hold regardless of flags); the direct-object-reference
    attacks run in `test_community.py` with the flag enabled on both
    tenants, where a pass means RLS and not the gate.
