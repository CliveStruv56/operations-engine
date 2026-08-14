"""The digest email body — pure rendering, no DB (that half of the sweep is
exercised from the API suite against a real Postgres, ASSUMPTIONS #13)."""

from datetime import date

from worker.claims.sweep import DueClaim, render_digest
from worker.email import unsubscribe_token

BASE = "https://client.example"
UNSUB = "https://api.example/api/v1/email/digest?tenant=t&membership=m&token=x"


def _due(statement: str, *, lapsed: bool = False) -> DueClaim:
    return DueClaim(
        statement=statement,
        next_review=None if lapsed else date(2026, 8, 10),
        expires_on=date(2026, 8, 1) if lapsed else None,
        lapsed=lapsed,
    )


def test_digest_puts_lapsed_first_and_links_out():
    due = [
        _due("The organisation's public liability insurance is in place.", lapsed=True),
        _due("The organisation's annual income was £847,000."),
    ]
    subject, text = render_digest(
        "Willow Housing", due, proposals=3, base_url=BASE, unsubscribe_url=UNSUB
    )
    assert subject == "2 facts need a check — Willow Housing"
    assert text.index("Lapsed 1 Aug") < text.index("Past review (10 Aug)")
    assert f"{BASE}/app/claims" in text
    assert UNSUB in text
    assert "3 facts waiting to be checked" in text


def test_digest_singular_and_no_proposals_footer():
    subject, text = render_digest(
        "Willow",
        [_due("The organisation's registered name is Willow.")],
        proposals=0,
        base_url=BASE,
        unsubscribe_url=UNSUB,
    )
    assert subject == "1 fact needs a check — Willow"
    assert "waiting to be checked" not in text


def test_digest_is_a_pointer_not_the_register():
    due = [_due(f"Fact number {i} has gone off.") for i in range(14)]
    _, text = render_digest("Willow", due, proposals=0, base_url=BASE, unsubscribe_url=UNSUB)
    assert "…and 4 more." in text
    assert "Fact number 13" not in text


def test_unsubscribe_token_is_stable_per_pair():
    # Same algorithm the API verifies; keyed on the pair so a token cannot be
    # replayed against another membership.
    assert unsubscribe_token("t1", "m1") == unsubscribe_token("t1", "m1")
    assert unsubscribe_token("t1", "m1") != unsubscribe_token("t1", "m2")
    assert unsubscribe_token("t1", "m1") != unsubscribe_token("t2", "m1")
