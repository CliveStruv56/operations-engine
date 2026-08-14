# Feature Build Spec — Fetch a funder's form from its URL ("Form fetch")
## Flowgrid OS · Feature on the question-set surface · Mini-PRD

**Version:** 0.1 (mini-PRD) · 12 August 2026 · **Built 14 August 2026** (approved same day)
**Status:** Shipped as specced: `POST /api/v1/question-sets/fetch` (Exa contents-by-URL,
so the user's address is never dereferenced from inside our network — the §2.4 SSRF
surface never existed to defend), a fetch row above the transcribe paste box shown only
with `web_search`, per-fetch `usage_events` metering, a per-tenant rate limit
(`FORM_FETCH_RATE_LIMIT_PER_HOUR`, default 20/hr — platform Exa key, same reasoning as
register lookups), truncation at the paste box's 24k cap surfaced rather than silent,
and the fetched URL pre-filling the required source-URL save field (§1's papercut).
§3 held: fetch pre-fills the box; review, transcribe and save are unchanged. §5's
out-of-scope list is untouched. Originally raised by a pilot user on 12 Aug after
transcribing a form by hand.
**Prerequisite:** Question sets, shipped 11 Aug (`app/refdata/`, `/app/forms`).
**Feature flag:** reuse `tenants.features->>'web_search'` — the same egress and the
same commercial boundary. No new flag.

---

## 0. Framing (read first)

Same working rules as `docs/groundwork-module-prd.md` §0. What binds here:

1. **Additive only.** One new route on an existing router
   (`/api/v1/question-sets/fetch`), one new field in the transcribe panel. No new
   table: a fetch produces the same proposal the paste box already produces.
2. **This is an assist, not an automation.** The output lands in the review step
   that already exists. It never saves a question set on its own — see §3.
3. Where this spec and the repo differ, the repo wins; record it in
   `docs/groundwork/ASSUMPTIONS.md`.

---

## 1. Why this is cheap

Both halves already exist, which is the whole argument for building it.

| Half | Already built | Left to do |
| --- | --- | --- |
| Prose → structured questions with limits | `POST /api/v1/question-sets/transcribe` (`app/refdata/transcribe.py`) | Nothing — it takes text and does not care where the text came from |
| URL → page text | Exa integration in `app/search.py`, already requesting `contents.text` | Call the contents-by-URL endpoint instead of search |

The new code is a route that fetches text, passes it to the existing transcriber,
and returns the existing proposal shape — plus a URL input beside the textarea in
`transcribe-panel.tsx`. **Roughly a day** to a working version.

It also closes a real papercut. The source URL is a required save field that users
forget, because they copy the form's *text*, not the page's address. A fetched set
knows where it came from.

---

## 2. Where the cost actually is

None of these are code problems, and all of them decide whether the feature is
worth having.

1. **Many funder forms are not web pages.** PDFs, Word documents, or a portal
   behind a login. Exa reads HTML. PDFs could route through the Docling path the
   vault already uses — more plumbing, still feasible. Login-gated portals are
   unreachable and always will be.
2. **A "how to apply" page is often not the questions.** It is eligibility prose,
   deadlines, and a link to the real form. Extraction quality swings by funder, and
   the failure is quiet: a plausible question set that is not the form.
3. **Limits usually live in a different document from the questions.** The fetch
   that finds the questions commonly misses the counts — the exact gap that makes a
   set useless for sizing answers (`docs/funder-forms-guide.md`, "Limits are the
   point").
4. **Server-side fetching of user-supplied URLs is an SSRF surface.** In a
   multi-tenant app whose API sits on Railway's private network, an unvalidated
   fetch reaches `postgres.railway.internal`. Needs scheme and host validation, a
   private-range denylist, no redirect following to private space, and a timeout.

---

## 3. The shape that is safe

**Fetch pre-fills the paste box. Nothing else changes.**

The user presses "Fetch", the text arrives in the textarea they already know,
and they press "Read the questions" as they do today — landing in the same
review-and-correct step, with the same unverified caveat on save.

This matters more than it sounds. The unverified state is only meaningful because
a human has looked; a pipeline that fetches, transcribes and saves unattended
produces official-looking sets nobody checked, which is worse than an empty list.
The same reasoning already governs the catalogue: real funder sets are transcribed,
never seeded.

It also degrades well. Where a funder publishes a PDF or hides behind a portal, the
fetch fails, the user pastes manually, and they are exactly where they are today —
no worse.

---

## 4. Risks

- **Quiet wrong extraction.** A confident question set built from the wrong page.
  Mitigated by review-before-save, and by keeping the fetched URL visible.
- **Funder terms of service.** Some prohibit automated retrieval. Worth a check
  before this is sold as a feature rather than used internally.
- **Per-fetch cost.** Exa contents calls are metered; needs the same cost telemetry
  as every other outbound call (hard constraint 5).
- **Expectation drift.** "It reads the funder's site" is easily heard as "it applies
  for me". The guide's first line exists for this reason.

---

## 5. Out of scope for a first phase

- PDF and Word form fetching (route through Docling later if demand is real).
- Anything behind a login.
- Crawling a funder's site to *find* the form page — the user supplies the URL.
- Watching a URL for changes and re-transcribing. Tempting, and the natural home
  for the staleness the verified flag already tracks, but it needs the fetch to be
  reliable first.
- Auto-saving without review. Not a phasing decision — see §3.
