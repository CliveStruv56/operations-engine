# Flowgrid OS enhancement plan (Nov 2026)

Status: **approved to start, 6 Nov 2026.** Stages 1 and 2 can begin now. Two of
the three decisions that gate stage 3 are agreed (see "Decisions"): the "no agent
tools" rule is lifted for draft-first tools ([ASSUMPTIONS #72](groundwork/ASSUMPTIONS.md)),
and Claude is the frontier model ([ASSUMPTIONS #73](groundwork/ASSUMPTIONS.md)).
Pricing is still open.

Inputs:
- `docs/kylon-comparison.md` — what Flowgrid can learn from Kylon (6 Nov 2026).
- The "App UI and design review" session (17–26 Oct 2026, PRs #11–#15) — its
  findings, checked against the code on 6 Nov, are folded into stage 2 below.

Working rules for implementation sessions:
- Read `CLAUDE.md` first. Hard constraints still apply, except the two decisions
  above, which are recorded as divergences in `docs/groundwork/ASSUMPTIONS.md`.
- One or two item IDs per session and per PR. Put the ID in the PR title, e.g.
  `F4: split chat.tsx`. Keep commits small and commit on green.
- Every new table ships with RLS **and** a test in `apps/api/tests/test_isolation.py`.
- Anything that departs from this plan or the spec gets an ASSUMPTIONS entry.
- When an item ships, tick it here and note the PR.

## The plan in brief

Goal: turn Flowgrid from a tool that answers and drafts into one that also does
routine work, **with a person releasing every action**. Keep the cited, metered,
UK-trustworthy character that sets it apart from Kylon.

| Stage | Weeks | Theme | Gate to the next stage |
| --- | --- | --- | --- |
| 1 Foundations | 1–2 | See the running app; injection fix; split chat; model test; card component | **A:** F2 and F5 done; tools and model decisions made |
| 2 First hour and finish | 3–8 | Setup guide, guidelines, playbooks, workspace report; finish the UI review | **B:** a pilot user reaches a first useful draft within an hour, unaided |
| 3 The action loop | 9–14 | Approval cards, automations, learned preferences, threads | **C:** 50 cards handled with no wrong write; automations live in two pilots |
| 4 Reach | 15–20 | Mail and calendar (draft-first), read-only MCP server, custom registers, installable app | — |

Timings assume the recent pace (five PRs merged on 26 Oct) and are a guide,
not a commitment. Effort below is in working days for one person with coding agents.

## Principles

1. **Draft first.** The AI may propose any change; a person releases it. Nothing
   reaches a funder, a client or an inbox without a click, enforced server-side.
2. **Cited or quiet.** Statements about the organisation cite a document page or
   a confirmed claim, or say they can't.
3. **Every call metered.** Automations, playbooks and Claude calls appear in
   usage with their cost and stay under the soft and hard caps.
4. **Isolation before features.** RLS plus an isolation test for every new table.
5. **One card.** A single card component for setup questions, confirmations and
   proposed actions.
6. **Plain and readable.** Plain names, 12px floor, no colour-only status,
   keyboard reachable — new screens meet the UI review's standard from the start.
7. **No growth hacks.** No share-for-credits, hidden background processes or
   invented value figures.

## Where Flowgrid starts (open items from the UI review)

Shipped in PRs #11–#15: contrast (`--faint` #585f5f, `--edge-ui`), 12px floor,
plain names, one Projects list with stored kinds, a page for every project,
sidebar cap, Usage and Settings in the main nav. Still open (each mapped to an
item below):

- **Type:** 204 one-off `text-[Npx]` sizes, ~105 spaced-capital labels, heavy
  chrome weights, chat answers ~90 characters wide, bone hairlines 1.25:1 → P8.
- **Navigation:** project scope lost between pages (and chats saved with
  `project_id: null`); no H1/`<main>` on Chat and Documents; overlapping active
  states; tabs not in the URL; palette has no "Go to" and shows ⌘K on Windows;
  no chat history page; `/admin` not linked either way; footer shows role not
  name; counts without a legend; Contacts' own module-off message → P6.
- **Accessibility:** no live region for streamed answers; citation [n] opens all
  sources (`chat.tsx:200`); RAG dots, claims badge and ★ rely on colour; palette
  has no focus trap or listbox; mobile drawer lacks Escape/`aria-expanded`;
  nine hand-rolled buttons; two amber primaries possible; Vault delete-swap
  loses focus → P7.
- **First use and chat:** no example prompts or checklist; empty states without
  a next step; raw model name, cost never shown; web-only answers get the
  grounded badge; "0 documents" in trust green → P9.
- **Code health:** `chat.tsx` was 1,064 lines → F4 (split into `app/app/_chat/`, largest file 421 lines). Legacy colour aliases → P8.
- **Smaller:** "Scheme type" label; change kind only general → development;
  custom project labels (Client, Internal, Bid) — backlog.
- **Visual check of the running app:** done in F1 (6 Nov 2026) — findings below,
  new work in P10 and P11.

## F1 visual pass findings (6 Nov 2026)

How it was run: `apps/web/e2e/visual-pass.spec.ts` (opt-in:
`VISUAL_PASS=1 pnpm test:e2e e2e/visual-pass.spec.ts`) screenshots 21 screens
at 1280×800 and 390×844, plus the phone drawer, against a mocked backend
seeded as a fictional development trust (3 projects, 4 chats, 5 documents,
6 facts, 3 members). It also checks each screen for horizontal overflow, text
under 12px, H1 and `<main>`, and console errors. Screens it could not fill
with realistic data (operator workspaces, funder catalogue, grant stages,
development-room registers) were judged on their empty state only. Not yet
seen: staging with real data, Safari/iOS, a tablet width, dark or high-contrast
modes, the command palette and modals.

Automatic checks: no app screen has text under 12px (the marketing home's
product mock-up does: 10.5–11px labels — P8); Chat and Documents still have no
H1 or `<main>` (already in P6); Settings overflows sideways by 47px on a phone;
no console errors from the app itself.

**Phone width (390px) — new item P10.** The workspace is not usable on a phone
yet, which matters before R4 (installable app):
- **Documents rows collapse** (`vault.tsx`): the title column is squeezed to
  nothing, the status chip sits on top of "Added …", and ★/Delete are off-screen.
  The worst screen found.
- **Tables clip their columns** with no scroll cue: Grant funding (only
  Application/Funder/Status show), Contacts (email cut), Settings → People
  (third column cut; this is the 47px overflow), Development projects.
- **Project and grant headers overflow:** on the development room the
  "Chat about this project" pill squeezes into a four-line circle and the stage
  strip runs off the edge (no LIVE); on a grant application MONITOR, EVALUATE,
  the status select and Edit are off-screen. Both tab strips wrap to 2–4 rows.
- **Chat composer:** mode tabs clipped at "Slid…" with no scroll cue; the
  placeholder is cut mid-word; the composer covers the last hero card.
- Settings → invite field shows "colleague@(" — too narrow; the drawer shows a
  ⌘K hint on a touch device.

**Laptop width (1280×800):**
- **Chats are below the sidebar's fold** (`sidebar.tsx` nav): at 800px tall
  only the "Chats in …" heading peeks out; the list everyone uses most needs a
  scroll inside the sidebar. Give chats the flexible space, or cap the nav
  above it → P6.
- **The plan panel in a project chat crushes task titles** to one word
  ("Confirm", "Draft th"): the chat column is too narrow for date, assignee,
  arrows, Note and Remove on one line → P11.
- **Operator console:** the Funder forms section sits outside the centred
  container, flush to the window's left edge (`app/admin/page.tsx:289`); the
  empty workspace table shows headers and no "no workspaces yet" row → P11.
- **One module, three names:** sidebar "Grant funding", add-on tab
  "Grant applications", development-room tab "Funding" — the room shows both
  "Funding" and "Grant applications" side by side → P6.
- **Development room tabs** (11 with add-ons) wrap onto a second line at 1280px → P11.
- **Two amber primaries** seen on: development room overview (Draft monthly
  report + Health card), Your organisation (Look up a register + That's right),
  Community empty state (Add a figure + Describe the place) → P7.
- **Mixed date formats:** 04/11/2026 on Documents, Projects and grant headers;
  "1 Apr 2027" on facts → P8 (pick one: "4 Nov 2026").
- **Chat hero copy is for a generic business** ("policies, prices,
  procedures"; suggestion "Draft a letter quoting for a new client") — wrong for
  charities and development trusts → P9.
- **Smaller:** grant "Stages & gates" is blank when there are no stages (no
  empty or loading message); native "Choose File / No file chosen" inputs in
  Settings; "Secured £0" shown in amber; Usage shows pence to four places
  (£0.9480) and uses a narrower column than other pages; "Reporting Calendar"
  in title case; Documents rows carry five controls each and "Refresh" does
  not say it re-reads the file → P11.


## Stage 1: foundations (weeks 1–2)

| ID | Item | Done when | Where | Days |
| --- | --- | --- | --- | --- |
| F1 | Visual pass of the running app | Screenshots of every main screen at laptop and phone width; issues added to this plan | Playwright against local or staging | 1 |
| F2 | Prompt-injection fix (LLM-1) | Retrieved text and tool output fenced and labelled as data in every system prompt; promptfoo canaries include injection cases | `app/litellm.py`, prompts, `infra/promptfoo/` | 2 |
| F3 | Content-security policy | `script-src` and `connect-src` with nonces (security review item 13) | `apps/web` middleware | 1 |
| F4 | Split `chat.tsx` | Under ~400 lines per file: composer, message list, sources panel, scope banner | `apps/web/app/app/` | 2 |
| F5 | Claude alias and model test | Claude added behind LiteLLM as alias `agent` on a zero-retention UK/EU endpoint (see #73). ~10 funder forms, ~20 cited questions and ~15 tool-call scenarios run on current aliases and on Claude; quality and cost per task recorded; routing rule for tool turns and final drafts set from the results | `infra/litellm/config.yaml`, `app/routing.py`, `infra/promptfoo/` | 3 |
| F6 | Card component | One `<ActionCard>` with confirm, edit and reject; first used by P1 | `apps/web/components/` | 2 |

- [x] F1 (#18) · [x] F2 (#22) · [ ] F3 · [x] F4 (#19) · [ ] F5 · [x] F6 (#21)

- F2 (#22, merged 7 Nov 2026): the promptfoo injection canaries (`infra/promptfoo/injection.yaml`) have not yet been run against the live models; Gate A needs one green run.
- PR #20 (7 Nov 2026) fixed CI drift: msgpack and dnspython advisories, and a date-sensitive test.

## Stage 2: first hour and finish (weeks 3–8)

| ID | Item | Done when | Where | Days |
| --- | --- | --- | --- | --- |
| P1 | Setup guide | Organisation guessed from the email domain; Companies House / Charity Commission match shown as a card; confirming imports claims; guide invites colleagues, asks for one job this week and starts it | `app/claims/registers.py`, new onboarding route, F6 | 5 |
| P2 | Sample workspace | Fictional development trust with documents, a project and a grant; operator-created for demos and trials; time-limited, hard budget | `routers/admin.py`, seed script | 2 |
| P3 | Project and workspace guidelines | Brief of up to ~4,000 characters, editable by members, read on every turn | `projects` table, routing context | 2 |
| P4 | Playbooks | Two tiers: Flowgrid-shipped playbooks, and workspace playbooks saved from a successful draft or question, private until shared. Operator can promote a workspace playbook to the shipped set | Question-set catalogue pattern | 4 |
| P5 | Monthly workspace report | Counts of cited answers, drafts, forms answered and deadlines met beside AI spend by project and module; page plus trustee-ready PDF. Publish typical costs per task | `usage_events`, worker PDF | 3 |
| P6 | Navigation finish | Persistent scope chip ("Showing: X · Show all") that survives page changes and saves `project_id`; H1 and `<main>` everywhere; one active state; tabs in `?tab=` with tablist roles; palette "Go to" plus actions, Ctrl on Windows; chat history page; `/admin` linked both ways; name in footer | `sidebar.tsx`, `command-palette.tsx`, pages | 5 |
| P7 | Accessibility finish | Live region for streamed answers; citation [n] opens source n; words beside RAG dots, claims badge and ★ (`aria-pressed`); palette focus trap and listbox; drawer Escape and `aria-expanded`; hand-rolled buttons on the shared Button | chat parts, components | 4 |
| P8 | Type scale and capitals sweep | Scale 12/13/14/16/18/22/29/44; lint rule against `text-[\d`; spaced capitals for stamps only; lighter chrome weights; answers capped at 68ch; darker bone hairline; legacy alias codemod | `globals.css`, every screen | 4 |
| P9 | Chat polish | Example prompts on first use; a next step in every empty state; friendly model name and cost under each answer; neutral badge for web-only answers; "0 documents" not green | chat parts | 2 |
| P10 | Phone layout | Every main screen usable at 390px with no sideways scroll: Documents rows stack (title first, actions in a menu); tables become cards or scroll with a visible cue; project and grant headers wrap (stage strip scrolls, actions below the title); composer mode tabs scroll with a cue; the visual-pass spec reports 0px overflow on every phone screen | `vault.tsx`, tables, `development-room.tsx`, grant page, composer | 3 |
| P11 | Visual-pass fixes | The laptop findings from F1 not covered by P6–P9: plan panel rows wrap in the chat column; operator console sections share one container and the empty table has a row; development-room tabs fit or scroll; empty state for grant stages; styled file inputs; neutral colour for £0; pence to two places; one page width; sentence-case tab labels; Documents row actions grouped | listed in "F1 visual pass findings" | 2 |

- [ ] P1 · [ ] P2 · [ ] P3 · [ ] P4 · [ ] P5 · [ ] P6 · [ ] P7 · [ ] P8 · [ ] P9 · [ ] P10 · [ ] P11

## Stage 3: the action loop (weeks 9–14)

Approval cards come first: automations, preferences and later email all produce cards.

| ID | Item | Done when | Where | Days |
| --- | --- | --- | --- | --- |
| A1 | Approval cards and tools | Chat can propose: create or assign a task, update a budget line, risk or condition, propose a claim, set a deadline, start a draft. Each appears as an F6 card showing the change; a member with the right role accepts, edits or rejects. Acceptance writes through the normal API and `audit_log`; rejection is logged. Tool turns use the `agent` alias (#73). No tool can submit outside Flowgrid | New `action_proposals` table (RLS), tool registry beside `app/routing.py`, `routers/conversations.py` | 8 |
| A2 | Saved automations | "Run this every month" on any draft, digest or check, keeping the accepted format. Triggers: schedule or record event ("grant deadline in 14 days"). Monthly budget; pause after three failures with an email to the owner; run history with steps and cost. Output arrives as a card or draft. **A new automation starts paused** until a person switches it on; automations are saved instructions plus a playbook, never user-written code | New `automations`, `automation_runs` tables (RLS), arq cron, drafting engine | 10 |
| A3 | Learned preferences | Draft edits compared with the original; repeated patterns become proposed preferences ("use 'tenants', not 'residents'") a person confirms. Scoped to workspace, project or funder; review date; viewable and editable on a page | Claims register pattern; new `preferences` table (RLS) | 5 |
| A4 | Threads and annotations | Comment on a draft section, document, claim or record; @mention a colleague or the assistant; highlight text and ask for a revision of that part only. Notifications to the activity feed and the weekly email | New `threads`, `comments` tables (RLS), section regeneration | 7 |

- [ ] A1 · [ ] A2 · [ ] A3 · [ ] A4

## Stage 4: reach (weeks 15–20)

| ID | Item | Done when | Where | Days |
| --- | --- | --- | --- | --- |
| R1 | Email and calendar, draft-first | Connect Microsoft 365 or Google (whichever the pilots use most first). Replies to funders and partners drafted as cards; only a person sends. Deadlines out as calendar events or an iCal feed. Read-only inbox search can feed cited answers | Encrypted OAuth token store (RLS), A1 cards, grants reporting calendar | 12 |
| R2 | Read-only MCP server | A tenant's own Claude or ChatGPT can search cited Documents and confirmed claims through a per-user key, scoped by RLS and metered | New API key table (RLS), retrieval and claims routes | 5 |
| R3 | Custom registers | "Make me a volunteer register" creates a typed table with list, board and calendar views, referenceable in chat and drafts | Module kit, generic records table (RLS) | 10 |
| R4 | Installable web app | PWA manifest and offline shell; mobile drawer and touch targets finished. (Kylon's Mac app is a thin wrapper around its web app; a native wrapper only if push becomes essential) | `apps/web` | 2 |

- [ ] R1 · [ ] R2 · [ ] R3 · [ ] R4

Left out on purpose: a cloud computer per agent, local agents joining the
workspace, multi-agent routing, custom-coded apps, integration breadth.

## Decisions

| Decision | Outcome | Needed by | Status |
| --- | --- | --- | --- |
| Lift "no agent tools in Phase 1" (spec §9.4) | Lifted for **draft-first tools only**; "Flowgrid never submits to a funder" stays the outer line | Before A1 | **Agreed 6 Nov 2026** — ASSUMPTIONS #72 |
| Frontier model | **Claude**, behind LiteLLM as alias `agent`, on a zero-retention UK/EU endpoint (AWS Bedrock or Google Vertex, chosen in F5 with written zero-retention and no-training terms). Used for tool turns and final drafts; open-weight aliases stay the default for everything else. F5 sets which task kinds route to it | F5 (week 2) | **Agreed 6 Nov 2026** — ASSUMPTIONS #73 |
| Pricing once automations run unattended | Recommended: per seat plus a pooled monthly AI allowance per workspace; automations draw on the pool. Stripe goes in with it | Before A2 ships | Open |
| Spend-cap refusal on drafts (security item 11) | Recommended: refuse at start once the hard cap is reached; automations pause the same way | Before A2 | Open |
| Sample workspaces for trials | Recommended: operator-made, time-limited demo with a hard budget; real workspaces stay operator-provisioned | Before P2 | Open |
| Spaced capitals | Recommended: stamps only | Before P8 | Open |
| Which mail and calendar first | Ask the pilot workspaces | Before R1 | Open |

Follow-ups from the agreed decisions:
- Marketing and collateral that say "open-weight models" (`README.md`,
  `docs/flowgrid-os-partner-one-pager.html`, the website's platform/security
  pages) need rewording once the `agent` alias is live — e.g. "open-weight by
  default, Claude where it matters, every call on a zero-retention host and metered".
- The DPA/subprocessor list must name the chosen Claude host before it goes live.

## How we'll know it worked

Capture baselines from the pilot workspaces in stage 1 before anything changes.

| Stage | Measure | Target |
| --- | --- | --- |
| 1 | F5 quality score and cost per task, current vs Claude | Recorded routing rule |
| 1 | Injection canaries passing | All |
| 2 | Time from first sign-in to first accepted draft or cited answer | Under 1 hour, unaided |
| 2 | Claims confirmed in the first session | 10 or more |
| 2 | Pages failing the review checks (12px floor, H1, colour-only status, keyboard reach) | None |
| 3 | Cards accepted unchanged / edited / rejected | Over half accepted; no wrong writes |
| 3 | Automations still running after 30 days | Most of those created |
| 3 | AI spend from automations, within caps | Tracked; no cap breaches |
| 4 | Workspaces with mail or calendar connected | Most pilots |
| All | Pilot workspaces active weekly | Rising stage on stage |
