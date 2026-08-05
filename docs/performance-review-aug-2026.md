# LLM latency review — 4 Aug 2026

> **Status — measured, and it worked.** Chat went from 30–40s to **under 2s**
> on staging (`ttft_ms` 166–356). Items 1, 2, 4, 5 and 6 of §6 landed; item 3
> was solved a different way, since paid Groq upgrades were closed to new
> accounts, so `drafter` routes through **OpenRouter** to the same Groq
> capacity. Items 7–9 are untouched and now optional. Numbers and the three
> hypotheses they settle are in `review-context-handoff.md` §6j.
>
> **Drafting confirmed too:** `case_for_support` 21.3s / 9 calls,
> `funding_application` 35.1s / 11 calls — against ~33 minutes before, with
> zero 429s. **Item 10 (parallelise draft sections) should be closed, not
> built:** at these times the concurrency no longer pays for its risk, and one
> `reasoner` call is half the wall clock, so parallelising the other ten would
> save almost nothing.
>
> **Two claims below are now disproven by measurement, not argument:**
> §3.1's worry that `reasoning_effort` might not reach a GLM model — it does;
> and §3.7's gateway key-auth caching hypothesis — the gateway adds no
> meaningful overhead. Both were flagged as unverified at the time; neither
> should be acted on now.
>
> **One correction to §4 below:** it offers DeepInfra as the fallback host for
> `drafter`, described as "slower per token". Measured, it is **48 t/s against
> Groq's 479** — a 10x gap that would mean ~6 min drafts rather than ~40s.
> Treat that suggestion as a last resort, not the recommended swap. The rest
> of the review is kept as written.

Scope: every path where a user waits on a model. Chat (`apps/api`), drafting
and ingest (`apps/worker`), the gateway (`infra/litellm`), and the chat UI
(`apps/web`). No code was changed.

A second opinion was supplied alongside this review; §2 assesses it. The short
version: it is a competent backend inventory, its top recommendation is
**actively harmful** in this codebase, and it looked at only one of the two
places the latency actually lives.

---

## 1. Headline

There is no single slow component. There are **three separate problems**, and
they explain three different complaints that all feel like "the LLM is slow":

| Symptom | Cause | Where |
| --- | --- | --- |
| Long pause after hitting send, before *any* text appears | Chat sends no `reasoning_effort` and no `max_tokens`. `workhorse` is a reasoning model. It thinks — emitting nothing the stream can render — before it writes a word. | `apps/api/app/litellm.py:138-173` |
| Text arrives, but the page stutters and the fan spins | Every single token re-parses the entire markdown of the answer *and every prior answer in the conversation*, then forces a scroll reflow. | `apps/web/app/app/chat.tsx:370`, `:283-285`, `:435-452` |
| Drafts take 30+ minutes or die | Groq free tier: 200k tokens/day, and a draft is ~51k. Rate-limited calls retry twice at a 120s timeout, then fall back. The repo's own measurement: **~3 min/call**. | `infra/litellm/config.yaml:54-55`, `apps/worker/worker/main.py:206-208` |

The first and third are already known to the project —
`docs/review-context-handoff.md` §6i lists the missing chat `reasoning_effort`
as open item 4, and the Groq quota as a blocker on item 1. This review
promotes both from "known gap" to "this is the cause".

The second is new and is not mentioned anywhere in the repo.

---

## 2. Assessment of the supplied report

### Where it is right

- **§8, concurrency wins.** Correct that `drafting/retrieval.py:116-121` runs
  vector and text search serially — though see the caveat below.
- **§5, output ceilings.** Right instinct, wrong conclusion. See §3.1.
- **§10, observability first.** The strongest section, and correctly placed
  as a prerequisite. It is under-ranked at #4 in its own priority list.
- **§3, caching.** Fair: there is no response cache anywhere. Value is lower
  than claimed (exact-prompt cache hits are rare in chat), but the *key-auth*
  angle it missed is real — see §3.7.

### Where it is wrong

**Its #1 recommendation — "parallelize drafting sections" — would make
drafting slower and more failure-prone, not faster.**

The report treats the ~11 sequential section calls as the bottleneck. They are
not. The bottleneck is that each call spends minutes waiting on Groq
rate-limit backoff. The report never opened `docs/review-context-handoff.md`,
where the project records that a real run **died on a Groq 429 after eight
model calls**, and that the free tier's 200k tokens/day is exhausted by one
afternoon of drafting (§6i, "Open, in priority order", item 1).

Firing 5 sections concurrently against a quota-limited endpoint converts a
slow job into a failing one: more 429s, more retries, faster quota burn, and
`num_retries: 2` multiplies each failure by three. The report half-sees this
("Risk: … higher chance of hitting provider rate limits") and then ranks it
first anyway.

Parallelism is the right *second* move. It is the wrong first one.

**Two smaller errors:**

- §8 says `conversations.py` "embeds the query and then calls the LLM
  sequentially — those two network calls could start together". They cannot:
  the embedding produces the retrieval that produces the system prompt the LLM
  call needs. The real concurrency win in that file is elsewhere (§3.4 below),
  and the report missed it.
- §8 suggests running the vector and text arms concurrently. Worth doing, but
  not as written — both run on a single asyncpg connection inside one tenant
  transaction, and asyncpg does not multiplex. It needs a second connection,
  which means a second `tenant_tx` and a second RLS `set_config`. That is a
  real change with a real cost, not a free `asyncio.gather`.

### What it missed

1. **The chat reasoning-token problem** — the single largest contributor to
   the user-visible complaint (§3.1).
2. **The entire frontend.** It reviewed "the LLM call paths in `apps/api`,
   `apps/worker`, and `infra/litellm`" and stopped. Roughly half the perceived
   slowness is in `apps/web` (§3.2).
3. **Unbounded chat history** (§3.3) — the reason chat gets slower the longer
   a conversation runs.
4. **Prompt layout defeats provider prefix caching** (§3.3) — a structural
   choice that makes every turn pay full prompt-processing cost forever.
5. **Research mode runs Exa and the embedder serially** (§3.4) — up to 15s of
   avoidable dead time on the slowest chat mode.
6. **The API runs one uvicorn process** (§3.6).

On §9's suggestion to cut embedding dimensions from 2048: that is not a
latency change worth making. It requires re-embedding the entire vault, a
migration on `doc_chunks.embedding`, a new HNSW index, and it degrades
retrieval quality — to save a few milliseconds on a path that is not the
bottleneck. Recommend against.

---

## 3. Findings

Ranked by expected reduction in what a user actually experiences.

### 3.1 Chat lets the model think for free — highest impact

`apps/api/app/litellm.py:138-148` sends `model`, `messages`, `stream` and
`stream_options`. That is all. No `max_tokens`, no `reasoning_effort`.

Every drafting-side call bounds both, and the repo documents exactly why
(`apps/worker/worker/drafting/llm.py:19-42`): the aliases are reasoning models
that bill thinking against `completion_tokens`, measured live at **675–709
tokens of thinking before the first word of prose**, and `reasoner` will think
to fill whatever budget it is given — an entire 4096 tokens, returning nothing.

Chat runs on `workhorse` (GLM-4.7-Flash) by default and bounds neither.

The latency consequence is specific and severe. The stream parser at
`litellm.py:169-173` reads only `delta.content`. Reasoning tokens arrive as
`delta.reasoning_content` or not at all. **So the entire thinking phase renders
as a spinner.** The connection is open, tokens are being billed, and the user
sees nothing. At the drafting-measured rate that is several seconds of dead air
on every message before the first character appears — and unbounded, so a hard
question is worse than an easy one in a way that is invisible.

This also explains a bug already logged in handoff §6i item 4: a reply that
thinks past its budget streams nothing and is stored as an empty assistant
message.

**Fix:** send `reasoning_effort: "low"` and a `max_tokens` ceiling on the chat
call, mirroring `drafting/llm.py`. One task mode — `financial`, which routes to
`reasoner` — is a defensible exception. This is a handful of lines and is the
highest-value change in this report.

### 3.2 The chat UI re-parses everything on every token — highest impact

Nothing in the other report covers this. It is roughly half the problem.

`apps/web/app/app/chat.tsx:370`:

```ts
onDelta: (delta) => setStreamText((t) => (t ?? "") + delta),
```

Each delta triggers a state update on `ChatPanel`. Three things then happen,
per token:

1. `AnswerMarkdown content={streamText}` (`:457`) re-runs `ReactMarkdown` with
   `remarkGfm` over the **whole accumulated answer**. Full remark parse, full
   AST, full reconciliation. Token *n* re-parses *n* tokens of text — the total
   work over a reply is O(n²).
2. `messages.map(...)` at `:435-452` re-renders every prior message.
   `AssistantMessage` is not wrapped in `React.memo`, so each one re-runs its
   own `ReactMarkdown` parse *and* the recursive `injectCites` tree walk in
   `components/markdown.tsx:11-27`. A 10-message conversation therefore does 11
   full markdown parses per token.
3. `useEffect(... , [messages, streamText])` at `:283-285` calls `scrollTo`,
   forcing a synchronous layout on every token.

A 600-token answer in a 10-message conversation is on the order of 6,600 full
markdown parses and 600 forced reflows. On a mid-range laptop this saturates
the main thread, and the stream *appears* to arrive slower than it does —
because rendering, not the network, is the limit.

**Fix, in order of value:**
- Wrap `AssistantMessage` in `React.memo`. Settled messages are immutable;
  they should never re-render mid-stream. Cheapest fix, largest single win.
- Buffer deltas and flush on `requestAnimationFrame` (~60/s instead of one per
  token), or render the streaming bubble as plain `whitespace-pre-wrap` text
  and only run markdown on the `done` event. Users cannot read partial markdown
  mid-stream anyway.
- Make the scroll effect depend on a throttled value, or gate it on
  `scrollHeight` actually having changed.

None of this touches the API. It is contained entirely in two files.

### 3.3 Chat history is unbounded, and the prompt is laid out to defeat caching

`apps/api/app/routers/conversations.py:332-335` fetches conversation history
with **no `LIMIT`**, and `:400` puts all of it into the prompt. Every message
ever sent in a conversation is re-sent, and re-processed by the provider, on
every turn. Prompt-processing time and cost grow linearly with conversation
length, without bound.

Worse, the layout prevents the standard mitigation. The system prompt at
`:385-398` is assembled fresh each turn and **freshly-retrieved vault excerpts
are concatenated into it** — 8 chunks at up to ~2,400 chars each, so roughly
4–5k tokens that differ every single turn. Because they sit at the *front* of
the message array, the entire prompt prefix changes each turn, so no
provider-side prefix cache can ever hit. The stable, cacheable part (the base
system prompt and the accumulated history) is stranded behind volatile content.

**Fix:** cap history (last N turns, or a token budget with older turns
summarised), and move per-turn retrieved excerpts out of the system message
into an attachment on the final user turn. Then the prefix — base prompt plus
history — is stable and cacheable, and turn *n+1* pays only for what is new.
This is a prompt-assembly change, not an architecture change.

### 3.4 Research mode serialises two independent network calls

`conversations.py:373-382`:

```python
if body.use_vault:
    embedding, embed_tokens = await litellm_client.embed_query(...)   # ~200-600ms
    ...
if body.task_kind == "research":
    web_sources = await exa_search(body.content)                     # up to 15s
```

The embedding call and the Exa search share no data. In research mode the user
waits for both, back to back, before the model starts. `exa_search` has a 15s
timeout (`app/search.py:24`).

Wrapping them in `asyncio.gather` removes the shorter of the two from the
critical path outright. This is the genuine concurrency win in this file — not
the embed/LLM pairing the other report proposed, which is not possible.

Same pattern, lower value, in `drafting/retrieval.py:116-121`: N queries × 2
serial round trips inside one transaction. Real, but tens of milliseconds
against a job measured in minutes. Low priority.

### 3.5 Groq's free tier is the drafting bottleneck — and it is a billing fix

`apps/worker/worker/main.py:206-208` records the measurement plainly:

> Drafts make ~11 sequential LLM calls; live proof measured **~3 min/call** on
> the drafter alias, so a full draft can run past 30 minutes.

Three minutes per call on Groq — among the fastest inference providers on the
market, serving a 120B model that should return in seconds — is not generation
time. It is rate-limit backoff. Handoff §6i confirms: the free tier is 200k
tokens/day, a single draft is ~35k in / ~16k out, and a live run died on a 429
after eight calls.

The gateway amplifies it. `infra/litellm/config.yaml:54-55` sets
`num_retries: 2` and `timeout: 120`, with a `drafter → workhorse` fallback. A
throttled call can therefore burn three attempts and a fallback before it
returns anything.

**The fix is a paid Groq tier, not a code change.** ~4 drafts per day is not a
product. Until that is done, nothing else in the drafting path is worth
optimising, and parallelising sections (the other report's #1) makes it
strictly worse.

Once the quota is lifted, *then* parallelise — with a `Semaphore(3)`, keeping
the outline call and any section that depends on it sequential. Expect roughly
3–4× on the section phase at that point, but not before.

### 3.6 The API runs a single uvicorn process

`apps/api/Dockerfile:29` is `uvicorn app.main:app` with no `--workers`. One
process, one event loop. Correct for pure async I/O, but any CPU-bound work —
JSON parsing of large payloads, the citation regex over long answers, Fernet
decryption — blocks *every* concurrent chat stream, not just its own.

With `db.py:25` capping the pool at `max_size=10`, headroom is thin. Not a
current bottleneck at present load; it will become one. Worth setting workers
to CPU count before it does.

### 3.7 Gateway configuration

- **No caching of any kind** (`config.yaml` has no `cache` block). The higher-
  value target is not response caching but the proxy's **virtual-key auth
  lookup**: with `database_url` set and no Redis cache, key validation can
  touch Postgres per request, adding a round trip in front of every model call.
  Redis is already running in both compose files. Measure it first — this is a
  hypothesis, not a confirmed finding.
- **Per-call HTTP clients in the worker.** `drafting/llm.py:137` and
  `embed.py:26` construct a new `httpx.AsyncClient` per call — new connection,
  no keepalive, no pooling. The API does this correctly with a module-level
  client (`app/litellm.py:62-67`). In-cluster the cost is small; it is still
  free to fix.
- `num_retries: 2` at a 120s timeout is aggressive for an interactive path.
  Consider splitting: retries are right for the worker, expensive for chat.

### 3.8 Things I checked that are *not* problems

Worth recording, so time is not spent here:

- **`month_spend` aggregate** (`conversations.py:326-331`) runs on every
  message, but `usage_events_tenant_idx (tenant_id, created_at)` covers it and
  RLS supplies the `tenant_id` predicate. It is an index range scan, not the
  sequential scan it looks like. Fine for now; revisit at high volume.
- **RLS overhead.** `app_current_tenant()` is declared `stable`
  (`migrations/versions/0001_initial_schema.py:43-49`), so the planner can
  hoist it. This is the right call and a common thing to get wrong.
- **The HNSW index and its query match.** `retrieval.py:84-88` casts to
  `halfvec(2048)` in both the `order by` and the predicate, matching the index
  expression at `0001_initial_schema.py:125-130`. The index will be used.
- **Retrieval SQL generally.** Two arms, 24 candidates each, RRF fusion in
  Python. Sound, and not where the time goes.
- **The SSE transport.** Frame parsing in `apps/web/lib/api.ts:69-89` is
  correct and incremental, and Coolify's proxy does not buffer by default. The
  transport is not the problem; what happens to each frame after parsing is
  (§3.2).

---

## 4. On changing models — the direct answer

You asked to be told if this means moving to a different model. Mostly it does
not, and that is the useful finding.

**Chat (`workhorse` → GLM-4.7-Flash).** Do not switch yet. The problem is that
the model is unbounded (§3.1), not that it is slow. Bound it first and measure.
An unbounded fast model still stalls; a bounded adequate one does not. If TTFT
is still poor after bounding, *then* consider a non-reasoning model for the
default chat alias — but not before, or you will have swapped models for
nothing and learned nothing.

**Drafting (`drafter` → Groq gpt-oss-120b).** Do not switch the model. Switch
the **plan**. Groq's paid tier is the highest-leverage change available in this
report and touches no code. If paid Groq is off the table, move the `drafter`
alias to DeepInfra's gpt-oss-120b — slower per token, but no daily cliff and no
429 storms, which is a net win at ~3 min/call today. Same alias name, one line
in `config.yaml`, no app code changes (the alias-only discipline in CLAUDE.md
pays off exactly here).

**`reasoner` (GLM-5.2) for `financial`.** The other report suggests demoting
it. Disagree — financial reasoning is where you want the thinking, it is
already bounded to `reasoning_effort: "low"` on the drafting side, and it is
the *only* alias the 4 Aug live test confirmed working end-to-end without
touching the Groq quota. Leave it.

**`embedder` dimensions.** Leave at 2048. See §2.

---

## 5. Measure before the second round

Everything in §3.1–§3.5 is safe to act on now — the causes are visible in the
code and corroborated by the project's own recorded measurements. Beyond that,
you are guessing without numbers.

Cheapest instrumentation that would settle the remaining questions:

1. **Time-to-first-content-delta in chat**, logged per message alongside
   `alias` and `tokens_out`. `StreamResult` (`app/litellm.py:40-51`) is already
   the right place to hang it. This one number confirms or kills §3.1 in a day.
2. **Split the chat pre-stream budget** into three timers — Tx1, embed, Exa,
   retrieval — logged per request. Confirms whether §3.4 is worth the change.
3. **Per-call timing on the drafting ledger.** `LlmCall`
   (`drafting/llm.py:64-75`) already carries alias and tokens; add elapsed. If
   the ~3 min/call is backoff, the distribution will be bimodal and obvious.
4. **LiteLLM Prometheus metrics.** Free, and separates gateway overhead from
   provider time.
5. **A React profile of one streamed reply.** Will show the O(n²) markdown
   parsing in §3.2 immediately and quantify it.

---

## 6. Priority order

Ordered by (user-visible gain) ÷ (effort and risk).

| # | Change | Effort | Where |
| --- | --- | --- | --- |
| 1 | `reasoning_effort` + `max_tokens` on the chat call | ~10 lines | `app/litellm.py` |
| 2 | `React.memo` on `AssistantMessage`; stop re-parsing settled messages | ~5 lines | `web/app/app/chat.tsx` |
| 3 | Groq paid tier (or move `drafter` to DeepInfra) | billing / 1 line | account / `config.yaml` |
| 4 | Buffer stream deltas to rAF; throttle the scroll effect | small | `web/app/app/chat.tsx` |
| 5 | Add TTFT + phase timers | small | `app/litellm.py`, `drafting/llm.py` |
| 6 | `asyncio.gather` the embed and Exa calls | small | `routers/conversations.py` |
| 7 | Cap chat history; move excerpts off the prompt prefix | medium | `routers/conversations.py` |
| 8 | Redis cache on the gateway (key auth first, responses second) | small | `config.yaml` |
| 9 | `--workers` on uvicorn | 1 line | `api/Dockerfile` |
| 10 | Parallelise draft sections with a semaphore — **only after #3** | medium | `drafting/engine.py` |

Items 1–4 address the actual complaint. Items 5–10 are follow-through.

Note that #1, #2 and #3 together are perhaps twenty lines of code and one
billing change, and between them they cover all three symptoms in §1. The
architecture is sound; it is under-configured.
