"""Chat-side claims lookup: cheap token match of the user's message against
the claims register, formatted for prompt injection. Third of a family — the
CRM (`app/crm/lookup.py`) and community (`app/community/lookup.py`) lookups
share the design and the reasoning: the message names the thing near-verbatim,
so whole-word matching in SQL answers without an extra model call.

The tokenizer is the community module's (2-char tokens, question words as
stopwords) because the questions are the same shape — "are we VAT registered?",
"who are the trustees?" — and a claim matches through its statement, its
subject, its kind's label, or the kind's `question_hints`, exactly as a
community statistic does.

Unlike the drafting engine's `worker/claims/facts.py`, nothing here may be
cited: the claims' evidence chunks are not in the chat excerpts, and telling
the model to cite an id it cannot see is how stripped markers happen. Expired
and overdue facts are still injected, marked — "our insurance lapsed in April"
is a better answer than silence about the insurance."""

import re
from datetime import date

import asyncpg

#: How many facts one message may pull in. A register holds 40–80 claims and a
#: broad question ("tell me about the company") legitimately matches many; ten
#: one-line statements is a paragraph, not a context problem.
MAX_CLAIMS = 10

# The community lookup's stopwords, kept in step by hand (same standing hazard
# as the worker's `render_statement` copy): message words that would match
# every statement rather than pick one out.
_STOPWORDS = frozenset(
    """the and for you your our who what whats when where how why can could
    get his her their them have has does did tell give find need want know
    with from about please there here this that they are was were will would
    much many any all some more most other of on in at to by is it as an or
    be if my we do no not so up us am he she its out off per via""".split()
)
_WORD_RE = re.compile(r"[A-Za-z0-9'-]{2,}")


def _tokens(message: str) -> list[str]:
    seen: list[str] = []
    for raw in _WORD_RE.findall(message):
        word = raw.strip("'-").lower().removesuffix("'s")
        if len(word) < 2 or word in _STOPWORDS or word in seen:
            continue
        seen.append(word)
        if len(seen) == 12:
            break
    return seen


def _sql_pattern(tokens: list[str]) -> str:
    """POSIX regex matching any token as a whole word (\\m/\\M boundaries)."""
    return r"\m(" + "|".join(re.escape(t) for t in tokens) + r")\M"


async def match_claims(conn: asyncpg.Connection, message: str) -> list[asyncpg.Record]:
    """Confirmed claims the message is asking about.

    Proposals and rejected facts never reach a prompt — the register's
    founding rule holds in chat exactly as it does in a draft: an unconfirmed
    fact is not something this workspace asserts.
    """
    tokens = _tokens(message)
    if not tokens:
        return []
    pattern = _sql_pattern(tokens)
    rows = await conn.fetch(
        """
        select c.subject, c.period, c.statement, c.as_of, c.expires_on, c.next_review,
               coalesce(k.label, c.kind) as label
        from claims c left join ref_claim_kinds k on k.key = c.kind
        where c.status = 'confirmed'
          and (c.statement ~* $1
               or c.subject ~* $1
               or k.label ~* $1
               or exists (select 1 from unnest(k.question_hints) h where h ~* $1))
        order by c.kind, coalesce(c.subject, ''), coalesce(c.period, '')
        limit $2
        """,
        pattern,
        MAX_CLAIMS,
    )
    return list(rows)


def claims_chat_block(claims: list[asyncpg.Record], today: date | None = None) -> str:
    """The facts, one statement per line, with the qualifiers that keep them
    honest — same wording as the drafting engine's `claims_block`, minus the
    citation instructions chat cannot honour."""
    today = today or date.today()
    lines = []
    for claim in claims:
        qualifiers = []
        if claim["period"]:
            qualifiers.append(claim["period"])
        if claim["as_of"]:
            qualifiers.append(f"as at {claim['as_of'].isoformat()}")
        if claim["expires_on"] is not None and claim["expires_on"] < today:
            qualifiers.append(f"EXPIRED {claim['expires_on'].isoformat()}")
        elif claim["next_review"] is not None and claim["next_review"] <= today:
            qualifiers.append("overdue for review")
        suffix = f" ({'; '.join(qualifiers)})" if qualifiers else ""
        lines.append(f"- {claim['statement']}{suffix}")
    return "\n".join(lines)
