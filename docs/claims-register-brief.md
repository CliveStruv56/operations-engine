# Claims Register Brief — one true place for what the tenant asserts about itself

## Flowgrid OS · Core primitive (unflagged) · Proposal

**Version:** 0.1 · 11 August 2026
**Status:** Proposed, **not approved for build**.
**Recommended timing:** inside the Tenderhouse sprint, built as **core** rather than
`bid_*`. See §9 — the window closes when Tenderhouse ships.
**Feature flag:** none. This is platform, like `documents` or `audit_log`.
**Prerequisite reading:** `docs/vertical-module-roadmap.md` §0.2 (the engine's shape),
`docs/modules/tenderhouse-prd.md` §0 (the answer-library framing this replaces),
`docs/groundwork-module-prd.md` §0 (working rules).

---

## 0. Framing (read first)

Same working rules as the module PRDs, restated where they bind:

1. **Additive only.** New tables prefixed `claim_`. Routes under `/api/v1/claims`.
   Frontend under `/app/claims`. No changes to core chat or vault behaviour.
2. **Where the repo's conventions differ from this brief, the repo wins.** Record
   divergences in `docs/groundwork/ASSUMPTIONS.md`.
3. **UK English** in all user-facing strings and generated documents.
4. Every mutation writes `audit_log` (actions namespaced `claims.*`); every LLM call
   writes `usage_events`.
5. **Draft-first holds throughout.** Nothing enters the register without a human
   confirming it. Nothing leaves a draft without a human reviewing it.
6. This is **not** a module. It carries no feature flag, because every vertical needs
   it and a tenant with no vertical modules still benefits.

---

## 1. The problem, in one story

A small charity — call it Riverside Community Trust — writes a National Lottery
application in March, bids for a council contract in May, and submits a monitoring
return to a two-year-old funder in July.

All three need the same facts: people served last year, annual income, trustee list,
what the safeguarding policy says, whether public liability cover is current, what
happened on the Meadow Lane project.

Today those facts live in someone's head, in last year's Word document, and in a
spreadsheet. Each time, a person digs them out and retypes them.

Here is the failure that costs money: **the figure that was true in the March
application is copied into the July report, where it is now eighteen months stale.**
Nothing was hallucinated. Nobody lied. A true statement simply outlived its truth.

`docs/modules/tenderhouse-prd.md` already names this as the module's critical
correctness property — *"the failure mode is a true-in-2024 statement asserted in
2026, not a hallucination."* That is a **platform** property, not a bid property.
Grantwork's case for support has the same failure mode. So does Assurance's evidence
mapping. So does a Groundwork feasibility study.

The claims register is one place where each fact lives once, with a date attached and
a document behind it.

---

## 2. What a claim is

A row with five load-bearing parts:

| Part | Example |
| --- | --- |
| **Statement** | "We supported 1,240 people in 2025/26." |
| **Evidence** | Link to the `doc_chunks` row on p12 of *Annual Accounts 2025-26* |
| **Owner** | The finance lead (a `memberships` row) |
| **Last verified** | 4 June 2026 |
| **Next review** | 4 June 2027 |

Typical claim types for a small organisation: registered identity, annual income,
headcount, people served, accreditations (Cyber Essentials, ISO 9001, safeguarding),
insurance cover and expiry, named policies with review dates, past contract values,
case studies, outcome statistics.

Expect **40–80 rows** per tenant. That is the whole of what a small organisation
repeatedly asserts about itself to the outside world.

---

## 3. How it gets populated

Four routes. Deliberately none of them is "sit down and fill in a form."

The design principle: **never ask the user to populate a database — ask them to
confirm or reject something already found.**

### 3.1 From public registers, automatically, on day one

The tenant enters a company number or charity number during setup. Companies House
and the Charity Commission both publish free public-register APIs. Registered name,
number, registered office, officers, incorporation date; for charities also income,
trustees, objects and filing history.

That is roughly **fifteen claims populated before anyone types a sentence**, each
already carrying a citation to an authoritative source and a review date tied to the
next filing.

This is the activation lever. Research gathered 11 Aug 2026 puts first-90-day churn
at 30–50% of all churn, with 44% of users abandoning when the first interaction
demands extensive data entry. **The register is never empty on the first screen.**

*Open:* exact API terms and key requirements for both registers need checking before
build. Both are believed free; neither has been verified against current terms.

### 3.2 From documents already in the vault

Ingest already parses uploads (Docling) into `doc_chunks`. When someone uploads annual
accounts, an insurance certificate or a safeguarding policy, the worker reads it and
**proposes** claims:

> "Annual income £847,000 — found on p12 of *Annual Accounts 2025-26*. Add?"

Proposed, never asserted. A human ticks yes or no — roughly ten seconds each — and the
evidence link is already attached because the source chunk is known.

### 3.3 Harvested from finished documents

Every bid, application and report the drafting engine produces contains claims. When
one is marked submitted, the engine scans it and offers what it finds:

> "This bid states you hold Cyber Essentials Plus. Add to the register?"

**This is the mechanism that makes the register grow as a by-product of work people
were doing anyway**, rather than as a maintenance chore that decays.

### 3.4 Typed in, on the spot

The residual case. Someone is mid-draft, hits a fact the register lacks, adds it there
and then.

---

## 4. What the user sees

A list. Filter, search, click a row for its evidence and history. Four states:

- **Verified** — checked recently, evidence attached.
- **Due for review** — review date passed. Still usable, flagged.
- **Unevidenced** — asserted by someone, nothing behind it.
- **Expired** — the insurance certificate ran out in April.

It is a register, not a dashboard. Dull on purpose.

---

## 5. How drafting uses it — the payoff

The mechanism already exists. `apps/api/app/crm/lookup.py::match_contacts` finds
relevant contacts and injects them into the chat prompt as a `contacts_block`. Claims
work identically: relevant claims are injected into the draft prompt as structured,
cited facts.

Three consequences:

**Drafts stop inventing.** The model is handed the income figure and the accreditation
list rather than guessing at them.

**Citations carry through to the finished document.** The engine already maps
`[c:<chunk_id>]` markers into DOCX footnotes and a data-sources appendix
(`apps/worker/worker/drafting/assemble.py`). Claims flow into that same machinery, so
a submitted bid shows *where each fact came from* — an unusual thing to be able to
hand a procurement officer.

**Stale claims warn before submission.** Groundwork already puts a first-page warning
block on a bid drafted against a non-`open` funding programme. Same treatment, same
place, same style: a draft leaning on an overdue or expired claim says so.

One sentence for the sales page:

> **Your workspace will not let you assert something you can no longer prove.**

---

## 6. How it stays true

Every claim carries a review date, defaulted by type — insurance to its expiry, income
to the next filing, policies to their stated review cycle, case studies annually.

Overdue claims surface in the weekly digest (approved 11 Aug 2026, tenant users only):

> "Four claims need checking. Your public liability cover expired on 12 April."

This is the `last_verified` / `next_review` staleness pattern already running on
`proj_ref_programmes` and `grant_ref_funders`. No new mechanism — an existing one
pointed at a new table.

---

## 7. Worked example, end to end

**September.** Riverside signs up, enters its charity number. Eleven claims populate
from the public register.

**Same week.** Eight documents go into the vault — accounts, policies, two old bids.
The worker proposes thirty-one more claims. Twenty minutes of ticking. The register
now holds forty-two verified facts, each cited.

**October.** A National Lottery application is drafted. Income, beneficiary numbers,
trustee list and two case studies come straight from the register, cited. Drafting
time falls because nobody is hunting for numbers.

**January.** A council tender. Different module, same forty-two facts, plus the
accreditations and insurance the tender asks for. Nothing retyped.

**April.** The digest flags public liability expiring in three weeks. Renewed,
certificate uploaded, claim re-verified against the new document.

**July.** The funder monitoring report is drafted. It uses the **current** beneficiary
number, not January's — because the register was updated in between and the report
reads from the register, not from the old bid.

That last paragraph is the whole value proposition.

---

## 8. Why it is a moat

**It is the shared spine under all three planned verticals.** Tenderhouse's answer
library, Grantwork's case-for-support facts and Assurance's evidence statements are
the same table wearing three hats. Built once, the other two get cheaper.

**The UK register seeding is not worth copying for a US-built competitor.** Companies
House and the Charity Commission are free, high-quality and specific to this market.

**It explains itself to a non-technical buyer in one sentence**, which matters when
the top barrier to UK SMB adoption is skills rather than budget (60% cite limited AI
skills; see §11).

---

## 9. Why it must be built as core, and why now

Tenderhouse's PRD makes the vault the answer library and each **question** a registry
row. Built as `bid_answers`, roughly 70% of it is then rebuilt for Grantwork's case
for support and again for Assurance's evidence statements.

Built instead as an unflagged core table that Tenderhouse *consumes* as its answer
library, the marginal cost inside the sprint is on the order of **two days**, and both
later modules inherit it.

The window closes when Tenderhouse ships. Retrofitting a core primitive underneath a
shipped module means a migration against live tenant data.

---

## 10. What this is deliberately not

- **Not a CRM.** The `contacts` module is about other people. This is about the tenant
  itself.
- **Not a document store.** It points at vault documents; it does not hold them.
- **Not automatic.** Nothing enters without a human tick; nothing leaves a draft
  without human review.
- **Not a compliance claim.** It records what can be evidenced. It never asserts
  compliance with anything — which keeps it on the right side of the line drawn for
  Assurance in `docs/modules/assurance-prd.md`.
- **Not a policy generator.** Automated policy generation is an explicit Assurance
  exclusion and stays excluded here.

---

## 11. Source notes

Market figures below are **secondary sources gathered 11 August 2026** and carry the
same caveat as `docs/vertical-module-roadmap.md` §4.3: none may enter an investor deck
without one real corroborating quote.

- First-90-day churn 30–50% of total; 44% abandon on extensive first-run data entry —
  AMW customer-onboarding statistics 2026.
- Median gross revenue retention ~40% for AI-native companies vs ~63% B2B SaaS —
  Userpilot, 2026.
- 60% of UK businesses cite limited AI skills/expertise as the top adoption barrier —
  techUK / ANS–YouGov, 2026.
- SME shape requirement (configurable to workflow, reliable unsupervised, maintainable
  by a non-specialist) — BCS, *The AI adoption gap*, 2026.

---

## 12. Open questions before build

1. **Register API terms** — Companies House and Charity Commission: free? key
   required? rate limits? (§3.1)
2. **Claim granularity** — is "annual income" one claim re-verified yearly, or one
   claim per financial year? The monitoring-report case in §7 suggests the former with
   history; confirm against Tenderhouse's per-question shape.
3. **Ownership when a member leaves** — claims owned by a deleted membership need a
   reassignment path.
4. **Extraction cost** — §3.2 and §3.3 are LLM calls. They need their own
   `LlmLedger` budget and a `usage_events` kind, decided before build.
5. **Whether Tenderhouse questions are claims or reference them.** A question-and-
   answer pair is not the same shape as an atomic fact. Most likely: questions live in
   `bid_*` and cite claims. Needs settling in the Tenderhouse spec, not here.
