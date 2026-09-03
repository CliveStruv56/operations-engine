"""One place PDFs are rendered, so one place decides what WeasyPrint may fetch.

WeasyPrint resolves every absolute URL it meets while laying a document out —
`<img src>`, CSS `url()`, `@import` — and its default fetcher performs a real
network request to do it. The worker sits inside the Railway private network
alongside Postgres, Redis and the LiteLLM gateway, none of which are reachable
from outside it, so a document carrying an attacker-chosen URL is a
server-side request forgery primitive pointed at exactly the things that are
otherwise unreachable.

`answer_pdf` is the live route: it renders assistant markdown, which a tenant
member steers and which retrieved documents and web results can influence.
`html: False` stops raw HTML but not `![](http://…)`, because markdown image
syntax is markdown, not HTML. The other three templates escape every field, so
they are not exploitable today — but "the template escapes it" is a property
that lasts until someone adds a field, whereas a fetcher that refuses is a
property of the renderer. All four go through here.

`data:` URIs still work: they carry their own bytes and reach no network.
"""

from typing import Any
from urllib.parse import urlsplit


class RemoteResourceBlocked(Exception):
    """A document asked WeasyPrint to fetch a remote URL.

    Never raised by normal rendering — every template embeds what it needs, and
    `answer_pdf` disables the markdown image rule as well, so an injected image
    is dropped before it reaches HTML. Reaching this means either a template
    grew a remote asset (use a `data:` URI) or something is injecting URLs into
    a document, which is worth a Sentry event rather than a silent omission.
    """


def deny_remote_resources(url: str) -> dict[str, Any]:
    """URL fetcher that serves `data:` URIs and refuses every network scheme."""
    if urlsplit(url).scheme == "data":
        from weasyprint.urls import default_url_fetcher

        return default_url_fetcher(url)
    # The scheme only: a blocked URL is attacker-authored and does not belong
    # in logs or Sentry breadcrumbs verbatim.
    raise RemoteResourceBlocked(
        f"PDF rendering blocked a remote resource (scheme: {urlsplit(url).scheme or 'relative'})"
    )


def render_pdf(html_text: str) -> bytes:
    from weasyprint import HTML  # lazy: needs system pango/cairo

    return HTML(string=html_text, url_fetcher=deny_remote_resources).write_pdf()
