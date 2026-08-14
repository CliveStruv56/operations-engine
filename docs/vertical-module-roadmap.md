# Vertical Module Roadmap — what to build after Groundwork
## Flowgrid OS · research + next-module recommendation

**Version:** 1.1 · 2 August 2026, status refreshed 14 August 2026
**Status:** Research complete; sequence in motion. Orders 1–2 are **done** (module kit
3 Aug, Grantwork 3–4 Aug — built ahead of the §4 validation gate, which has still not
been run). Tenderhouse is next and is now cheaper than the §3 estimate: the claims
register (`docs/claims-register-brief.md`, built 12 Aug, unflagged core) already is the
answer library §2.1 assumed Tenderhouse would build for itself.
**Scope:** Which industry/sector modules to add after Groundwork, in what order, and the
platform work that makes each one cheaper than the last.

---

## 0. Why this document exists

Flowgrid OS ships one vertical module today: **Groundwork** (community-led development
projects), gated on `tenants.features->>'projects'`. The commercial model treats modules as
per-tenant entitlements — "the packaging lever for the two-tier model" — and the
partner/reseller channel is the stated route to scale. So "what is module #3?" is
simultaneously a build-sequencing question and an investor-narrative question.

Two findings from the research shape every recommendation below.

### 0.1 There is no module system

Both existing modules are hand-wired across roughly **18 registration points**. Groundwork is
≈5,500 LOC / 2 migrations / 3 worker jobs; CRM is ≈1,600 LOC / 1 migration / 0 worker jobs.
Copy-pasting that a third time is affordable; a fourth and fifth time is not. More seriously,
the copy-pasted material includes the RLS boilerplate — where the failure mode is **silent
cross-tenant leakage**, not a test failure. §1 is the fix.

### 0.2 The engine has a specific shape, and it is not "AI for X"

Strip Groundwork of its housing vocabulary and what remains is a reusable machine:

> a **stage-gated spine** + a **typed document registry** + a **seeded content library** +
> **staleness-tracked reference data** + an **LLM pipeline that assembles a cited DOCX whose
> tables come from real rows, not model output** + a **non-LLM one-page PDF** summarising
> position.

Sectors whose work already has that shape are cheap to serve and genuinely differentiated.
Sectors whose work is transactional — bookings, rostering, payments, pipeline CRM — are
expensive to serve and produce an undifferentiated chat wrapper. That single test does most
of the ranking work in §2, and it is why the "health clubs" class of candidate is
recommended against rather than merely ranked low.

**The ideal customer profile for any Flowgrid vertical module**, stated once:

> An SMB or consultancy running a small number of long-lived, document-heavy engagements
> that are **externally scrutinised** by a funder, buyer or regulator, where each engagement
> follows a standard lifecycle and where a recurring submission or report is the artefact
> that gets paid for or judged.

---

## 1. Platform work first — the "module kit"

Converts "another 5,500-LOC copy-paste" into "a manifest, a migration and a router".

**Status: §1.1–1.5 shipped 3 August 2026** (§1.5 in `c62b6d7` — `worker/drafting/` is the
module-agnostic engine, `worker/drafts/` the Groundwork adapter). Only §1.6 (hygiene) partly
remains: the web flag guard landed, the schema-location rule is recorded as ASSUMPTIONS #20
but Groundwork's own split is deliberately left in place.

| Item | Status |
| --- | --- |
| 1.1 Module manifest | ✅ `apps/api/app/modules.py` |
| 1.2 `make_feature_gate(flag)` | ✅ both modules adopted it |
| 1.3 RLS migration helper | ✅ `apps/api/migrations/rls.py` + `test_every_module_table_has_rls` |
| 1.4 `PATCH .../features` | ✅ endpoint + operator-console editor |
| 1.5 Generalised drafting pipeline | ✅ `apps/worker/worker/drafting/` (engine) + `drafts/` (Groundwork adapter) |
| 1.6 Hygiene (web flag guard, schema location) | ◑ flag guard shipped; schema rule recorded (ASSUMPTIONS #20), Groundwork's split left as-is |

### 1.1 Module manifest — replaces six hand-edited registration points ✅

A new flag today must be added independently to `apps/api/app/schemas.py:53`
(`FEATURE_FLAGS`), `apps/web/lib/admin.ts:38`, a new `require_*` gate, the sidebar JSX in
`apps/web/app/app/sidebar.tsx`, `apps/api/app/routers/activity.py:20` (`ALLOWED_ACTIONS`),
and `apps/api/tests/test_isolation.py:16` (`TENANT_TABLES`). Nothing enforces consistency
between them.

`apps/api/app/modules.py` holds one `Module(flag, label, tables, feed_prefix)` per
entitlement. `FEATURE_FLAGS`, the gate dependencies, the activity feed's namespace patterns
and the RLS coverage check all derive from it. `apps/web/lib/admin.ts` mirrors the display
half; the API rejects unknown keys with a 422, so the two lists cannot drift into a flag that
looks enabled in the console and 404s in the app.

`web_search` is declared with no tables — it is cross-cutting chat enrichment rather than a
module with a router, but it is still an entitlement the console has to offer.

### 1.2 `make_feature_gate(flag)` factory ✅

The two gates were byte-for-byte identical apart from the flag string. Both now come from the
factory; `require_projects` and `require_contacts` survive as aliases at their existing import
paths, so none of the ~60 router call sites changed.

The two idioms stay distinct: **404 for whole module routers** (module invisible) versus
**400 / silent-skip for cross-cutting enrichment** inside shared endpoints such as chat and
⌘K search.

### 1.3 RLS migration helper ✅

`apps/api/migrations/rls.py::enable_tenant_rls()`. Deliberately migrations-local rather than
imported from `app`, so schema history cannot shift when application code is refactored.
Migrations 0003, 0005 and 0009 now call it and emit byte-identical SQL.

The helper makes it easy to get right; **`test_every_module_table_has_rls` makes it
impossible to get wrong quietly**. It asserts every manifest table has RLS enabled plus a
`tenant_isolation` policy with both a USING and a WITH CHECK clause keyed on
`app_current_tenant()` — USING alone still permits writing rows tagged for another tenant,
WITH CHECK alone still permits reading them. This is the check that would have caught a
forgotten policy, which no functional test can: the tables a new module adds are exactly the
tables no existing test touches.

### 1.4 `PATCH /admin/tenants/{id}/features` ✅

Creation was the only write path for `features`, so selling a module to a live client meant
hand-editing jsonb. Now a platform-admin endpoint, audited as `tenant.features_change`, with
a module editor in the operator console.

Two design rulings: it **merges** rather than replaces (naming one module cannot silently
drop another), and withdrawal is `{"flag": false}`, which hides the module without deleting
its rows. It runs in `db.tenant_tx()` scoped to the target tenant, as tenant creation does —
the `tenant_update` policy accepts `id = app_current_tenant()`, so **`db.platform_tx()` was
deliberately not used** and that fenced connection stays read-only as its docstring promises.

### 1.5 Generalise the drafting pipeline — the single biggest lever

`apps/worker/worker/drafts/` is ~1,600 LOC. The genuinely reusable part is
outline → sections → assemble → register, plus the `LlmLedger` cost guard (`drafts/llm.py`)
and the DOCX assembler (`drafts/assemble.py`). The `Section` dataclass at
`drafts/prompts.py:16-24` — `key, title, alias, uses_vault, table, guidance` — is already
module-agnostic. `SKELETONS` and `ContextPack` (`drafts/context.py`) are not: both are keyed
on `proj_*` tables.

Extract a `ContextPack` protocol (engagement header + fact tables + vault excerpts), a
per-module `gather()` callable, and a module-registered `SKELETONS` map. Keep `job.py`,
`llm.py`, `assemble.py` and `register.py` shared. This makes a new draftable document type a
~150-line change rather than a new pipeline, and it is what the estimates in §3 assume.

### 1.6 Two hygiene items to fix before they are replicated

- **Missing web-side flag guard.** `/app/projects`, `/app/projects/new` and
  `/app/projects/[id]` have no feature check and render a raw API error string when the flag
  is off. `apps/web/app/app/contacts/page.tsx:48` has the correct pattern (404 → "not
  enabled" state). Fix Groundwork, then copy the good pattern into every new module.
- **Schema-location rule.** Groundwork splits its Pydantic models between core
  `apps/api/app/schemas.py:283-339` and `apps/api/app/groundwork/schemas.py`. Adopt one rule
  — all module schemas live in `app/<mod>/schemas.py` — and record it in
  `docs/groundwork/ASSUMPTIONS.md`.

### 1.7 Module tiers — use these for estimating

| Tier | What it is | Cost | Example |
| --- | --- | --- | --- |
| **0 — template pack** | New `proj_ref_templates` / `proj_ref_programmes` seed rows only. No code. | 1–2 days | Built-environment variants (§2.4) |
| **1 — register module** | Tables + router + typed client + pages. No worker jobs. | ~1,500–2,000 LOC, ~15 files | CRM |
| **2 — spine module** | Tier 1 + stage/gate spine + draftable docs + worker jobs + PDF export | ~5,500 LOC, 2 migrations | Groundwork |

With §1.1–1.5 complete, a Tier 2 module drops to roughly **2,500–3,000 LOC**.

---

## 2. Ranked shortlist

Scored on three criteria. **Leverage** = fraction of Groundwork/CRM machinery reused.
**WTP** = evidence of existing spend at or above our price point. **Channel** = existence of
a consultant, franchise or trade-body population who would resell white-label.

| # | Vertical | Leverage | WTP | Channel | Tier | Verdict |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | **Bid & tender operations** ("Tenderhouse") | ★★★★★ | ★★★★★ | ★★★★★ | 2 | Build — biggest market |
| 2 | **Grant funding & impact reporting** ("Grantwork") | ★★★★★ | ★★★★☆ | ★★★★★ | 2 | Build first — cheapest |
| 3 | **Inspection & assurance readiness** ("Assurance") | ★★★★☆ | ★★★★★ | ★★★★★ | 2 | Build third |
| 4 | Built-environment consultancies (architecture, ecology/BNG, planning, heritage) | ★★★★★ | ★★★☆☆ | ★★★☆☆ | **0** | Ship as template packs, not a module |
| 5 | H&S / ISO / quality consultancies | ★★★★☆ | ★★★★☆ | ★★★★★ | 2 | Strong, but overlaps #3 — merge or defer |
| 6 | Accountancy & bookkeeping practices | ★★☆☆☆ | ★★★★★ | ★★★★★ | — | **Channel, not a module** |
| 7 | Food & drink manufacture / hospitality groups (BRCGS, SALSA, HACCP) | ★★★★☆ | ★★☆☆☆ | ★★★☆☆ | 2 | Right shape, thin budgets |
| 8 | Letting/estate agency & block management | ★★★☆☆ | ★★★☆☆ | ★★★★☆ | 1 | Live regulatory shock, crowded PropTech |
| 9 | Independent schools / MATs | ★★★★☆ | ★★★★☆ | ★★☆☆☆ | 2 | Good fit, long sales cycles, safeguarding data |
| 10 | MSPs / IT consultancies (Cyber Essentials, ISO 27001) | ★★★★☆ | ★★★★☆ | — | 2 | They are the reseller; do not compete |
| 11 | Recruitment agencies | ★★☆☆☆ | ★★★★☆ | ★★★☆☆ | — | ATS shape, not document-lifecycle shape |
| 12 | Health clubs, salons, hospitality venues | ★☆☆☆☆ | ★★☆☆☆ | ★★☆☆☆ | — | **Recommend against** |

### 2.1 Bid & tender operations — see `docs/modules/tenderhouse-prd.md`

A single SME tender response costs £1,500–£8,000 to produce (freelance bid writers charge
£300–£600/day); unassisted win rates run around 20–35%. Social value is now mandatory in most
tenders at 10–30% of the score, yet a majority of bidders score under half the available
social-value points. Incumbent tooling is enterprise-priced — Loopio reportedly from ~$20k/yr,
AutogenAI ~$30k/yr with a five-seat minimum, Responsive from $5k/yr for five users — against
a thin SME layer around £99/month. A £49/seat white-label product sits in an evidenced gap.

### 2.2 Grant funding & impact reporting — see `docs/modules/grantwork-prd.md`

The charity sector spends on the order of **£900m a year applying for grants**, and charities
in the £100k–£1m income band spend around **35% of their grant income** on the applications
themselves. Groundwork already contains a funding-programme catalogue with
`last_verified`/`next_review` staleness, an AI-draftable `funding_bid`, and a
`monthly_report` skeleton (`apps/worker/worker/drafts/prompts.py:26-42`) that maps almost
line-for-line onto a funder monitoring report. This is the closest thing to a re-skin
available, and it sells to customers we already have.

### 2.3 Inspection & assurance readiness — see `docs/modules/assurance-prd.md`

CQC is targeting 9,000 assessments by September 2026, sharply raising inspection odds for
small providers; small care agencies already spend £100–£250/month on software that handles
*records*, not assurance. Independent training providers face ESFA funding-assurance reviews
plus Ofsted monitoring visits within 24 months of first enrolment, with two days' notice.
The gate-item model is an unusually exact match: a regulator's framework is a tree of
statements, and "do we have evidence for this statement?" *is* a gate item.

**Scope boundary:** organisational assurance evidence only — no care plans, patient records
or pupil records. Lead with Ofsted-regulated education and training providers, which involve
no clinical data at all. See the PRD for the full boundary and its enforcement.

### 2.4 Built-environment consultancies — Tier 0, not a module

Architecture, ecology/BNG, planning and heritage practices are the highest-leverage group on
the list — the RIBA Plan of Work spine is already modelled — but the population is small
(around 3,769 RIBA chartered practices) and trading conditions are poor, with architectural
businesses in financial distress up by nearly a fifth in 2025. BNG's extension to Nationally
Significant Infrastructure Projects from November 2026 is a genuine tailwind for ecology
consultancies specifically.

Correct treatment: **new `proj_ref_templates` rows**, not a new module. Days of work, widens
Groundwork's addressable base, no new tables, no new flag.

### 2.5 Accountancy is a channel, not a module

The numbers are attractive — an estimated 30,000–40,000 UK firms, roughly 80% with four or
fewer staff, practice-management software already selling at £30–60/user/month (exactly our
price point), and MTD for Income Tax starting April 2026 for the £50k+ band.

But the value in that category is workflow plus integrations (HMRC, Companies House, Xero),
and we have no integration layer; the field is dense (Karbon, Bright, Senta, TaxDome). Our
drafting engine is not what an accountant is buying.

Meanwhile accountants are the single most trusted advisor to UK SMBs and map cleanly onto the
partner motion: sign a client → provision workspace → curate → bill monthly.

**Recommendation: pursue accountancy practices as Managed-tier resellers in GTM; do not build
an accountancy module.**

### 2.6 Why the "health clubs" class scores badly

Worth stating plainly, since consumer-facing SMBs are the intuitive place to look. Gyms,
salons, clinics and similar businesses have thin operating-document estates, and their
software budget already goes to bookings, memberships, payments and marketing automation.
Flowgrid OS's differentiator — assembling a cited, data-grounded document from a maintained
spine — has almost nothing to bite on. We would be selling an undifferentiated chat wrapper
into a market with entrenched incumbents (Mindbody, Glofox, Fresha).

The same logic rules out most transaction-led consumer SMB sectors. **Sector-specific is not
the same as vertical-suitable**: the qualifying test is the ICP in §0.2, not industry
identity.

---

## 3. Recommended sequence

| Order | Work | Effort | Why here |
| --- | --- | --- | --- |
| 1 | **Module kit** (§1.1–1.6) — ✅ done 3 Aug 2026 | 2–3 days | Unblocks everything; §1.4 unblocks selling modules at all |
| 2 | **Grantwork** — ✅ built 3–4 Aug 2026 (handoff §6g) | 3–4 weeks (~£5–7k) | Cheapest; sells to existing Groundwork customers; proves multi-module expansion |
| 3 | **Tenderhouse** — next; cheaper now the claims register exists | 4–6 weeks (~£7–10k) | Biggest market and clearest price gap; Grantwork de-risks the bid-drafting work |
| 4 | **Built-environment template packs** (Tier 0) | 1–2 days | Widens Groundwork's base for almost nothing |
| 5 | **Assurance** | 5–7 weeks (~£9–12k) | Highest channel leverage; most reference-data commitment; do it once the kit is proven three times |

Estimates use the £350–500/day benchmark established in the platform plan and assume the
module kit is done first.

**Billing dependency.** Stripe billing remains the open Phase 1 item and gates monetising any
of this beyond manual invoicing. §1.4 (`PATCH .../features`) is the minimum needed to sell
modules manually in the interim.

**Packaging note.** With three or more modules, per-module entitlement stops being free —
decide before Tenderhouse whether modules are Pro-tier inclusions or priced add-ons. The
per-seat cost model absorbs inference fine; the question is purely commercial.

---

## 4. Validation before build

This is a product decision, so the meaningful verification is commercial, not technical.

1. **Cheapest real test.** The Groundwork pilot tenant's clients are largely grant-funded
   charities — a Community Land Trust building affordable housing *is* a grant-funded
   charity. Ask the pilot consultancy directly whether a Grantwork flag on their existing
   workspace would be bought. A yes validates the multi-module thesis without writing code.
2. **Channel test.** Ten discovery calls — five bid consultancies or freelance bid writers,
   five fundraising consultancies — asking specifically whether they would resell a branded
   client workspace at Managed pricing. Channel fit is the load-bearing assumption in all
   three PRDs and the one most likely to be wrong.
3. **Pricing test.** Confirm the Tenderhouse price gap with one real quote from Loopio or
   AutogenAI. Every competitor figure in §2.1 is secondary-source and **must not go into an
   investor deck unverified**.

---

## 5. Source notes

Market figures throughout are secondary-source, gathered 2 August 2026, and are point-in-time
snapshots in the same sense as the funding catalogue — treat them as `last_verified`, not as
truth. Re-verify before any external use.

- Charity grant-application spend: [Civil Society](https://www.civilsociety.co.uk/news/charity-sector-spends-900m-a-year-applying-for-grant-funding-report-finds.html) · [UK Fundraising](https://fundraising.co.uk/2022/07/28/small-medium-charities-spend-over-a-third-of-grant-income-on-applications/)
- Bid costs, win rates, social value: [Glaxtons](https://www.glaxtons.co.uk/blog/how-much-do-bid-writing-services-cost/) · [Tender Consultants](https://www.tenderconsultants.co.uk/uk-public-procurement-statistics/) · [social value guide](https://www.tenderconsultants.co.uk/social-value-and-tendering/)
- Bid software pricing: [CleanTender comparison](https://cleantender.co.uk/resources/comparisons/ai-bid-management-software-uk) · [Loopio pricing breakdown](https://autorfp.ai/blog/loopio-pricing)
- Accountancy practice software and MTD: [Bright](https://brightsg.com/blog/how-much-does-practice-management-software-cost-for-accounting-firms-in-the-uk/) · [Karbon](https://karbonhq.com/resources/best-accounting-practice-management-software-uk/) · [FSB on MTD 2026](https://www.fsb.org.uk/resources/article/making-tax-digital-2026-deadlines-rules-and-more-MCQVRXUNIJC5EQRAZBQ7DFJNGYMA)
- Care and inspection: [Caredaily 2026 compliance guide](https://www.caredaily.co.uk/blog/digital-care-management-software-in-the-uk-the-2026-compliance-guide/) · [InspectReady](https://inspectready.co.uk/blog/cqc-compliance-guide-small-care-homes/)
- Training providers: [ESFA evidence requirements](https://www.gov.uk/guidance/apprenticeship-funding-rules-for-training-providers/evidence-requirements) · [Ofsted inspection and ESFA intervention](https://www.gov.uk/government/publications/provider-guide-to-delivering-high-quality-apprenticeships/ofsted-inspection-and-esfa-intervention)
- H&S consultancy: [Arinite](https://www.arinite.com/blog/health-and-safety-consultants-for-small-businesses-what-you-need-and-how-to-choose)
- Bid writers as channel: [Charity Excellence](https://www.charityexcellence.co.uk/charity-freelance-fundraiser/)
- Architecture sector: [Architects' Journal / RIBA survey](https://www.architectsjournal.co.uk/news/surge-in-overseas-work-boosts-architects-income-riba-survey-shows)
- Lettings regulation: [Propertymark on the Renters' Rights Act](https://www.propertymark.co.uk/resource/renters-rights-act-practical-steps-for-letting-agents-to-take-now.html)
