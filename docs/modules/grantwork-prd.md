# Module Build Spec — Grant Funding & Impact Reporting ("Grantwork")
## Flowgrid OS · Vertical module · Mini-PRD

**Version:** 0.1 (mini-PRD) · 2 August 2026
**Status:** Researched and recommended, **not approved for build**. Needs the validation in
`docs/vertical-module-roadmap.md` §4 first.
**Prerequisite:** The module kit (`docs/vertical-module-roadmap.md` §1) — particularly §1.5,
the generalised drafting pipeline, which this module's estimate assumes.
**Feature flag:** `tenants.features->>'grants' = 'true'`.

---

## 0. Framing (read first)

Same working rules as `docs/groundwork-module-prd.md` §0. Restated where they bind:

1. **Additive only.** New tables prefixed `grant_`. Routes under `/api/v1/grants`. Frontend
   under `/app/grants`. The only core touchpoint is reading `tenants.features`.
2. **Where the repo's conventions differ from this spec, the repo wins.** Record divergences
   in `docs/groundwork/ASSUMPTIONS.md`.
3. **All reference data is seed data, never code.** The funder catalogue is rows with
   `last_verified` / `next_review`, exactly as `proj_ref_programmes`.
4. **UK English** in all user-facing strings and generated documents.
5. Every mutation writes `audit_log` (actions namespaced `grants.*`); every LLM call writes
   `usage_events` kind `draft`.

**Product context.** UK charities, CICs and community organisations with roughly £100k–£3m
income run a rolling portfolio of grant applications, each of which becomes — if won — a
multi-year obligation to report against outcomes on the funder's schedule. Today this lives
in spreadsheets, a shared drive of past bids, and one person's memory of what each funder
wants. The sector spends on the order of **£900m a year applying for grants**, and charities
in the £100k–£1m band spend around **35% of their grant income** on the applications
themselves.

**The core loop that must feel magical:** *keep the application and its outcomes current →
the funder's monitoring return assembles itself.*

**Why this module first.** It is the closest thing to a re-skin of Groundwork available.
Groundwork already ships a funding-programme catalogue with staleness tracking, an
AI-draftable `funding_bid`, and a `monthly_report` skeleton
(`apps/worker/worker/drafts/prompts.py:26-42`) that maps nearly line-for-line onto a funder
monitoring report. It also sells to customers we already have: a Community Land Trust
building affordable housing *is* a grant-funded charity, so the Groundwork pilot's client
base is in scope with no new sales motion. That makes it the cleanest available proof of the
multi-module expansion story.

---

## 1. The seven components

| Component | Grantwork |
| --- | --- |
| **Spine** | Case for support → Prospect research → Application → Decision → Delivery → Monitoring → Evaluation |
| **Entities** | `grant_funders`, `grant_applications`, `grant_stages`, `grant_documents`, `grant_conditions`, `grant_reporting_periods`, `grant_impact_measures`, `grant_outcomes` |
| **Reference data** | Funder catalogue extending the `proj_ref_programmes` shape — NLHF, AHF, National Lottery Community Fund, community foundations, named trusts |
| **Seeded library** | Per application type: stages, standard tasks, required-document set, common conditions |
| **Registry** | Bid pack documents + monitoring returns per funder, statuses `required → drafting → review → final → submitted` |
| **Draftable docs** | `case_for_support`, `funding_application`, `monitoring_report`, `impact_evaluation` |
| **Exports** | Funder-facing one-page **impact card** (non-LLM, WeasyPrint, tenant accent on the header rule) |

### 1.1 Reuse map

| Groundwork asset | Reuse |
| --- | --- |
| `proj_ref_programmes` schema + staleness pattern | Direct — funder catalogue is the same shape |
| `funding_bid` skeleton (`prompts.py`) | Near-direct — becomes `funding_application` |
| `monthly_report` skeleton | Near-direct — becomes `monitoring_report` |
| `proj_conditions` | Pattern reuse — award conditions behave identically |
| `worker/health_card.py` WeasyPrint pattern | Pattern reuse — impact card |
| Gate mechanics + doc-status auto-flip | Direct |
| Vault RAG (read-only) | Direct — need evidence, beneficiary stories, past evaluations |

Estimated **60–70% reuse** post module-kit.

### 1.2 Derived analytics (pure functions, unit-tested, not stored)

Application success rate by funder and by size band · pipeline value weighted by stage ·
reporting-obligation calendar with overdue RAG · restricted-vs-unrestricted income split ·
funder concentration risk (share of income from the top funder).

---

## 2. Drafting workflows

Uses the common pipeline (gather → outline → sections → assemble → register) once §1.5 of the
roadmap generalises it. Same cost guard: ≤15 LLM calls, ≤24k tokens per call.

- **`monitoring_report`** — module data plus outcome measures for the reporting period. Funder
  requirements drive which sections appear. Figures render as real tables from
  `grant_impact_measures`, never from model output.
- **`funding_application`** — parameterised by the funder catalogue row. If catalogue
  `status != 'open'`, the draft carries the same first-page warning block Groundwork uses.
  Vault-grounded on need evidence and community support.
- **`case_for_support`** — vault-grounded, reusable across applications; the anchor document
  most applications derive from.
- **`impact_evaluation`** — end-of-grant, aggregates all reporting periods.

**Guardrails** (inherit `docs/groundwork-module-prd.md` §7 in full): draft-first with no
auto-submit; `[TO CONFIRM]` mandatory; vault-derived statements carry resolvable citations;
stale catalogue rows badge in UI and warn inside drafts; versions append-only; RLS plus
isolation tests before any feature code.

---

## 3. Commercial

**ICP.** Charities, CICs, community organisations and social enterprises with roughly
£100k–£3m income, plus the freelance bid writers and fundraising consultancies serving them.

**Channel.** Freelance charity bid writers charge £250–£400/day and are an organised,
addressable population (CIOF-affiliated consultancies, directories, registration schemes),
alongside infrastructure bodies — CVSs, community foundations, Locality, ACRE, NAVCA.

**Pricing.** Charity budgets are tight. £29/seat Core is defensible direct to charities;
£799/mo Managed is a stretch for a small charity but is the right price **to the
consultancies**, who run one branded workspace per client. Sell Managed to the channel, Core
direct.

**Estimate** (post module-kit): ~2,500 LOC, 1 migration, 2 worker jobs. **3–4 weeks solo,
~£5–7k** at £350–500/day. Cheapest module on the roadmap.

---

## 4. Risks

| Risk | Mitigation |
| --- | --- |
| Charity price sensitivity | Managed tier sold to consultancies, not charities |
| Funder catalogue maintenance | Same quarterly re-verification rule as `proj_ref_programmes`; staleness badges are load-bearing |
| Overlap with Groundwork's funding tab | Deliberate. Decide explicitly whether a tenant with both flags sees one funding surface or two, and record the ruling in ASSUMPTIONS.md before build — this is the first real cross-module design question the codebase has faced |
| "AI wrote our bid" reputational risk for charities | Draft-first plus `[TO CONFIRM]` already covers it; make the DRAFT watermark and the human-review step prominent in UI copy |

---

## 5. Out of scope for a first phase

Donor/CRM fundraising (individual giving, direct debits, Gift Aid) · finance integration or
restricted-fund accounting · a funder-facing portal · automated funder discovery/scraping ·
Charity Commission filing · impact measurement frameworks beyond simple measures against
targets.
