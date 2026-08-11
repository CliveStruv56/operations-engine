"""Reading a funder's published question list into a structured question set.

The model's job here is **extraction, never authorship**. It reads text a
person pasted from a funder's own guidance and returns the questions that are
in it, in the order they appear, with the limits the text states.

The one rule that matters: **a limit that is not in the text comes back null.**
An invented character limit is the worst output this feature can produce —
worse than no question set at all — because it is silently wrong at exactly
the moment nobody can check it. The consultant writes 2,000 characters to a
1,500-character field and finds out at the portal, after the writing is done.
A null limit is visible, and the review screen asks for it.

So this is a transcription assistant, not a drafting one. The human confirms
every question before anything is stored, exactly as with the claims register:
never ask somebody to populate a database, ask them to correct something.
"""

import json
import re

from app.errors import ApiError
from app.refdata.schemas import Question

#: Guessing here would be worse than failing here.
SYSTEM = """\
You transcribe UK funder application forms into structured data.

You are reading text a person copied from a funder's own published guidance.
Extract the questions it contains. You are not writing an application and you
are not improving anyone's questions.

Rules, in order of importance:
1. NEVER invent a character or word limit. If the text does not state a limit
   for a question, return null. A wrong limit is worse than no limit: it is
   discovered only when an answer will not paste into the funder's form.
2. Transcribe question text as written. Do not rephrase, shorten, tidy or
   merge questions. Keep the funder's own wording, including its punctuation.
3. Keep the order the questions appear in.
4. Guidance is the funder's own explanatory note under a question, if any.
   Never write your own advice into it. Empty string when there is none.
5. If a passage is not a question — a heading, eligibility blurb, a deadline —
   leave it out entirely rather than turning it into a question.

Reply with a JSON object: {"questions": [{"text": ..., "guidance": ...,
"limit": <int|null>, "limit_kind": "characters"|"words", "required": bool}]}.
JSON only, no commentary. If the text contains no questions at all, return
{"questions": []}.\
"""

#: Bound the paste. A funder's question list runs to a few thousand characters;
#: anything much larger is a whole guidance PDF, which belongs in the vault.
MAX_SOURCE_CHARS = 24_000


def build_prompt(source: str) -> list[dict]:
    return [
        {"role": "system", "content": SYSTEM},
        {
            "role": "user",
            "content": (
                "Transcribe the questions in the following text.\n\n"
                f"<funder-guidance>\n{source}\n</funder-guidance>"
            ),
        },
    ]


def _strip_fences(raw: str) -> str:
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        text = text.split("\n", 1)[1] if "\n" in text else text
    return text


def question_id(position: int) -> str:
    """A stable question id.

    Positional (`q1`, `q2`) rather than derived from the wording: the id ends
    up in a stored answer sheet, and a person correcting a typo in a question
    should not silently orphan the answers already written against it.
    """
    return f"q{position}"


def parse_questions(raw: str) -> list[Question]:
    """Turn the model's reply into questions, dropping anything malformed.

    Deliberately strict about limits and lax about everything else: a question
    that arrives without usable text is noise to discard, but a limit that
    arrives in the wrong shape must become null rather than a guess.
    """
    try:
        data = json.loads(_strip_fences(raw))
    except ValueError:
        raise ApiError(
            502,
            "transcription_failed",
            "Could not read that as a question list — try pasting a smaller section.",
        ) from None
    if not isinstance(data, dict) or not isinstance(data.get("questions"), list):
        raise ApiError(
            502,
            "transcription_failed",
            "Could not read that as a question list — try pasting a smaller section.",
        )

    questions: list[Question] = []
    for item in data["questions"]:
        if not isinstance(item, dict):
            continue
        text = str(item.get("text") or "").strip()
        if not text:
            continue
        limit = item.get("limit")
        if not isinstance(limit, int) or isinstance(limit, bool) or limit <= 0:
            # Includes the model returning "2000" as a string, or 0, or a
            # float. Anything we are not certain about becomes "ask the human".
            limit = None
        kind = item.get("limit_kind")
        order = len(questions) + 1
        questions.append(
            Question(
                id=question_id(order),
                order=order,
                text=text,
                guidance=str(item.get("guidance") or "").strip(),
                limit=limit,
                limit_kind=kind if kind in ("characters", "words") else "characters",
                required=bool(item.get("required", True)),
                uses_vault=False,
            )
        )
    return questions


_LIMIT_HINT = re.compile(r"\b(\d{2,5})\s*(characters?|words?)\b", re.IGNORECASE)


def limits_in_source(source: str) -> int:
    """How many limits the pasted text appears to state.

    Used only to tell the reviewer when the model found fewer limits than the
    text seems to contain — a cheap, dumb second opinion on the one field
    nobody can verify later.
    """
    return len(_LIMIT_HINT.findall(source))
