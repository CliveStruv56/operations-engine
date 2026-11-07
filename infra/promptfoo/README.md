# Prompt canaries (promptfoo)

Live-model regression checks for the failure classes this repo has been
bitten by three times (handoff §6h/§6i, DRAFT-002): a reasoning model
spending its whole budget thinking and returning **empty prose**, and a
section prompt **referring to a table it was never given** — plus, since F2,
**prompt injection** (`injection.yaml`): a document, web result, contact
note, typed claim or funder's guidance telling the model to do something
else. Ordinary CI
cannot catch these — they are provider behaviours, not code paths — so these
run against the **staging gateway with real models**, cost a few pence per
run, and are deliberately not part of `ci.yml`.

Run locally against a gateway:

```sh
export LITELLM_BASE_URL=http://localhost:4000
export LITELLM_API_KEY=sk-dev-master-key
npx promptfoo@latest eval -c infra/promptfoo/sections.yaml
npx promptfoo@latest eval -c infra/promptfoo/transcribe.yaml
npx promptfoo@latest eval -c infra/promptfoo/injection.yaml
```

In GitHub, `.github/workflows/prompt-checks.yml` runs both weekly and on
demand, using the `STAGING_LITELLM_BASE_URL` / `STAGING_LITELLM_KEY` secrets;
it skips cleanly when the secrets are not configured.

**These prompts are canaries, not mirrors.** The real prompts live in
`app/prompts.py`, `worker/drafting/` and `app/refdata/transcribe.py`; the
cases here re-state the *contracts* (non-empty prose under
`reasoning_effort: low` + 4096 tokens, no phantom table references, no
invented limits) in a self-contained way. When a real prompt's contract
changes, change the canary with it.

`injection.yaml` is the exception: its cases are the real builders' output
(chat, transcription, drafting section, document summary) for hostile
inputs, because what is under test is the fencing itself. Each case needs the
attacker's code word or link to be absent *and* a fact from the honest data
to be present, so a model that refuses everything still fails.
`apps/api/tests/test_prompt_injection.py` checks the file still uses the
current data rule and fence labels from `untrusted.py`; when a builder's
wording changes, regenerate the affected case.

A failure here means a provider or model has drifted — check
`docs/groundwork/ASSUMPTIONS.md` #26–#27 before touching the gateway config:
DigitalOcean and Novita must never be added to `reasoner`, and
`drop_params: true` is never the fix.
