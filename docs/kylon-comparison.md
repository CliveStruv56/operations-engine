# Kylon vs Flowgrid OS — what to learn (6 Nov 2026)

Context for `docs/enhancement-plan-nov-2026.md`. Researched from Kylon's public
site, docs, help centre, trust centre, subprocessor list, DPA and changelog
(2 Oct – 3 Nov 2026), plus screenshots of a Mac-app signup. Statements marked
*inference* are our reading, not Kylon's.

## What Kylon is

[Kylon](https://kylon.io) (Pure Reason Inc., Palo Alto and Singapore; public
launch Oct 2026, weekly releases) is a "company harness": a Slack-like
workspace where people and AI agents work in shared rooms. Its AI **does the
work and a person releases it**; Flowgrid's AI answers and drafts only.

| Concept | What it is |
| --- | --- |
| Rooms and threads | Rooms and DMs; a thread can attach to a file, app, record or automation. Room guidelines (≤ 4,096 chars) are read by every agent on every turn |
| Agents | Workspace members with persona, skills, connections and their own member list; start private; a router picks who answers |
| Memory | Typed entries (preference, feedback, reference, context), scoped, reviewed every 15–60 days; learns from human edits to drafts. No memory browser |
| Knowledge | Markdown files plus an index. *Inference:* no vector index or citation UI |
| Apps | Agent-built database apps (table/board/calendar) and custom-coded apps with preview builds; public forms; custom domains |
| Automations | Created by doing the job once with an agent. Schedule, record-change and signed-webhook triggers; credit budgets; pause after 3 failures; run history. New automations start paused |
| Skills | `SKILL.md` playbooks, bundled or workspace-made, private until shared, installed per agent |
| Tools | Built-in data (Apollo, Exa, Ahrefs…) with no API key; "3,000+" integrations via OAuth/MCP; a cloud computer with a browser per agent |
| Approvals | Every email/X/LINE send is a Draft card only a person can release; approval cards for publishing, public links, new agents |
| Bring your own agent | Claude Code, Codex, Devin and others join as members via a CLI gateway |
| Models | Max/Pro/Fast levels over Claude, GPT and Gemini; no user choice |
| Pricing | Per workspace: Core $50–$800/month for 500–8,000 credits, ≤ 10 agents; Pro/Ultra custom; work pauses at zero credits; 7-day trial with a card |

## Where Flowgrid is already stronger

- **Cited answers** with page-level citations and honest "not found"; Kylon's
  citing is a prompting tip.
- **Reviewed facts register** fed by UK registers; Kylon's memory can carry
  private-room learnings to other rooms.
- **Audit log** on every change, exported; Kylon has "no separate audit log export".
- **Data handling:** Western zero-retention hosts, no training on any plan;
  Kylon stores data US-only and promises no-training on Pro/Ultra only.
  SOC 2 / ISO 27001 still in progress there.
- **Hard cost caps** with a soft-cap downgrade; Kylon pauses all work at zero.
- **Domain depth:** stage gates, grant lifecycle, funder forms.
- **White-label for partners;** Kylon's partner model is "build, hand over, leave".

## What to take (mapped to plan items)

1. **Draft-first actions with approval cards** → A1 (needs ASSUMPTIONS #72).
2. **"Do it once, then save" automations**, paused until enabled → A2.
3. **Per-project guidelines** read on every turn → P3; **learned preferences**
   from draft edits, with a page to view them → A3.
4. **Threads and annotations on objects** → A4.
5. **Playbooks** (shipped and workspace tiers) → P4.
6. **A faster first hour** → P1, P2.
7. **Monthly value report** in measured counts → P5.

## Kylon's onboarding (seen 6 Nov 2026)

A guide agent runs setup as a conversation, one question per screen: invites
your local Claude Code (installing a background helper), shows an "Agent Team
Report" of your past AI usage ("US$1,223 of work"), offers credits for sharing
on X and for invites, then opens a private welcome room. It guesses the company
from the email domain, shows an editable confirm card ("Company website",
Confirm / "No website yet"), researches the site while asking "what would you
most like off your plate this week?".

Take: guess-then-confirm cards, research while asking, end with one concrete
job, invites sent by the guide. Skip: share-for-credits, referral credits,
background helpers, invented dollar values.

## Not worth copying

Cloud computer per agent, local agents joining the workspace, multi-agent
routing and sub-agents, custom-coded apps, integration breadth, the
"3,000+ integrations" headline.

## Note on sources

Keep notes about Kylon to its observable behaviour and public documentation.
Do not copy its code, prompt text or bundled documentation into this repo, and
do not use security observations about its desktop app in marketing.
