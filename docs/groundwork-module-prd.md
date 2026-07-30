# Module Build Spec — Development Projects ("Groundwork")
## Operations Engine · Module Phase 1 (MVP) · PRD for an LLM coding agent

**Version:** 1.0 · 29 July 2026
**Status:** Approved for build. Pilot tenant #1 (a development consultancy) is committed and will onboard at exit.
**Prerequisite:** The Operations Engine **Phase 1 core is built and live** (multi-tenant chat workspace, knowledge vault RAG with citations, LiteLLM gateway with route aliases, Supabase Postgres + RLS, R2 storage, Redis/worker queue, Stripe billing, audit log, usage events). This spec adds a feature-flagged module on top. **Do not modify core behaviour; this build is additive.**

---

## 0. How to work with this spec (read first)

You are integrating a new module into an existing production codebase. Follow these rules:

1. **Read the repo before writing code.** Locate and reuse: the RLS/tenancy helper (every request runs `set_config('app.current_tenant', $tenant_id, true)` inside a transaction), the FastAPI router registration pattern, the asyncpg pool wrapper, the worker queue (arq/rq consumer used by the Docling pipeline), the R2 presigned upload/download helpers, the LiteLLM client (OpenAI-compatible, called with the tenant's virtual key, **aliases only — never provider SDKs**), the vault retrieval function (pgvector cosine + tsvector full-text, reciprocal-rank fusion, returns chunks with ids), the audit-log and usage-event writers, and the frontend API client generation (OpenAPI → TS in `/packages/shared`).
2. **Where the repo's conventions differ from this spec, the repo wins.** Record every such divergence in `docs/groundwork/ASSUMPTIONS.md` as you go.
3. **Work milestone by milestone (Section 10).** A milestone is done when its proof point passes and tests are green in CI. Do not start the next milestone with a red suite.
4. **Additive only.** New tables are prefixed `proj_`. New API routes live under `/api/v1/projects`. New frontend routes live under `/app/projects`. The only core touchpoint is reading `tenants.features` for the flag.
5. **Feature flag:** the module is active for a tenant iff `tenants.features->>'projects' = 'true'`. Flag off → API routes return 404, nav item hidden. No schema change to `tenants` is needed (features is already JSONB).
6. **Every mutation writes `audit_log`. Every LLM call writes `usage_events`** (kind `draft`, with model, tokens in/out, cost) via the existing writers.
7. **All reference data is seed data, never code.** Funding programmes, templates, risk library: rows in tables, loaded by an idempotent seed script. Programme facts carry `last_verified` dates — they are point-in-time snapshots (verified 28 Jul 2026), not immutable truth.
8. **MIT/Apache/BSD-licensed dependencies only.** New deps this spec expects: `python-docx` (MIT) for DOCX assembly, `WeasyPrint` (BSD-3) for the one-page health-card PDF. Check licences on anything else you add.
9. **UK English** in all user-facing strings and generated documents.

**Product context (one paragraph):** Consultants who run community-led development projects (affordable housing by CLTs/cohousing groups, community buildings) manage 3–15 concurrent projects that each run 6–12 years through five sector-standard stages — **Group, Site, Plan, Build, Live** (mapping to RIBA Plan of Work 0–1, 2–4, 5, 6–7). Today they work in spreadsheets and Word. This module gives them a stage-gated project spine and three AI-drafted documents grounded in the project's own data. The core loop that must feel magical: *keep the spine current → the monthly client report assembles itself.*

**Explicit non-goals for this phase (do not build):** Gantt/timeline component (milestone list only) · community client portal (consultant-facing UI only) · recurring obligations scheduler (task due dates only) · development appraisal engine (flat budget table only) · planning statement / business plan / share offer drafting (three document types only) · Stripe changes (pilot is invoiced manually; flag is set by ops) · contracts/valuations ledger (contract facts are JSONB fields) · meeting-intelligence integration · Scotland/Wales statutory rule packs beyond the seeded applicability toggles.

---

## 1. Data model — 9 tenant tables + 2 platform reference tables

All `proj_*` tenant tables follow the core RLS pattern exactly:

```sql
alter table proj_projects enable row level security;
create policy tenant_isolation on proj_projects
  using (tenant_id = current_setting('app.current_tenant', true)::uuid);
-- Repeat for every proj_* tenant table. A migration is not done until its
-- table has RLS + a passing isolation test (Section 9).
```

```sql
-- ===== 1. projects =====
create table proj_projects (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants(id) on delete cascade,
  name text not null,
  client_org text,                              -- the community group / client name
  project_type text not null default 'clh_new_build',
  delivery_route text,                          -- direct | ha_partnership | council_enabled
  status text not null default 'active',        -- active | dormant | complete | archived
  dormancy_reason text,                         -- required when status='dormant'; key from risk library categories
  stage_current text not null default 'group',  -- group | site | plan | build | live
  site_address text,
  homes_planned int,
  start_date date,
  target_completion date,
  applicability jsonb not null default '{}',    -- {wales:bool, hrb:bool, bng_exempt:bool, conservation_area:bool}
  contract_facts jsonb not null default '{}',   -- {contractor, contract_form, retention_pct, lads_per_week}
  created_by uuid,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);
create index on proj_projects (tenant_id, status);

-- ===== 2. stages =====
create table proj_stages (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null,
  project_id uuid not null references proj_projects(id) on delete cascade,
  stage_key text not null,                      -- group | site | plan | build | live
  label text not null,                          -- display name
  riba_ref text,                                -- e.g. "RIBA 0–1"
  position int not null,
  status text not null default 'pending',       -- pending | active | passed | regressed | na
  planned_start date, planned_end date,
  forecast_start date, forecast_end date,
  actual_start date, actual_end date,
  gate jsonb not null default '[]',             -- [{id, criterion, kind: doc|task|manual, ref, done, done_by, done_at, note}]
  gate_signed_off_by uuid,
  gate_signed_off_at timestamptz,
  gate_exceptions text,
  unique (project_id, stage_key)
);
create index on proj_stages (tenant_id, project_id);

-- ===== 3. tasks (milestones are flagged tasks) =====
create table proj_tasks (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null,
  project_id uuid not null references proj_projects(id) on delete cascade,
  stage_key text not null,
  title text not null,
  details text,
  owner_name text,
  due_date date,
  is_milestone boolean not null default false,
  tags text[] not null default '{}',            -- e.g. {statutory}, {funding}, {planning}
  status text not null default 'todo',          -- todo | doing | done | na
  source text not null default 'template',      -- template | manual | ai
  completed_at timestamptz,
  position int not null default 0
);
create index on proj_tasks (tenant_id, project_id, stage_key, status);
create index on proj_tasks (tenant_id, due_date) where status in ('todo','doing');

-- ===== 4. document registry =====
create table proj_documents (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null,
  project_id uuid not null references proj_projects(id) on delete cascade,
  doc_type_key text not null,                   -- from template doc-type list
  title text not null,
  stage_key text not null,
  status text not null default 'required',      -- required | drafting | review | final | submitted | na
  ai_draftable boolean not null default false,
  regulated boolean not null default false,     -- future use; none regulated in MVP set
  current_file_key text,                        -- R2 object key of latest version
  vault_document_id uuid,                       -- optional link to a core vault document
  versions jsonb not null default '[]',         -- [{version, file_key, created_at, created_by, note}]
  notes text,
  updated_at timestamptz default now(),
  unique (project_id, doc_type_key)
);
create index on proj_documents (tenant_id, project_id, status);

-- ===== 5. budget lines =====
create table proj_budget_lines (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null,
  project_id uuid not null references proj_projects(id) on delete cascade,
  category text not null,                       -- land | construction | externals | abnormals | fees | statutory | contingency | finance | other
  label text not null,
  budget numeric(12,2) not null default 0,
  forecast numeric(12,2) not null default 0,
  actual numeric(12,2) not null default 0,
  note text,
  position int not null default 0
);
create index on proj_budget_lines (tenant_id, project_id);

-- ===== 6. funding sources (the tenant's stack per project) =====
create table proj_funding_sources (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null,
  project_id uuid not null references proj_projects(id) on delete cascade,
  programme_key text,                           -- optional ref → proj_ref_programmes.key
  name text not null,
  funder text,
  kind text not null,                           -- grant | loan | shares | equity | s106 | other
  amount_sought numeric(12,2),
  amount_secured numeric(12,2),
  status text not null default 'identified',    -- identified | applying | offered | secured | drawing | complete | declined
  conditions text,
  drawdown_schedule jsonb not null default '[]',-- [{label, due_date, amount, status: planned|claimed|paid, claimed_at}]
  notes text,
  updated_at timestamptz default now()
);
create index on proj_funding_sources (tenant_id, project_id);

-- ===== 7. risks =====
create table proj_risks (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null,
  project_id uuid not null references proj_projects(id) on delete cascade,
  category text not null,                       -- key from seeded risk library
  description text not null,
  likelihood int not null check (likelihood between 1 and 5),
  impact int not null check (impact between 1 and 5),
  owner_name text,
  mitigation text,
  status text not null default 'open',          -- open | monitoring | closed
  review_date date,
  source text not null default 'template',      -- template | manual
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);
create index on proj_risks (tenant_id, project_id, status);

-- ===== 8. planning conditions tracker =====
create table proj_conditions (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null,
  project_id uuid not null references proj_projects(id) on delete cascade,
  application_ref text,                         -- LPA reference, free text
  number text not null,                         -- condition number as on the decision notice
  description text not null,
  pre_commencement boolean not null default false,
  status text not null default 'outstanding',   -- outstanding | submitted | discharged | partially_discharged | na
  submitted_at date,
  discharged_at date,
  notes text
);
create index on proj_conditions (tenant_id, project_id, status);

-- ===== 9. stakeholders (lite) =====
create table proj_stakeholders (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null,
  project_id uuid not null references proj_projects(id) on delete cascade,
  name text not null,
  org text,
  role text not null,                           -- lpa | landowner | funder | contractor | consultant | community | other
  email text, phone text,
  notes text,
  last_contact date
);
create index on proj_stakeholders (tenant_id, project_id);
```

**Platform reference tables** (NOT tenant-scoped; `select` for all authenticated users via RLS policy `using (true)`, writes only via service role / seed script):

```sql
create table proj_ref_templates (
  key text primary key,                         -- 'clh_new_build'
  version int not null,
  payload jsonb not null                        -- {stages:[...], tasks:[...], doc_types:[...], risks:[...]}
);

create table proj_ref_programmes (
  key text primary key,                         -- e.g. 'sahp_cme'
  name text not null,
  funder text not null,
  nations text[] not null,                      -- {england} | {scotland} | {wales} | {uk}
  kind text not null,                           -- capital | revenue | loan | equity_match | advice
  stage_fit text[] not null,                    -- subset of {group,site,plan,build,live}
  amount_note text,                             -- human-readable range/basis
  match_note text,
  eligibility text not null,
  status text not null,                         -- open | announced | paused | closed | ended
  route_url text,
  docs_required text[] not null default '{}',
  last_verified date not null,
  next_review date not null,
  notes text
);
```

**Derived, not stored:** portfolio RAG health is computed in the API per project: **programme** = red if any milestone task overdue >30 days, amber if overdue ≤30 days, else green; **cost** = red if Σforecast > Σbudget by >10%, amber if over at all, else green; **risk** = red if any open risk with likelihood×impact ≥ 16, amber if ≥ 9, else green. Pure function with unit tests.

---

## 2. Seed content (ship as fixtures + idempotent seed script)

### 2.1 Template `clh_new_build` v1 — stages & gates

| # | stage_key | label | riba_ref | Gate checklist (kind) |
|---|---|---|---|---|
| 1 | group | Group | — (continuous) | Legal entity incorporated (manual) · Governance & decision-making agreed (manual) · Bank account & insurances in place (manual) |
| 2 | site | Site | RIBA 0–1 | Housing needs evidence in place (doc: housing_needs_survey) · Development appraisal viable (doc: development_appraisal) · Legal interest secured — option/HoTs/freehold (manual) · Pre-app response assessed (doc: preapp_response) |
| 3 | plan | Plan | RIBA 2–4 | Planning consent granted (manual) · Funding package committed (manual) · Contractor tender accepted (manual) · Development/partnership agreements signed (manual) |
| 4 | build | Build | RIBA 5 | Practical completion certified (doc: pc_certificate) · Building control completion received (manual) · Warranties in place (manual) |
| 5 | live | Live | RIBA 6–7 | All homes allocated & occupied (manual) · Management arrangements operational (manual) · Funder final sign-off received (doc: final_monitoring_report) · End of defects period reached (manual) |

Stage rows are created per project from this template; `doc:`-kind gate items resolve done-ness from the referenced registry row reaching status `final` or `submitted` (recompute on document status change); `manual` items are toggled by the user.

### 2.2 Template task library (seeded per project; ~64 tasks; titles below, agent adds one-line details each)

**Group (8):** Confirm vision & objectives with client group · Choose & register legal form (CLT/CBS/co-op) · Adopt constitution & policies · Recruit/confirm steering group & roles · Skills audit & training plan · Open bank account, arrange insurances · Membership drive & register · Agree decision-making & meeting cadence.
**Site (12):** Define site requirements brief · Site search & land audit · Landowner approach & negotiation [milestone] · Commission housing needs survey · Desktop planning-policy review · Development appraisal v1 · Title & legal due diligence · Utilities & access desk study · Contamination Phase 1 desk study `{statutory}` · Pre-application submission [milestone] `{planning}` · Assess pre-app response · Heads of terms / option agreement [milestone].
**Plan (18):** Appoint architect/design team [milestone] · Appoint QS/cost consultant · Appoint principal designer (CDM) `{statutory}` · Community co-design rounds · Concept design sign-off (RIBA 2) [milestone] · Spatial coordination (RIBA 3) · BNG assessment & Gain Plan `{statutory}` (skip if bng_exempt) · Fire statement prepared `{statutory}` · Submit planning application [milestone] `{planning}` · S106 heads of terms `{planning}` · CIL liability & exemption forms `{planning}` · Planning decision [milestone] `{planning}` · Update appraisal & value engineer · Funding applications submitted [milestone] `{funding}` · Finance close [milestone] `{funding}` · Technical design (RIBA 4) · Tender pack issued · Tender review & contractor selection [milestone].
**Build (14):** Building regs full-plans approval `{statutory}` · Appoint principal contractor (CDM) `{statutory}` · F10 notification if notifiable `{statutory}` · Party wall notices (if applicable) `{statutory}` · Utility connections ordered [milestone — long lead] · Pre-start meeting & programme baseline · Start on site [milestone] · Monthly valuations & certificates (recurring) · Monthly funder drawdown claims (recurring) `{funding}` · Variations/change control log maintained · Discharge pre-commencement conditions `{planning}` [milestone] · Snagging inspection · Practical completion [milestone] · Handover pack & O&M received.
**Live (12):** Allocations policy adopted · Advertise & allocate homes [milestone] · Leases/tenancies executed · Residents move in [milestone] · Setup management arrangements (RMC/agent) · Service charge budget set · Defects log & contractor liaison · End-of-defects inspection [milestone] · Retention release · Funder final monitoring report `{funding}` · Impact report to board · Lessons-learned review.

**Applicability effects at project creation:** `wales=true` → add task "SAB drainage approval" `{statutory}` (Plan). `hrb=true` → add banner on project ("Higher-Risk Building — BSA gateways apply; out of MVP scope, track manually") + task "Confirm BSR gateway strategy" `{statutory}`. `bng_exempt=true` → skip BNG task. `conservation_area=true` → add task "Heritage/conservation officer pre-app engagement" `{planning}`.

### 2.3 Document-type registry (seeded per project; 32 types)

Format: `doc_type_key · title · stage · ai_draftable`

group: `constitution · Constitution / rules · false` · `vision_statement · Project vision statement · false` · `skills_audit · Skills & capacity audit · false`
site: `housing_needs_survey · Housing needs survey · false` · `site_brief · Site requirements brief · false` · `development_appraisal · Development appraisal · false` · `due_diligence_report · Site due diligence report · false` · `preapp_pack · Pre-application pack · false` · `preapp_response · Pre-app response & assessment · false` · `heads_of_terms · Heads of terms / option agreement · false`
plan: **`feasibility_study · Feasibility study · TRUE`** · `design_brief · Design team brief · false` · `engagement_report · Community engagement report · false` · `planning_application_pack · Planning application pack · false` · `s106_hot · S106 heads of terms · false` · `bng_gain_plan · Biodiversity gain plan · false` · **`funding_bid · Funding application · TRUE`** (one registry row per funding source; see 5.3) · `finance_terms · Finance term sheet · false` · `tender_pack · Tender pack · false` · `development_agreement · Development / partnership agreement · false`
build: `build_contract · Building contract · false` · `baseline_programme · Baseline programme · false` · **`monthly_report · Monthly client report · TRUE`** (versioned monthly) · `drawdown_claim · Funder drawdown claim · false` · `variation_log · Variation & change log · false` · `pc_certificate · Practical completion certificate · false`
live: `allocations_policy · Allocations policy · false` · `lease_pack · Lease / tenancy pack · false` · `management_agreement · Management agreement · false` · `handover_pack · Resident handover pack · false` · `final_monitoring_report · Funder final monitoring report · false` · `impact_report · Impact report · false`

### 2.4 Risk library (seeded to every project as `source='template'`, status `open`, consultant edits down)

| category key | Default description | L | I | Default mitigation |
|---|---|---|---|---|
| site_acquisition | Site not secured or acquisition falls through | 4 | 5 | Parallel site options; option agreement early; LA relationship |
| funding_gap | Funding gap between stages stalls the project | 4 | 5 | Stage-gated fundraising plan; monitor drawdown vs spend monthly |
| planning_refusal | Planning refused or hostile pre-app | 3 | 5 | Pre-app engagement; community support evidence; policy-compliant design |
| cost_inflation | Build cost inflation breaks viability | 3 | 4 | Contingency ≥10%; re-tender options; value engineering rounds |
| group_capacity | Volunteer burnout / loss of key people | 3 | 4 | Succession planning; consultant carries process load; training |
| partner_withdrawal | HA partner or lender withdraws | 2 | 5 | Alternative partners identified; avoid single-point dependence |
| la_delay | Local authority slow decisions / officer turnover | 3 | 3 | Named contacts; escalate via members; build slack into programme |
| local_opposition | Local opposition undermines consent | 2 | 4 | Early engagement; support-letter campaign; address objections in design |
| contractor_insolvency | Contractor insolvency mid-build | 2 | 5 | Financial checks at tender; retention; warranty & step-in rights |
| governance_dispute | Governance dispute within client group | 2 | 3 | Clear constitution; decision log; independent chair option |

### 2.5 Funding programme catalogue (10 rows, all `last_verified='2026-07-28'`, `next_review='2026-10-28'`)

| key | name | funder | nations | kind | stage_fit | amount_note | status | eligibility (condensed) |
|---|---|---|---|---|---|---|---|---|
| sahp_cme | Social & Affordable Homes Programme 2026–36 (CME route) | Homes England | england | capital | plan,build | Negotiated per scheme; £27.3bn programme | open | RPs; community-led groups typically via RP partner; community-led a named priority |
| crtb_fund | Community Right to Buy Fund (Pride in Place) | MHCLG | england | capital | site,plan | ~£51m acquisition + £10m capacity, per-award TBC | announced | Community groups acquiring Assets of Community Value; route unpublished at last verification |
| ahf_viability | Heritage Revival Fund — Project Viability Grant | Architectural Heritage Fund | england | revenue | group,site | Up to £20k | open | Charities/not-for-profits; historic buildings, town centres, deprived areas |
| ahf_development | Heritage Revival Fund — Project Development Grant | Architectural Heritage Fund | england | revenue | plan | Up to £100k; ≥10% match | open | As above; RIBA 2–4 work |
| nlhf_10_250 | National Lottery Heritage Grants £10k–£250k | National Lottery Heritage Fund | uk | capital | site,plan,build | £10k–£250k | open | UK not-for-profits; heritage focus; 4 investment principles |
| booster_equity | Community Shares Booster Fund — equity match | Co-operatives UK | england | equity_match | plan | £10k–£50k matched investment | open | CBS/co-ops with share offer; Standard Mark usually required; dev grants strand paused |
| acre_halls | Platinum Jubilee Village Halls Fund | ACRE (Defra) | england | capital | plan,build | £7.5k–£75k at 20% of cost; 80% match | paused | Rural halls (pop <10k); charities/CIOs; freehold or 21+yr lease; limited funds — verify |
| ecology_clh | Community-led housing lending | Ecology Building Society | uk | loan | plan,build | To 80% LTV (CLT/HA), 75% (co-op/cohousing) | open | CLTs, co-ops, cohousing; business plan + projections; EPC standards |
| rihf | Rural & Islands Housing Fund | Scottish Government | scotland | capital | site,plan,build | Negotiated; feasibility grants to £20k | open | Rural/island community bodies; extended to 2028 |
| cwmpas_cch | Communities Creating Homes | Cwmpas / Welsh Government | wales | advice | group,site,plan | Advice + small grants to £2.5k | open | Welsh community-led housing groups |

`docs_required` per row: seed sensibly from kind (grant → business plan, financial projections, governance docs, community support evidence, project timeline, funding stack; loan → accounts, appraisal, security/valuation, planning status; equity_match → share offer document, projections, Standard Mark evidence).

---

## 3. API surface — `/api/v1/projects` (conventions: JSON snake_case, JWT + tenant middleware, module flag checked by dependency)

| Method & path | Behaviour |
|---|---|
| `POST /projects` | Create from setup payload `{name, client_org, delivery_route, homes_planned, start_date, target_completion, site_address, applicability{...}}`. Seeds stages, tasks, document registry, risks from `proj_ref_templates.clh_new_build`. Returns full project. |
| `GET /projects` | Portfolio list: each row includes computed RAG (programme/cost/risk), stage_current, next milestone (title+date), counts (open risks, outstanding pre-commencement conditions, overdue tasks). |
| `GET /projects/{id}` · `PATCH /projects/{id}` | Detail / update scalar fields incl. contract_facts, applicability. |
| `POST /projects/{id}/status` | `{status, dormancy_reason?}` — dormant requires a reason key. |
| `GET /projects/{id}/stages` · `PATCH /projects/{id}/stages/{stage_id}` | Dates & status; `regressed` allowed with note. |
| `POST .../stages/{stage_id}/gate/{item_id}/toggle` | Manual gate items only; doc-kind items are computed. |
| `POST .../stages/{stage_id}/signoff` | `{exceptions?}` — requires all gate items done OR exceptions text; sets signed_off fields; advances `stage_current`; audit-logged. |
| `GET/POST/PATCH/DELETE .../tasks` | CRUD + `?stage_key=&status=&overdue=true` filters; bulk-complete endpoint. |
| `GET .../documents` · `PATCH .../documents/{id}` | Registry list; status transitions (any → any, audit-logged); notes; link `vault_document_id`. |
| `POST .../documents/{id}/upload` → `POST .../documents/{id}/upload/complete` | Presigned R2 PUT (reuse core helper, mime allowlist docx/pdf/xlsx); complete appends to `versions`, sets `current_file_key`. `GET .../documents/{id}/download` → presigned GET. |
| `GET/PUT .../budget` | Bulk read/upsert of budget lines; response includes totals + variance per category. |
| `GET/POST/PATCH/DELETE .../funding` | Funding sources CRUD incl. drawdown_schedule JSONB. |
| `GET /projects/funding-programmes` | Reference catalogue with `?nation=&kind=&stage=&status=` filters; each row includes `stale: next_review < today`. |
| `GET/POST/PATCH/DELETE .../risks` · `.../conditions` · `.../stakeholders` | CRUD. |
| `POST /projects/{id}/drafts` | `{kind: monthly_report\|feasibility_study\|funding_bid, params: {month?, funding_source_id?, instructions?}}` → enqueue worker job → `{job_id}`. Validates: funding_bid requires funding_source_id; monthly_report requires month. |
| `GET /projects/drafts/{job_id}` | `{status: queued\|running\|complete\|failed, document_id?, download_url?, error?}` (poll; SSE optional). |
| `POST /projects/{id}/health-card` | Generates the one-page PDF; returns presigned GET URL. |

---

## 4. Frontend — `/app/projects` (Next.js App Router; reuse core auth/layout/theming; nav item gated on the feature flag)

**`/app/projects` — Portfolio.** Table: project · client · stage chip (Group→Live stepper mini) · three RAG dots with tooltips · next milestone (title, date, overdue styling) · pre-commencement conditions outstanding count · updated. Row click → project room. "New project" → setup form (single page, not a chat wizard): fields per `POST /projects` + the four applicability toggles with one-line explanations. Empty state explains the module in two sentences.

**`/app/projects/[id]` — Project room.** Header: name, client, status control (active/dormant-with-reason/complete), stage stepper (click stage → tab anchors). Tabs:
1. **Overview** — RAG summary cards, next 5 milestones, funding position (sought vs secured vs drawn), top 3 open risks by score, recent activity (from audit log), **"Generate health card (PDF)"** and **"Draft monthly report"** buttons.
2. **Stages & gates** — accordion per stage: dates (planned/forecast/actual, editable), gate checklist (manual toggles; doc-kind items shown with live status and a link to the registry row), sign-off button (disabled until complete unless exceptions entered), exceptions display.
3. **Tasks** — filterable list (stage, status, tag, overdue); milestone flag renders a flag icon; inline add/edit; bulk complete.
4. **Documents** — registry table: type, stage, status pill, version count, updated; actions: upload version, download, change status, **"Draft with AI"** on the three `ai_draftable` rows (opens draft modal).
5. **Funding** — stack table (name, funder, kind, sought, secured, status, next drawdown due); drawdown rows expand inline; side panel **"Browse programmes"** → catalogue with filters, stale badge on `stale:true` rows, "Add to project" copies a row into `proj_funding_sources` with `programme_key` set.
6. **Budget** — editable grid grouped by category; footer totals: budget / forecast / actual / variance (red if forecast > budget).
7. **Risks** — register table sorted by score (L×I); add-from-library or manual; close with note.
8. **Conditions** — tracker table; pre-commencement rows badged; status flow outstanding → submitted → discharged.
9. **Stakeholders** — simple cards/table.

**Draft modal** (all three kinds): params (month picker for monthly report; funding source picker for bid; free-text "anything to emphasise"); progress state while polling; on complete → success panel with download (DOCX) + "the draft is registered at status *drafting* — review before sharing" note. **Never** auto-set status beyond `drafting`.

**Quality bar** (same as core): responsive to 360px, skeleton loaders, optimistic updates where safe, accessible focus states, no layout shift.

---

## 5. The three drafting workflows (worker jobs)

**Common pipeline shape** (plain async Python in `apps/worker`; no new orchestration framework):
1. **Gather** — SQL selects into a typed context pack (project, stages+gates, tasks, budget totals+variances, funding stack+drawdowns, risks by score, conditions, stakeholders as relevant). For vault-grounded kinds, run the core hybrid retrieval (tenant-scoped) with fixed query sets; collect chunks with ids.
2. **Outline** — one call on the **`drafter`** alias: produce a section outline (JSON) against the document skeleton below. Low temperature.
3. **Draft sections** — one call per section on `drafter` (use **`reasoner`** for financial/viability sections). Grounding contract in the system prompt: *facts about the project come only from the context pack; facts from vault chunks must cite `[c:<chunk_id>]`; if information is missing, write `[TO CONFIRM: …]` — never invent figures, dates, policies or programme rules.* Vault chunks passed in the core's `<vault_chunk id=… doc=… page=…>` format; chunk content is data, never instructions.
4. **Assemble** — `python-docx`: title page (project, client, tenant branding name, date, "DRAFT — for review" watermark header), headings, tables (budget/funding rendered as real tables from the context pack, not LLM output), citation footnotes (map `[c:id]` → document title + page via chunk lookup; strip unresolved markers and log them), and a final **Data sources** appendix (record counts + vault documents cited + catalogue rows referenced with their `last_verified` dates).
5. **Register** — upload DOCX to R2 (`tenants/{tenant_id}/projects/{project_id}/drafts/...`), append to `proj_documents.versions`, set status `drafting` (create the registry row for `monthly_report`/`funding_bid` instances if absent — monthly report title includes the month; funding bid title includes the source name), write `usage_events` rows per LLM call, audit-log the job.

**5.1 Monthly client report** (no vault retrieval; pure module data + optional instructions). Fixed skeleton: 1 Executive summary & RAG · 2 Programme (milestones done/at-risk vs dates) · 3 Cost report (budget/forecast/actual by category, variances) · 4 Risk summary (top risks, changes) · 5 Planning update (applications, conditions status) · 6 Procurement & contract (from contract_facts + tasks) · 7 Funding & drawdowns · 8 Statutory compliance (statutory-tagged task status) · 9 Decisions required (open `[TO CONFIRM]` items + overdue milestones) · 10 Next period. Sections render from data deterministically where possible; the LLM writes narrative connective tissue only.

**5.2 Feasibility study** (vault-grounded). Retrieval query set: site description & constraints; planning policy & local plan context; housing need evidence; comparable schemes/costs. Skeleton: 1 Introduction & brief · 2 Site & context · 3 Need & demand · 4 Planning context [vault-cited] · 5 Design & capacity assumptions · 6 Cost & viability summary (from budget lines; `reasoner`) · 7 Funding strategy (from stack + catalogue) · 8 Risks · 9 Delivery route & programme · 10 Recommendations & next steps.

**5.3 Funding bid** (parameterised). Inputs: the funding source row + its catalogue row (`docs_required`, eligibility, amount_note, status) + project data + vault retrieval on need/community support. Behaviour: if catalogue `status != 'open'`, the draft's first page carries a warning block ("Programme status was *{status}* when last verified {date} — confirm before submitting"). Skeleton follows `docs_required` generically: 1 Organisation & governance · 2 The project · 3 Need & community support [vault-cited] · 4 What the funding will pay for (from budget) · 5 Full funding stack & match · 6 Delivery plan & milestones · 7 Risks & management · 8 Outcomes & monitoring commitment.

**Cost guard:** each job ≤ 15 LLM calls, context per call ≤ 24k tokens; abort with a friendly error beyond that. Expected cost ≈ $0.05–0.15/draft on the routed mix — log actuals.

**5.4 Health card** (no LLM): one-page WeasyPrint PDF from a fixed HTML template, plain English: project + client · stage position (Group→Live bar) · "on track?" three traffic lights with one-line explanations · money summary (total cost, secured funding, gap) · next 3 milestones · top 3 risks in plain words · "decisions needed from the board". Tenant brand colour on the header rule.

---

## 6. Integration contract with the core (read-only expectations)

- **Auth/tenancy:** module routes use the same JWT dependency + tenant middleware + RLS transaction wrapper. No new roles; `member` can do everything except delete projects (admin+).
- **Vault:** module reads retrieval results only; it never writes vault documents (uploading project files to the module registry stores to R2 under module keys, NOT into `documents`/`doc_chunks` — vault ingestion of project files is a user action in the core UI, out of scope here beyond the optional `vault_document_id` link).
- **LiteLLM:** aliases `drafter` and `reasoner` only, via the tenant's virtual key. If aliases are named differently in the live config, map in one constants file and record in ASSUMPTIONS.md.
- **usage_events / audit_log:** reuse writers; new `kind` value `draft` for usage; audit actions namespaced `projects.*` (e.g. `projects.gate_signoff`).
- **Theming:** project room inherits the tenant CSS variables automatically; health card uses tenant primary colour.
- **Billing:** none. Ops sets `features.projects=true` manually for the pilot tenant.

---

## 7. Guardrails (product requirements, not suggestions)

1. **Draft-first:** no generated document ever leaves status `drafting` without a human status change. No auto-send, no auto-submit, anywhere.
2. **No invented facts:** the `[TO CONFIRM]` convention is mandatory in prompts; assembly counts unresolved markers and surfaces "N items to confirm" in the UI success panel.
3. **Citations:** vault-derived statements carry resolvable citations; unresolved markers are stripped and logged, never rendered as fake references.
4. **Staleness:** catalogue rows past `next_review` badge in the UI and warn inside any draft that references them.
5. **Version history:** registry versions are append-only; no destructive overwrites.
6. **Isolation:** every `proj_*` tenant table ships with RLS + isolation tests before any feature code lands on it.

---

## 8. Out-of-scope reminders for the agent (do not "helpfully" add)

Gantt charts · client-facing portal or share links · recurring job scheduler · appraisal calculators · additional templates or document types · Stripe/pricing changes · email sending · new LLM providers or direct provider calls · modifications to core chat/vault behaviour · Scotland/Wales statutory logic beyond the seeded toggles.

---

## 9. Acceptance criteria (Definition of Done)

**Isolation & flag**
- [ ] Isolation suite extended: two tenants with projects — every module endpoint as tenant A returns zero tenant-B rows; direct-object-reference attacks on all `{id}` routes → 404/403
- [ ] `features.projects` false → all module routes 404; nav hidden; no console errors

**Spine**
- [ ] Creating a project seeds exactly: 5 stages, 64 tasks (±applicability adjustments), 32 registry rows, 10 risks; re-running the seed script is idempotent
- [ ] Applicability toggles produce their documented effects (2.2)
- [ ] Gate sign-off blocked until items done or exceptions given; doc-kind gate items flip automatically when the registry row reaches `final`; sign-off advances `stage_current` and audit-logs
- [ ] Dormant status requires a reason; portfolio shows dormant styling
- [ ] Portfolio derived RAG matches the pure-function unit tests; renders 25 projects < 1s p50 (staging)

**Documents & drafting**
- [ ] Upload/download a registry document version round-trips via presigned URLs; versions append correctly
- [ ] Monthly report on the demo project: DOCX with all 10 sections; every figure traceable to module records (manual spot-check of 10 figures = 10/10); zero invented content; cost row logged
- [ ] Feasibility study on the demo project (with 3 seeded vault docs): ≥5 resolvable citations to correct documents/pages; `[TO CONFIRM]` items surfaced in UI
- [ ] Funding bid against a `status='announced'` programme carries the status warning block
- [ ] Draft jobs respect the 15-call/24k-token guard; failure path shows a friendly error and no orphaned registry rows
- [ ] Health card: one page, renders tenant brand colour, all six content blocks present

**Ops**
- [ ] Migrations up/down clean (Alembic); seed script documented in README
- [ ] All module mutations visible in `audit_log`; draft costs visible in `/usage/summary`
- [ ] New-dev setup notes for the module appended to repo docs; ASSUMPTIONS.md exists and is honest

**Exit demo (founder + pilot acceptance)**
- [ ] Pilot consultancy onboarded as a live tenant with `features.projects=true`
- [ ] 1–2 real projects entered (target: data entry ≤ 90 min per project with the consultant)
- [ ] First real monthly client report generated, reviewed and sent to their client within 15 minutes of data entry completing
- [ ] Consultant confirms the §11A pilot metrics are being tracked: reports/month from live data, drafts actually used, self-reported time saving

---

## 10. Milestones — 4 weeks (phrased as agent working sessions)

| Week | Build | Proof point |
|---|---|---|
| **W1 — Schema & seeds** | Migrations for 11 tables + RLS + policies; isolation tests; template fixture + idempotent seed loader; `POST /projects` end-to-end with applicability effects; RAG pure function + tests | Create project via API → correct seeded counts; isolation suite green |
| **W2 — Spine UI** | Portfolio page; project room with all 9 tabs CRUD-complete; gate mechanics incl. doc-kind auto-flip; setup form | Founder walkthrough: create → edit every tab → sign off Site gate with exceptions → dormant/reactivate |
| **W3 — Drafting** | Worker pipelines (common shape + 3 kinds); DOCX assembly with citations + data-sources appendix; draft modal + polling; registry integration; usage/audit wiring | Three DOCX drafts from the demo project meet the acceptance checks |
| **W4 — Health card, polish, pilot** | WeasyPrint health card; staleness badges; catalogue browser; error/empty states; acceptance run; pilot onboarding (tenant flag, seed real projects with the consultant) | Full acceptance list green in staging; pilot tenant live with first real monthly report |

**Estimate note for the founder:** ~3.5–4 dev-weeks at the established freelance rate (≈£6–8K at £350–500/day); marginal run-cost per active module seat ≈ $1.70/month per the module design's unit economics.

---

*Companion documents (context, not required to build): module research & design `cms4tc4de0l8i08ad8e17ucwf` (esp. §11A MVP Cut) · platform core build spec `cms0k8yb00qcz07adpiplrtaa` · consolidated platform recommendations `cmrz5sbjm0xzr06adrscga3tv`. Funding programme facts verified 28 Jul 2026 — re-verify quarterly per the project's standing rule.*
