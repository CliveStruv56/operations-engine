"""PDF rendering never reaches the network.

The worker runs inside the private network beside Postgres, Redis and the
LiteLLM gateway. WeasyPrint's default URL fetcher would resolve any absolute
URL in a document from that position, and `answer_pdf` renders assistant
markdown, which tenant members steer and retrieved documents influence.
"""

import pytest

from worker.answer_pdf import _MD
from worker.pdf import RemoteResourceBlocked, deny_remote_resources


@pytest.mark.parametrize(
    "url",
    [
        "http://litellm.railway.internal:4000/health",
        "https://attacker.example/pixel.png",
        "file:///etc/passwd",
        "//attacker.example/protocol-relative.png",
    ],
)
def test_remote_resources_are_refused(url: str):
    with pytest.raises(RemoteResourceBlocked):
        deny_remote_resources(url)


def test_blocked_message_does_not_echo_the_url():
    """A blocked URL is attacker-authored; it must not land in logs verbatim."""
    with pytest.raises(RemoteResourceBlocked) as exc:
        deny_remote_resources("https://attacker.example/secret-path?data=leaked")
    assert "attacker.example" not in str(exc.value)
    assert "leaked" not in str(exc.value)


def test_markdown_images_never_become_img_tags():
    """`html: False` does not cover markdown image syntax — disabling does.

    Without this an assistant reply ending `![](http://internal/…)` renders an
    <img>, and rendering the page fetches it. With the rule disabled the same
    input degrades to a literal `!` followed by an ordinary link: the URL is
    still *present* in the document, which is fine and deliberate — WeasyPrint
    resolves `src`, not `href`, so nothing is requested while laying the page
    out, and answers legitimately contain links (every citation is one). The
    property under test is that no fetchable element is produced.
    """
    rendered = _MD.render("Answer text.\n\n![](http://litellm.railway.internal:4000/health)\n")
    assert "<img" not in rendered
    assert "src=" not in rendered


def test_raw_html_images_stay_escaped():
    rendered = _MD.render('Answer.\n\n<img src="http://attacker.example/x.png">\n')
    assert "<img" not in rendered
