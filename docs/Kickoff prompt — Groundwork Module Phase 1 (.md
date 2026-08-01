@# Kickoff prompt — Groundwork Module Phase 1 (send with groundwork-module-prd.md)

You are building Module Phase 1 of "Development Projects (Groundwork)" for the
Operations Engine — a live, multi-tenant production SaaS. The complete
specification is in `groundwork-module-prd.md` (attached). Treat the PRD as the
single source of truth for SCOPE; treat the repo as the single source of truth
for CONVENTIONS.

BEFORE WRITING ANY CODE
1. Read the PRD end to end — especially §0 (working rules) and §8 (out-of-scope).
2. Explore the repo and locate every primitive listed in PRD §0.1 (RLS/tenancy
   helper, worker queue, R2 helpers, LiteLLM client, vault retrieval,
   audit/usage writers, API client generation).
3. Reply with a short ORIENTATION REPORT before any code: the file paths of each
   primitive you found · the LiteLLM alias names actually in the live config ·
   anything in the repo that contradicts the PRD · your Week 1 plan. Wait for my go.

WORKING CADENCE — one milestone at a time (PRD §10)
- Execute the current week only. Hard stop at each proof point. Do not start the
  next week until I say go.
- Show me at each checkpoint:
  • W1: migration files · RLS policies · isolation test output (green run) ·
    seed loader run showing exact counts (5 stages / 64 tasks ±applicability /
    32 docs / 10 risks) · a POST /projects request/response transcript.
  • W2: screen-by-screen walkthrough (screenshots), including gate sign-off
    blocked→exceptions→doc-auto-flip behaviour and the dormant-with-reason flow.
  • W3: the three generated DOCX files from the demo project · the usage_events
    cost rows · the citation resolution log for the feasibility study.
  • W4: the full §9 acceptance checklist annotated pass/fail with evidence ·
    the pilot onboarding runbook.
- Every checkpoint report contains: what you built · decisions & assumptions
  (with the ASSUMPTIONS.md diff) · test results · open questions (max 5, each
  with your recommended answer).

WHEN THE REPO DIVERGES FROM THE PRD
The repo wins. Log it in docs/groundwork/ASSUMPTIONS.md. If the divergence is
material (schema patterns, auth flow, alias names, queue mechanics), PAUSE and
flag it in your next message rather than improvising a workaround.

NON-NEGOTIABLES
- Additive only: no changes to core tables, routes or behaviour.
- Every proj_* table has RLS + a passing isolation test BEFORE feature code
  touches it.
- All model calls via the existing LiteLLM aliases with the tenant's key —
  never direct provider SDKs.
- Generated drafts never leave status "drafting" without a human action.
- Nothing from the PRD §8 out-of-scope list, however tempting.
- New dependencies limited to python-docx and WeasyPrint unless you clear a
  licence-checked addition with me first.

Definition of done is PRD §9, demonstrated in STAGING — not "works locally".

Begin with the orientation report.
