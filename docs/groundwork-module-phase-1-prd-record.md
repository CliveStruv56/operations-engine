# Groundwork Module — Phase 1 PRD (Record)

Project record of the Development Projects ("Groundwork") module Phase 1 PRD handed to the coding agent: scope, integration contract with the live Engine core, seed content summary, acceptance criteria and 4-week milestones. Canonical handoff artifact: groundwork-module-prd.md (file cms6h6r3705pa06adxhntffsy).

## Purpose & Status

**What this is:** the record of the Module Phase 1 PRD for **Development Projects (codename Groundwork)** — written 29 Jul 2026 for an LLM coding agent to build the §11A Level B MVP as an integration on the **live Operations Engine core** (Clive confirmed core complete, 29 Jul 2026).

**Canonical handoff artifact:** `groundwork-module-prd.md` — file id `cms6h6r3705pa06adxhntffsy` (thread `cms4sjd4x0xmx07addvt28aqt`). Paste that single file into the coding agent; it is fully self-contained. Companion docs are referenced inside it but not required to build.

**Trigger:** design partner #1 secured — a development consultancy wanting the full application with this module as part of the AI Engine. Proceeding at 1 partner (original gate was 2) — Clive's call, recorded in the project doc.

**Scope (locked to §11A of `cms4tc4de0l8i08ad8e17ucwf`):** 9 tenant tables + 2 reference tables · 1 template (CLH new-build) · 3 drafting workflows (monthly client report · feasibility study · parameterised funding bid) · portfolio + 9-tab project room · planning conditions tracker · flat 10-programme funding catalogue · health-card PDF · full guardrails. Explicit non-goals restated in the PRD (no Gantt, portal, scheduler, appraisal engine, Stripe changes).

## PRD Contents Summary

**§0 Agent working rules** — read the repo first; repo conventions win (divergences logged in ASSUMPTIONS.md); additive-only; feature flag `tenants.features.projects`; audit/usage on everything; seed data never code; MIT/Apache/BSD deps only (adds python-docx, WeasyPrint).

**§1 Data model** — full DDL: `proj_projects`, `proj_stages` (gate checklist JSONB with doc-kind items auto-flipping from registry status), `proj_tasks` (milestones flagged, statutory/funding/planning tags), `proj_documents` (registry with append-only versions), `proj_budget_lines`, `proj_funding_sources` (drawdown schedule JSONB), `proj_risks`, `proj_conditions` (pre-commencement flag), `proj_stakeholders` — all with the core's exact RLS pattern — plus platform-scoped `proj_ref_templates` and `proj_ref_programmes`. Portfolio RAG is a documented pure function (programme/cost/risk), not stored state.

**§2 Seed content** — CLH new-build template v1: 5 stages with gate checklists; 64-task library (Group 8, Site 12, Plan 18, Build 14, Live 12) with applicability effects (Wales→SAB task, HRB→banner+task, BNG-exempt→skip, conservation→heritage task); 32 document types (3 AI-draftable); 10-risk failure-mode library with default mitigations; 10-programme funding catalogue verified 28 Jul 2026 (SAHP CME, CRtB Fund [announced], AHF viability + development, NLHF £10k–250k, Booster equity match, ACRE halls, Ecology lending, Scottish RIHF, Cwmpas) with last_verified/next_review dates.

**§3–4 API & frontend** — `/api/v1/projects` surface in core conventions; `/app/projects` portfolio + project room (Overview, Stages & Gates, Tasks, Documents, Funding with catalogue browser, Budget, Risks, Conditions, Stakeholders); draft modal with draft-first messaging.

**§5 Drafting workflows** — common 5-step worker pipeline (gather → outline → sectioned drafting → python-docx assembly with citation footnotes + data-sources appendix → register at status *drafting*); drafter/reasoner aliases only; [TO CONFIRM] no-invention convention; 15-call/24k-token cost guard (≈$0.05–0.15/draft); per-workflow skeletons (10-section monthly report · vault-grounded feasibility · programme-parameterised bid with staleness warning). Health card = one-page WeasyPrint PDF, no LLM.

**§6–8 Integration contract, guardrails, out-of-scope reminders** — read-only expectations on core (auth/tenancy, vault retrieval, aliases, writers, theming); six product-requirement guardrails; "do not helpfully add" list.

## Acceptance & Milestones

**Acceptance highlights (full list in the PRD §9):** isolation suite extended to all module endpoints · flag-off = 404 + hidden nav · seeding counts exact and idempotent · gate mechanics incl. doc-kind auto-flip · monthly report: 10/10 spot-checked figures traceable, zero invented content · feasibility: ≥5 resolvable vault citations · bid against an announced programme carries the status warning · health card one page, branded · **exit demo: pilot consultancy live, 1–2 real projects entered (≤90 min each), first real monthly report generated within 15 minutes of data entry completing**, §11A pilot metrics being tracked.

**Milestones (4 weeks):** W1 schema + RLS + seeds + create-project E2E · W2 portfolio + project room CRUD + gate mechanics · W3 the three drafting pipelines + DOCX assembly + registry integration · W4 health card, staleness badges, polish, acceptance run, pilot onboarding. Estimate ~£6–8K at established freelance rates; marginal run-cost ≈ $1.70/module seat/month.

**Standing cautions carried into the PRD:** funding programme facts are snapshots (verified 28 Jul 2026, next review 28 Oct 2026); LiteLLM alias names to be confirmed against the live config; repo reality beats spec assumptions.
