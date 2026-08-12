# Funder forms, end to end

What the `/app/forms` page is for, what happens to what you type there, and —
the question everyone asks first — what Flowgrid does *not* do.

## Nothing is ever submitted for you

Flowgrid never touches a funder's website. It has no login to their portal, no
API into their system, and no way to file anything on your behalf. It does not
watch for deadlines on their end or acknowledge receipt.

What it produces is an **answer sheet**: your answers, each sized to that
question's field limit, with a copy button beside every one. You open the
funder's own portal, paste each answer into the matching box, and submit it
yourself. That last step is deliberately yours — an application goes out over
your name, and a wrong figure pasted automatically is still your wrong figure.

## The sequence

**1. Transcribe.** Paste the funder's published questions into `/app/forms` →
"Add a form". The text can come from their "how to apply" page, a questions
and word-counts sheet, or the form itself. Press "Read the questions" and the
model turns that prose into a structured list: each question, the funder's own
guidance note under it, and its field limit.

Transcription is not invention. Questions are copied, not paraphrased — if a
question comes back reworded, that is a bug worth reporting, because a draft
answering a question the funder did not ask is worse than no draft.

**2. Correct, then save.** Fix anything misread, then fill four things:

| Field | Why it is required |
| --- | --- |
| Funder | Names the row and groups the sets |
| Form | Distinguishes an EOI from a full application for one funder |
| Where these came from | The receipt — the page you transcribed from |
| At least one question | Nothing to answer otherwise |

Save stays disabled until all four are present, and says which are missing.
The source URL is the one people forget, because you copy the form's *text*,
not the page's address. Keep it: in six months it is the only way to check
whether the funder has changed the form under you.

**3. Verify.** A saved set starts **unverified**, and every draft written
against it carries that caveat until somebody presses "I have checked this
against the funder's form". That is not ceremony. The whole value of the sheet
is that answers fit the boxes; if the transcription is wrong, the fit is a
fiction, and the caveat is what stops a draft being trusted before anyone has
looked.

**4. Draft.** In a grant or project, open the draft modal and pick a saved
form. The engine writes one answer per question — grounded in your vault, and
sized to that question's limit.

**5. Check the sheet, then paste.** The answer sheet shows each question, its
answer, and a live count: "Everything fits", or "N over — shorten before
pasting". Copy each answer into the funder's portal by hand.

## Limits are the point

Steps 4 and 5 both hang on the limits captured in step 1. A question saved
with no limit gives the engine no target length, so the answer comes back
arbitrarily sized and the sheet cannot tell you whether it fits. You lose the
one check that catches 900 words heading for a 500-character box.

So when the panel says **"no limit found — check the funder's form"**, treat it
as work outstanding, not a cosmetic warning. Go back to the guidance, find the
stated word or character count, and type it in. If the funder genuinely
publishes no limit, saving without one is fine — you are simply choosing to do
without the fit check for that question.

A limit that changes after you transcribe produces an answer that will not fit
and a sheet that says it does. That is what verification re-checks.

## Two kinds of row

The list shows two sources, and the difference is on the face of each row.

**From the catalogue** — curated centrally and shared across workspaces. Read
only here. `generic_eoi_v1`, the generic expression of interest, ships seeded.

**Transcribed here** — this workspace's own, editable and deletable here, and
carrying the unverified caveat until checked.

An operator can promote a well-transcribed set into the platform catalogue via
`/admin`, so other workspaces inherit the work. Real funder sets are only ever
transcribed — they are never seeded from a fixture, because a stale set that
looks official is more dangerous than an empty list.
