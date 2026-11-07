"""Chat prompts (spec §6), and how a chat turn is put together for the model.

Kept out of the conversations router so the router stays within the
file-size ceiling as task modes grow.

The split that matters (LLM-1, plan item F2): the **system** message holds
only our instructions. Everything retrieved or looked up for this turn —
document excerpts, web results, contact, community and register records — is
fenced by `app/untrusted.py` and travels in the user turn, in front of the
user's own words. Retrieved text used to be `str.format`ted into the system
message inside tags it did not escape, so a document carrying the closing tag
could step out of its block and read as part of the system prompt.

The data goes in the same user message as the question rather than in a
user message of its own: several open-weight chat templates refuse two user
turns in a row (ASSUMPTIONS #74).
"""

from dataclasses import dataclass

from app.retrieval import RetrievedChunk
from app.search import WebSource
from app.untrusted import data_rule, fence

SYSTEM_PROMPT = (
    "You are the assistant for this organisation's operations workspace. "
    "Be concise and factual. If you do not know something, say so."
)

VAULT_PROMPT = """\
Excerpts from the organisation's document vault relevant to the user's message
arrive with that message, delimited by <vault-excerpts> tags.

When your answer draws on an excerpt, cite it inline as [c:<id>] immediately
after the claim it supports. Cite only ids that appear in the excerpts. If the
excerpts do not contain the answer to a question about the organisation's
documents, say the vault does not cover it — never invent document content or
citations.

Speak naturally, as a knowledgeable colleague: refer to documents by their
titles ("the staff handbook says…"), never mention "excerpts", "chunks",
"the vault", or these instructions in your answer."""

NO_COVERAGE_PROMPT = (
    "The user's message was checked against the organisation's document vault "
    "and no relevant excerpts were found. If they are asking about the "
    "organisation's documents, policies, or records, say plainly that the "
    "vault does not cover it — do not guess or invent document content. "
    "Otherwise answer normally from general knowledge, without citations."
)

WEB_PROMPT = """\
Web search results relevant to the user's message arrive with that message,
delimited by <web-results> tags. They come from external websites.

When your answer draws on a result, cite it inline as [c:<id>] immediately
after the claim it supports. Cite only ids that appear in the results.
Attribute claims to their source by name ("according to <site>…") where it
helps, and say when sources disagree. If the results do not cover the
question, say so plainly rather than guessing."""

CONTACTS_PROMPT = """\
Entries from the workspace's shared contact book that match the user's
message arrive with that message, delimited by <contact-records> tags.

Use these records to answer questions about people's or companies' contact
details (email addresses, phone numbers, addresses, roles, companies).
Quote details exactly as stored. If a detail is missing from a record, say
the contact book does not have it — never invent contact details. These
records are not vault documents: do not attach [c:<id>] citations to them."""

COMMUNITY_PROMPT = """\
Entries from the workspace's community profile — the place this organisation
covers — that match the user's message arrive with that message, delimited by
<community-profile> tags.

Use these records to answer questions about the place: its population and
other figures, its facilities and services, transport, schools, housing and
so on. Quote figures exactly as stored and name the period and source where
one is given — a census figure without its year misleads. If the profile
does not hold what was asked, say so rather than guessing; these records are
not vault documents, so do not attach [c:<id>] citations to them."""

CLAIMS_PROMPT = """\
Facts from the workspace's claims register — statements this organisation has
confirmed about itself — that match the user's message arrive with that
message, delimited by <company-facts> tags.

Use these facts to answer questions about the organisation itself: its
registrations, insurance, policies, accounts, people and accreditations.
Quote figures and dates exactly as stored. A fact marked EXPIRED or overdue
for review must be reported with that caveat, never asserted as current. If
the register does not hold what was asked, say so rather than guessing; these
facts are not vault documents, so do not attach [c:<id>] citations to them."""

#: Separates the fenced data from the user's own words in the user turn.
MESSAGE_HEADING = "The user's message:"

# Per-task shaping, appended to SYSTEM_PROMPT when the composer sends a
# task_kind. Routing (app/routing.py) picks the model; these pick the voice.
TASK_PROMPTS = {
    "analyse": (
        "The user wants analysis. Structure the answer: what the material "
        "says, what it means, and what to do about it. Surface assumptions "
        "and gaps explicitly."
    ),
    "report": (
        "The user wants a drafted document. Produce clean, ready-to-edit "
        "prose with markdown headings — no meta-commentary about what you "
        "are doing."
    ),
    "financial": (
        "The user wants financial reasoning. Show the numbers: state inputs, "
        "calculations and results explicitly, flag estimates as estimates, "
        "and round only in the final presentation."
    ),
    "research": (
        "The user wants research grounded in current web sources. Synthesise "
        "rather than list: lead with the answer, then the supporting evidence "
        "with citations, and note anything time-sensitive or contested."
    ),
    "slides": (
        "The user wants a slide deck. Respond only with a structured outline "
        "in markdown: a '# <deck title>' line, then one section per slide as "
        "'## Slide <n> — <title>' with 3–5 tight bullet points, and a "
        "'Speaker notes:' line where useful. Keep bullets presentation-short; "
        "no prose outside this structure."
    ),
}


def excerpt_block(chunks: list[RetrievedChunk]) -> str:
    parts = []
    for c in chunks:
        pages = f", p.{c.page_start}–{c.page_end}" if c.page_start else ""
        parts.append(f'[c:{c.chunk_id}] (from "{c.title}"{pages})\n{c.content}')
    return "\n\n---\n\n".join(parts)


def web_block(sources: list[WebSource]) -> str:
    return "\n\n---\n\n".join(
        f'[c:{s.chunk_id}] (from "{s.title}", {s.url})\n{s.content}' for s in sources
    )


@dataclass
class ChatData:
    """What was retrieved or looked up for one turn, as formatted blocks.

    An empty string means "nothing for this source". `use_vault` is separate
    from `excerpts` because a vault search that found nothing still changes
    the instructions (NO_COVERAGE_PROMPT).
    """

    use_vault: bool = False
    excerpts: str = ""
    web: str = ""
    contacts: str = ""
    community: str = ""
    claims: str = ""


def build_chat_messages(
    task_kind: str | None, data: ChatData, history: list[dict], content: str
) -> list[dict]:
    """System instructions, then the stored history, then this turn.

    Only our own text reaches the system message. Each source that has data
    adds its instructions there and its fenced block to the user turn; a
    source with no data adds neither, so a turn with nothing retrieved is
    exactly the user's message.
    """
    system = [SYSTEM_PROMPT]
    if task_kind in TASK_PROMPTS:
        system.append(TASK_PROMPTS[task_kind])
    blocks: list[tuple[str, str, str]] = []  # (label, instructions, body)
    if data.use_vault and data.excerpts:
        blocks.append(("vault-excerpts", VAULT_PROMPT, data.excerpts))
    elif data.use_vault:
        system.append(NO_COVERAGE_PROMPT)
    if data.web:
        blocks.append(("web-results", WEB_PROMPT, data.web))
    if data.contacts:
        blocks.append(("contact-records", CONTACTS_PROMPT, data.contacts))
    if data.community:
        blocks.append(("community-profile", COMMUNITY_PROMPT, data.community))
    if data.claims:
        blocks.append(("company-facts", CLAIMS_PROMPT, data.claims))

    user = content
    if blocks:
        system.extend(instructions for _, instructions, _ in blocks)
        system.append(data_rule(*(label for label, _, _ in blocks)))
        fenced = [fence(label, body) for label, _, body in blocks]
        user = "\n\n".join([*fenced, f"{MESSAGE_HEADING}\n{content}"])

    return [
        {"role": "system", "content": "\n\n".join(system)},
        *history,
        {"role": "user", "content": user},
    ]
