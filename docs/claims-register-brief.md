# Claims Register Brief — one true place for what the tenant asserts about itself

## Flowgrid OS · Core primitive (unflagged) · Built

**Version:** 0.2 · written 11 August 2026, status updated 12 August 2026
**Status:** **BUILT.** Approved 12 Aug 2026 and delivered in four commits —
`cef54ce`, `9fea88c`, `be4e8e4`, `0d85908`. §13 says what each one covers.
§12's open questions are all settled, and the rulings live in
`docs/groundwork/ASSUMPTIONS.md` **#30–#43**, not here.

**Two follow-ups are proposed and NOT built — see §14.** Read that section
before starting either: both exist to avoid a specific failure, and one of them
has no infrastructure to build on.

**Original timing note (now historic):** inside the Tenderhouse sprint, built as **core** rather than
`bid_*`. See §9 — the window closes when Tenderhouse ships. It was built ahead
of Tenderhouse instead, which satisfies the same argument.
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

---

## 13. What was built (12 August 2026)

Four commits, each independently green. Branch `claims-register`, off `main`.

| Commit | What |
| --- | --- |
| `cef54ce` | The register itself. Migration **0016** (`ref_claim_kinds`, `claims`, `claim_revisions` + RLS), the claim-kind fixture and seeder, `app/claims/` (schemas, three register clients, service), `/api/v1/claims` incl. three import routes, `/app/claims`, the settings section, isolation coverage |
| `9fea88c` | Claims reach the four organisation sections. `Section.uses_claims`, `<organisation-claims>` block, `claims`/`claim_excerpts` on `DraftPackBase`, the excerpt merge in the engine, stale-claim warning joined onto each module's `warning_block` |
| `be4e8e4` | Form pre-fill. `worker/drafting/prefill.py`, partition before `plan_calls`, `AnswerOut.origin`/`claim_ids`, "From your register" stamps and the sheet header count |
| `0d85908` | Extraction and harvesting. Migration **0017** (`usage_events.kind = 'extract'`), `worker/claims/extract.py` + `harvest.py`, the ingest hook, the submit trigger, `disown_claims` on member removal |

**Jurisdictions.** Companies House, the Charity Commission for England and
Wales, and **OSCR (Scotland)** are all live. Terms were verified on 12 Aug
2026: all three are free, all three publish under the Open Government Licence,
and the OGL attribution duty is discharged by the register provenance line in
the Data sources appendix plus a credit on `/app/claims`. Companies House
allows 600 requests per five minutes **per application**, which is why
`register_lookup_rate_limit_per_hour` exists — it is the only rate limit in the
codebase whose job is protecting other tenants rather than us.

**Northern Ireland (CCNI) is deliberately not built.** It has no per-charity
JSON API, only a CSV export, so it needs an operator-refreshed
`ref_ni_charities` snapshot rather than a live lookup — a different shape from
the other three. The UI says so plainly rather than letting an NI charity
discover it by failing. Roughly half a day if wanted.

**Outstanding before Scotland works in anger:** the OSCR key is issued on an
approval request rather than self-serve, so it has lead time. And the OSCR API
predates the 9 March 2026 register change that put trustee names on the
Scottish Charity Register — whether they are in the *API payload* (as opposed
to the web entry and the daily CSV) needs confirming against a live response
before trustee auto-fill is promised to a Scottish client. The client already
treats trustees as an optional block for that reason.

---

## 14. Proposed follow-ups

Both were asked for on 12 Aug 2026. **§14.1 step 1 and all of §14.2 are now
built** (branch `claims-summary-badge`, ASSUMPTIONS #44 and #45).

> **Steps 2 and 3 built, 14 Aug 2026.** The infrastructure decision they were
> blocked on was taken once, deliberately: **Resend** as the platform email
> transport (plain httpx, no SDK; empty key = disabled; `app/email.py` with a
> deliberate worker mirror in `worker/email.py`) and **arq `cron_jobs`** as
> the scheduler. Step 2: a daily 06:10 UTC sweep (`worker/claims/sweep.py`,
> tenant discovery via the owner-run `claims_sweep_tenants()` in migration
> 0020) writes `claims.review_due` to `audit_log` at most once per tenant per
> 7 days; `claims.%` was added to `FEED_PATTERNS` (the trap named below).
> Step 3: a Monday 07:00 UTC digest to admins/owners, worst-first and capped
> at ten lines, with a per-member preference (`memberships.digest_opt_out`)
> and a signed pause/resume link served by `/api/v1/email/digest` — GET
> confirms, POST acts, so a mail scanner's prefetch changes nothing. The same
> transport now sends invite emails; the invite response carries `email_sent`
> so the UI never pretends. The rule held: both consumers trigger on
> needs-attention claims only.

### 14.1 Surfacing overdue claims on a regular basis

> **Step 1 shipped, 12 Aug 2026.** `GET /claims/summary` returns
> `{needs_attention, stale, expired, proposals}` — four numbers rather than the
> two specified below, because two cannot name *which* problem somebody has
> (ASSUMPTIONS #44). It is counted in Postgres in one round trip, carried on the
> workspace context beside projects and conversations (so it refreshes on tab
> focus, which matters for a count that changes at midnight with nobody
> touching anything), and shown as a badge on the sidebar's "Your organisation"
> item: `needs_attention + proposals`, labelled "1 lapsed, 1 past review, 3 to
> check", and warn-coloured only when something has actually gone off. The
> register screen refreshes it after every confirm, reject, check and import.
> **Steps 2 and 3 below are unchanged and unbuilt** — re-verified on 12 Aug
> 2026 that the codebase still has no scheduler and no email transport.

**The gap.** §6 of this brief assumed a weekly digest would carry the "four
claims need checking" line. **No digest infrastructure exists anywhere in the
codebase** — no scheduler, no email transport, no template, no user preference.
So today an overdue or expired claim is visible in exactly two places, both of
which require somebody to already be looking: the register screen, and the
first page of a draft that leans on it.

That is the wrong way round. The whole value proposition in §7 is the July
monitoring report using the *current* beneficiary number — and a fact only gets
updated if somebody is told it has gone off **before** they need it.

**What to check first, because it changes the shape.** Search for a scheduler
and an email transport before designing anything. As of 12 Aug 2026 there is
neither: arq runs jobs enqueued by the API, not on a cron, and nothing in the
codebase sends email except Supabase's own auth flows. Confirm that is still
true — if a digest has since been built for something else, this becomes a
query and a template rather than a piece of infrastructure.

**Recommended shape, cheapest first.** Three steps, each shippable alone:

1. **In-app, always visible (half a day).** A count on the sidebar's "Your
   organisation" item, the same way an inbox shows unread. Needs
   `GET /claims/summary` returning `{needs_attention, proposals}` — cheap,
   indexed by `claims_review_idx`, and it makes the register self-announcing
   without any new infrastructure. **Do this one first regardless**, because it
   is the only step with no dependency and it is what makes the other two
   optional rather than essential.
2. **A scheduled sweep (one to two days).** An arq cron job — arq supports
   `cron_jobs` alongside `functions` in `WorkerSettings`, so this needs no new
   dependency — running daily, per tenant, collecting claims where
   `next_review <= today or expires_on < today`. It writes an `audit_log` row
   (`claims.review_due`) so the tenant activity feed carries it. Note
   `FEED_PATTERNS` in `app/modules.py` currently only surfaces module
   namespaces (`projects.*`, `grants.*`), so `claims.*` must be added there or
   the row is written and never shown — that is the easy thing to get wrong.
3. **Email, only if steps 1 and 2 are not enough (two to three days plus a
   decision).** Requires choosing a transport, a sender domain, an
   unsubscribe path and a per-user preference. That is a platform decision
   well beyond this feature, and it should not be smuggled in under it.

**The rule that must hold.** Whatever surfaces this must count only claims that
are *actually* a problem, never "you have eighty facts". `claims_warning` in
`worker/claims/facts.py` already follows that rule and ASSUMPTIONS #43 records
why unowned claims are excluded from attention counts for the same reason: a
warning that is always there is not read.

### 14.2 Telling people when a departing member's claims are released

> **Built, 12 Aug 2026 — and the caveat below was settled against adding the
> column (ASSUMPTIONS #45).** Two findings this section did not know: ownership
> was unreachable from the UI (nothing in `apps/web` ever sent
> `owner_membership_id`, so *every* claim was unowned and the filter would have
> matched everything), and an owner could not be cleared (`is not None` meant
> null read as "unchanged"), so the only owned→unowned path was removing the
> person.
>
> **The ruling: no `owner_lost_at`.** The second finding makes it cheap, so cost
> is not the reason — meaning is. A claim that lost its owner is not a fact that
> has gone off; its content is still true, so it cannot join `needs_attention`
> without wrecking a count that means "this may be false", and a permanent
> number of its own is the badge nobody reads. It stays reversible: `audit_log`
> holds every `member.remove` with its count, so the column can be added and
> backfilled if a pilot user asks to be chased.
>
> **What shipped instead:** an owner picker on every confirmed row (with
> `ClaimPatch.owner_membership_id` the one field in the codebase where an
> explicit null means "clear it"), an opt-in `?owner=none` view that Settings
> links straight to, `DELETE /members/{id}` answering **200 with
> `{claims_disowned: N}`** rather than 204, and a removal notice naming the
> count with a link to reassign. `_check_owned_membership` closes the same
> RLS-bypassed foreign-key hole as `_check_owned_document`.

**What happens today.** `disown_claims` (`app/claims/service.py`) nulls
`owner_membership_id` on every claim the removed member owned, and the count
goes into the `member.remove` audit meta as `claims_disowned`. That is a
complete audit trail and **nobody is told**: `member.*` is not in
`FEED_PATTERNS`, so it never reaches the tenant activity feed, and the register
screen shows the claims as ordinary confirmed facts with no owner.

**What was asked for.** Two things, and they are different:

1. **Visible when somebody opens the register.** An "unowned" filter or badge
   on `/app/claims`, so the facts nobody is responsible for are findable.
   Straightforward: `owner_membership_id` is already on `ClaimOut` and the web
   type. The only real decision is whether to show it always or only for claims
   that *lost* an owner — see the caveat below.
2. **Proactively told.** The admin who removed the member is the right
   audience and the moment of removal is the right time, because it is the only
   moment they can reassign. `DELETE /members/{id}` currently returns 204 with
   no body, so this needs either a response body (a contract change) or a
   follow-up toast driven by re-reading the audit row.

**The caveat that shapes it.** ASSUMPTIONS #43 records why unowned claims are
*not* counted as needing attention: ownership is optional, most claims never
have an owner, and counting them would put a permanent warning on every
workspace. So "show me unowned claims" is a filter people opt into, not a
badge — **unless** the schema learns to distinguish "never had an owner" from
"lost its owner". That distinction does not exist today (`on delete set null`
erases it) and adding it means either a nullable `owner_lost_at` column or
reading it back out of `audit_log`. Settle that before building either half,
because it decides whether this is a filter or an alert.

**Recommended:** add the filter (half a day), change the 204 to return
`{claims_disowned: N}` and show it in the removal confirmation (half a day),
and only add `owner_lost_at` if a pilot user actually asks to be chased about
it.
