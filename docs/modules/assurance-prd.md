# Module Build Spec — Inspection & Assurance Readiness ("Assurance")
## Flowgrid OS · Vertical module · Mini-PRD

**Version:** 0.1 (mini-PRD) · 2 August 2026
**Status:** Researched and recommended, **not approved for build**. Build only after the module
kit has been proven by two earlier modules.
**Prerequisite:** The module kit (`docs/vertical-module-roadmap.md` §1).
**Feature flag:** `tenants.features->>'assurance' = 'true'`.

---

## 0. Scope boundary — read before anything else

This module handles **organisational assurance evidence only**: policies, audits, training
matrices, self-evaluation, improvement plans, mock-inspection findings, governance records.

It **does not** ingest care plans, patient records, pupil records or any individual
service-user data, and it must be **built so that it cannot**: no route accepts them, and the
document-type registry has no slot for them. This is a hard product constraint, not a
guideline — it keeps the module clear of NHS DSPT, IG Toolkit and clinical-safety (DCB0129)
obligations that would dwarf the build.

**Sequencing follows from that boundary.** Lead with **Ofsted-regulated education and
training providers** — independent training providers, early years settings, FE — which
involve no clinical data at all. Treat CQC-regulated adult social care as a phase-two
extension, and only after a DPIA and a DSPT assessment have been completed and recorded.

---

## 1. Framing

Same working rules as `docs/groundwork-module-prd.md` §0. Restated where they bind:

1. **Additive only.** New tables prefixed `asr_`. Routes under `/api/v1/assurance`. Frontend
   under `/app/assurance`. The only core touchpoint is reading `tenants.features`.
2. **Where the repo's conventions differ from this spec, the repo wins.** Record divergences
   in `docs/groundwork/ASSUMPTIONS.md`.
3. **All reference data is seed data, never code.** Regulator frameworks are versioned rows
   with `last_verified` / `next_review`.
4. **UK English** in all user-facing strings and generated documents.
5. Every mutation writes `audit_log` (actions namespaced `assurance.*`); every LLM call
   writes `usage_events` kind `draft`.

**Product context.** Regulated small providers live in a permanent state of inspection
readiness rather than a project. CQC is targeting 9,000 assessments by September 2026,
sharply raising inspection odds for small providers. Independent training providers face ESFA
funding-assurance reviews plus an Ofsted monitoring visit within 24 months of enrolling their
first apprentices — **with two days' notice**. Small care agencies already spend £100–£250/month
on software, but that software handles *records*; nothing handles *assurance*.

**The core loop that must feel magical:** *keep the evidence mapped → the self-evaluation and
the improvement plan assemble themselves, and you always know which statements you cannot
currently evidence.*

**Why the engine fits.** The gate-item model is an unusually exact match. A regulator's
framework is a tree of statements; "do we have evidence for this statement?" *is* a gate item
of kind `doc | task | manual` that auto-flips when a registry row reaches `final`. Groundwork
already implements exactly that mechanism.

---

## 2. The seven components

| Component | Assurance |
| --- | --- |
| **Spine** | Framework domains as stages (Ofsted EIF areas / CQC quality statements), each gated by evidence completeness |
| **Entities** | `asr_evidence`, `asr_evidence_links`, `asr_actions`, `asr_audits`, `asr_findings`, `asr_review_cycles` |
| **Reference data** | `asr_frameworks`, `asr_statements` — platform-level, versioned, select-only `using (true)` |
| **Registry** | Evidence documents mapped **many-to-many** onto statements (the one structural departure from Groundwork, where the mapping is one-to-one) |
| **Seeded library** | Per provider type: the framework's statement tree, a standard evidence checklist, a standard audit cycle |
| **Draftable docs** | `self_evaluation` (SEF), `quality_improvement_plan`, `provider_information_return`, `mock_inspection_report` |
| **Exports** | **Inspection-readiness card** — non-LLM, WeasyPrint, RAG per domain computed from evidence coverage |

### 2.1 Reference data is the module, and it is a commitment

`asr_frameworks` / `asr_statements` are not a one-off seed. Regulators change frameworks;
CQC's assessment approach has already shifted more than once. **A stale framework shown as
current is this module's worst failure mode** — worse than a bad draft, because the provider
acts on it.

Requirements: frameworks are versioned (never edited in place); every statement carries
`last_verified` / `next_review`; the `stale` badge is prominent rather than subtle; a draft
referencing a stale framework version carries a first-page warning block, as Groundwork does
for non-`open` funding programmes. Budget a standing quarterly review cycle as an operating
cost of the module, not a project task.

### 2.2 Derived analytics (pure functions, unit-tested, not stored)

Evidence coverage percentage per domain and overall · statements with no evidence (the "what
would we fail on tomorrow" list) · evidence age distribution · overdue actions RAG · audit
cycle completion.

---

## 3. Drafting workflows

Uses the common pipeline once roadmap §1.5 generalises it. Same cost guard: ≤15 LLM calls,
≤24k tokens per call.

- **`self_evaluation`** — the anchor document. Sections follow the framework's domains;
  every claim of quality must point at a linked evidence item or be marked `[TO CONFIRM]`.
- **`quality_improvement_plan`** — derives from uncovered statements and open findings;
  actions render as a real table from `asr_actions`, not from model output.
- **`provider_information_return`** — parameterised by regulator.
- **`mock_inspection_report`** — evidence coverage plus findings, written as an inspector
  would frame it.

**Guardrails** (inherit `docs/groundwork-module-prd.md` §7, plus one specific to this domain):

- **The module never asserts compliance.** It reports *evidence coverage* and what is missing.
  Draft language must not state or imply that a provider meets a standard; that is a judgement
  reserved to the regulator, and asserting it would be both wrong and a liability. Enforce in
  the system prompt and check it in the acceptance run.
- Draft-first, no auto-submit; `[TO CONFIRM]` mandatory; citations resolvable; versions
  append-only; RLS plus isolation tests before feature code.

---

## 4. Commercial

**ICP (phase one).** Ofsted-regulated independent training providers, early years settings and
FE providers. **Phase two, gated on a DPIA:** CQC-regulated adult social care.

**Channel — the strongest of the three modules.** Independent Ofsted and CQC compliance
consultants and mock-inspection firms are numerous and already sell exactly this service
manually. Franchise networks in care and childcare would take a branded workspace for their
franchisees, which is the Managed tier's ideal shape: one contract, many workspaces.

**WTP.** High. A poor inspection outcome is existential for a small provider — it affects
funding, contracts and insurability. Compare against existing spend of £100–£250/month on
software that does not address this at all.

**Estimate** (post module-kit): ~3,000 LOC, 2 migrations, 2 worker jobs, **plus meaningful
non-code effort curating framework reference data**. **5–7 weeks solo, ~£9–12k** at
£350–500/day, with the reference-data curation the least predictable part.

---

## 5. Risks

| Risk | Mitigation |
| --- | --- |
| Framework reference data goes stale | Versioned frameworks, prominent `stale` badges, warning block in drafts, standing quarterly review (§2.1) |
| Scope creep toward care records / pupil records | Enforce §0 structurally: no route, no doc type, no field accepts them. Re-state the boundary in the acceptance criteria |
| Module implies compliance it cannot assert | Explicit guardrail in §3; check it in acceptance |
| Curation effort under-estimated | Seed one framework only in phase one; add regulators one at a time, each with its own review cycle |
| CQC extension pulls in DSPT obligations | Phase two only, gated on a completed DPIA and DSPT assessment |

---

## 6. Out of scope for a first phase

Care planning, rostering, eLearning or LMS functionality · individual service-user or learner
records of any kind · direct regulator portal submission · multi-site or group-level
roll-ups · automated policy generation from templates · more than one regulator framework.
