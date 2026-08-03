# Module Build Spec — Bid & Tender Operations ("Tenderhouse")
## Flowgrid OS · Vertical module · Mini-PRD

**Version:** 0.1 (mini-PRD) · 2 August 2026
**Status:** Researched and recommended, **not approved for build**. Needs the validation in
`docs/vertical-module-roadmap.md` §4 first — including one real competitor quote.
**Prerequisite:** The module kit (`docs/vertical-module-roadmap.md` §1), and ideally Grantwork
shipped first to de-risk the shared bid-drafting work.
**Feature flag:** `tenants.features->>'bids' = 'true'`.

---

## 0. Framing (read first)

Same working rules as `docs/groundwork-module-prd.md` §0. Restated where they bind:

1. **Additive only.** New tables prefixed `bid_`. Routes under `/api/v1/bids`. Frontend under
   `/app/bids`. The only core touchpoint is reading `tenants.features`.
2. **Where the repo's conventions differ from this spec, the repo wins.** Record divergences
   in `docs/groundwork/ASSUMPTIONS.md`.
3. **All reference data is seed data, never code.** The frameworks/portals catalogue carries
   `last_verified` / `next_review`.
4. **UK English** in all user-facing strings and generated documents.
5. Every mutation writes `audit_log` (actions namespaced `bids.*`); every LLM call writes
   `usage_events` kind `draft`.

**Product context.** UK SMBs selling into the public sector — facilities, security, care,
construction, IT, training — run 4–30 bids a year. Each is a fixed-deadline document assembly
job answering a buyer's question set, drawing on the same underlying material every time:
policies, accreditations, case studies, CVs, method statements, past winning answers. Today
that material lives in a folder, and the answer library is whoever has been there longest.

A single SME tender response costs **£1,500–£8,000** to produce; freelance bid writers charge
£300–£600/day. Unassisted win rates run around **20–35%**. Social value is now mandatory in
most tenders at **10–30% of the score**, yet a majority of bidders score under half the
available social-value points — a scoring gap that is directly addressable with better
evidence retrieval.

**The core loop that must feel magical:** *keep the answer library current → the next tender's
first draft assembles itself, with every reused claim traceable to where it came from.*

**Why the engine fits.** This is the closest structural match to Groundwork in the shortlist.
The vault is *already* an answer library; the document registry is *already* a per-question
status machine; the drafting pipeline *already* assembles cited documents whose tables come
from real rows.

---

## 1. The seven components

| Groundwork component | Tenderhouse equivalent |
| --- | --- |
| Stage-gated spine (Group→Site→Plan→Build→Live) | **Find → Qualify (bid/no-bid) → SQ/PQQ → ITT → Clarifications → Submit → Award/Debrief** |
| Typed document registry | The tender's **question set** — each question is a registry row with status `required → drafting → review → final → submitted` |
| Seeded content library per template | Seeded question sets per framework/portal type |
| `proj_ref_programmes` + staleness | **Frameworks & portals catalogue** — CCS, YPO, ESPO, NHS SBS, Find a Tender. Staleness matters identically |
| Vault RAG (read-only) | **The answer library** — past winning bids, policies, accreditations, case studies |
| AI-draftable docs | Per-question answer drafts; social value method statement; executive summary |
| Health-card PDF | **Bid/no-bid scorecard** — non-LLM, pure function over qualification fields |

**Entities** (`bid_` prefix): `bid_opportunities`, `bid_stages`, `bid_questions`,
`bid_answers` (append-only versions), `bid_tasks`, `bid_clarifications`, `bid_pricing_lines`,
`bid_outcomes` (award/loss plus debrief notes). Platform reference: `bid_ref_frameworks`,
`bid_ref_question_banks`.

### 1.1 Derived analytics (pure functions, unit-tested, not stored)

Win rate by framework, by buyer and by value band · answer-library coverage percentage (how
much of this question set can be served from existing material) · days-to-deadline RAG ·
social-value score exposure (weighting × unanswered questions).

Answer-library coverage is the module's signature number: it turns "should we bid?" from a
gut call into a computed one, and it feeds the scorecard.

---

## 2. Drafting workflows

Uses the common pipeline once roadmap §1.5 generalises it. Same cost guard: ≤15 LLM calls,
≤24k tokens per call.

- **Per-question answer draft** — retrieves from the answer library, drafts against the
  question's word limit and scoring criteria, cites the source bid or policy for every reused
  claim. The unit of work is the question, not the document.
- **Social value method statement** — the highest-value single draft given the scoring gap.
  Grounded on the tenant's own social-value evidence, not generic commitments.
- **Executive summary** — assembled last, from the finalised answers.

**Guardrails** (inherit `docs/groundwork-module-prd.md` §7, with two additions that matter
more here than anywhere else):

1. **No auto-submit, ever.** A missed or wrong submission is unrecoverable and contractually
   consequential. Draft-first is absolute.
2. **Reused claims must carry a resolvable citation to their source bid**, so a reviewer can
   check whether the claim is *still true* — accreditations lapse, staff leave, case studies
   age. This is the single most important correctness property in the module: the failure
   mode is not a hallucination, it is a true-in-2024 statement asserted in 2026.
3. `[TO CONFIRM]` mandatory; stale catalogue rows warn inside drafts; versions append-only;
   RLS plus isolation tests before any feature code.

---

## 3. Commercial

**ICP.** UK SMBs bidding into the public sector at 4–30 bids/year, plus the bid consultancies
and freelance bid writers who write for them.

**The price gap — the core commercial argument.** Incumbent tooling is enterprise-priced:
Loopio reportedly from ~$20k/yr, AutogenAI ~$30k/yr with a five-seat minimum, Responsive from
$5k/yr for five users. The SME layer beneath is thin (around £99/month). A £49/seat product
sits in an evidenced gap — **and none of the incumbents are white-label multi-tenant**, which
is the thing a bid consultancy actually needs.

**Channel.** The strongest single argument for this module. A bid consultancy runs one
Flowgrid workspace per client, branded as theirs, with the client's own answer library — which
is precisely the "sign a client → provision workspace → curate → bill monthly" motion in the
partner one-pager. Freelance bid writers at £250–£800/day are a large, directly addressable
population.

**Estimate** (post module-kit): ~3,000 LOC, 1–2 migrations, 2 worker jobs (answer draft,
scorecard PDF). **4–6 weeks solo, ~£7–10k** at £350–500/day.

---

## 4. Risks

| Risk | Mitigation |
| --- | --- |
| Most crowded market of the three (AutogenAI, Loopio, mytender.io, CleanTender) | Compete on white-label multi-tenancy and price, not on features. No incumbent serves the consultancy-with-many-clients shape |
| Competitor pricing figures are secondary-source | Get one real quote before this appears in any deck. Roadmap §4.3 |
| Stale reused claims asserted as current | Mandatory source citation per reused claim (§2.2) — treat as a correctness requirement, not a nicety |
| Question sets vary wildly by buyer | Seed question *banks* by framework, but make manual question-set entry first-class; do not assume portal parsing in phase one |
| Portal integrations look tempting | Explicitly out of scope — see §5 |

---

## 5. Out of scope for a first phase

Automated tender discovery or portal scraping (Find a Tender, Contracts Finder) · direct
portal submission · pricing/commercial modelling beyond a flat line table · e-signature ·
contract management post-award · consortium/multi-supplier bid workflows · automatic parsing
of buyer ITT documents into question sets (manual entry plus paste first; parse later once
real question sets are in hand).
