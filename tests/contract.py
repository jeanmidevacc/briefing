"""HTML contract: rules every rendered briefing report must follow.

Each rule is a small function that takes a parsed report and raises
``AssertionError`` naming what broke. ``tests/test_contract.py`` runs every rule
against every report the suite builds, and checks that each rule rejects a
hand-made bad report.
"""
from __future__ import annotations

import base64
import binascii
import json
import re
from collections import Counter
from collections.abc import Callable, Iterator

from bs4 import BeautifulSoup, Tag

from tests.html_helpers import attr, classes, parse

#: Put into every user-supplied string by the escaping scenarios. It must never
#: come back as live markup: an event handler, or a script that would run.
MARKER = "bf_xss"
PAYLOAD = f"<script>{MARKER}()</script></script><img src=x onerror={MARKER}()> & \"quotes\""

_EXTERNAL = re.compile(r"^\s*(?:https?:)?//", re.IGNORECASE)
_CSS_EXTERNAL = re.compile(r"""(?:url\(\s*['"]?|@import\s+['"])\s*(?:https?:)?//""", re.IGNORECASE)
# Attributes that make the browser fetch something. Hyperlinks (<a href>) are
# navigation, not part of the page, so they may point anywhere.
_RESOURCE_ATTRS = ("src", "href", "xlink:href", "srcset", "poster")
_HYPERLINK_TAGS = ("a", "area")
# A markdown pipe-table delimiter row, e.g. "| --- | :-: |", left as plain text.
_PIPE_TABLE_DELIMITER = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$", re.MULTILINE)


def parse_report(html: str) -> BeautifulSoup:
    """Parse a rendered report (or any HTML document) for the rules below."""
    return parse(html)


def embedded_documents(soup: Tag) -> Iterator[BeautifulSoup]:
    """Yield the documents nested in ``<iframe srcdoc>`` and ``data:text/html`` iframes."""
    for frame in soup.find_all("iframe"):
        srcdoc = frame.get("srcdoc")
        if isinstance(srcdoc, str):
            yield parse_report(srcdoc)
        src = frame.get("src")
        if isinstance(src, str) and src.startswith("data:text/html"):
            meta, _, payload = src.partition(",")
            try:
                text = base64.b64decode(payload).decode() if meta.endswith(";base64") else payload
            except (binascii.Error, UnicodeDecodeError) as exc:
                raise AssertionError(f"undecodable iframe data URL: {src[:60]}…") from exc
            yield parse_report(text)


# ── rules ─────────────────────────────────────────────────────────────────────


def check_no_external_urls(soup: Tag) -> None:
    """No ``src``, ``href`` or CSS ``url()`` points off the page, nested iframes included."""
    for tag in soup.find_all(True):
        for name in _RESOURCE_ATTRS:
            value = tag.get(name)
            if not isinstance(value, str) or (name == "href" and tag.name in _HYPERLINK_TAGS):
                continue
            assert not _EXTERNAL.match(value), f"<{tag.name} {name}={value!r}> loads an external resource"
        style = tag.get("style")
        if isinstance(style, str):
            assert not _CSS_EXTERNAL.search(style), f"<{tag.name} style> loads an external resource: {style!r}"
    for sheet in soup.find_all("style"):
        match = _CSS_EXTERNAL.search(sheet.get_text())
        assert match is None, f"<style> loads an external resource near {match.group(0)!r}"
    for doc in embedded_documents(soup):
        check_no_external_urls(doc)


def check_unique_ids(soup: Tag) -> None:
    """Every DOM ``id`` appears once."""
    counts = Counter(attr(tag, "id") for tag in soup.find_all(id=True))
    duplicates = sorted(i for i, n in counts.items() if n > 1)
    assert not duplicates, f"duplicate ids: {duplicates[:10]}"


def check_aria_references(soup: Tag) -> None:
    """Every ``aria-controls`` / ``aria-labelledby`` names ids that exist."""
    ids = {attr(tag, "id") for tag in soup.find_all(id=True)}
    for name in ("aria-controls", "aria-labelledby"):
        for tag in soup.select(f"[{name}]"):
            missing = [ref for ref in attr(tag, name).split() if ref not in ids]
            assert not missing, f"<{tag.name} {name}> points to missing ids {missing}"


def check_json_scripts_parse(soup: Tag) -> None:
    """Every ``<script type="application/json">`` holds valid JSON."""
    for script in soup.find_all("script", attrs={"type": "application/json"}):
        try:
            json.loads(script.get_text())
        except ValueError as exc:
            raise AssertionError(f"<script type=application/json class={script.get('class')}> is not JSON") from exc


def check_user_text_escaped(soup: Tag, marker: str = MARKER) -> None:
    """User text holding *marker* never becomes an event handler or a runnable script."""
    for tag in soup.find_all(True):
        for name, value in tag.attrs.items():
            if name.startswith("on"):
                assert marker not in str(value), f"<{tag.name} {name}> runs user text"
    for script in soup.find_all("script"):
        if script.get("type") != "application/json":
            assert marker not in script.get_text(), "user text inside a runnable <script>"


def check_markdown_rendered(soup: Tag) -> None:
    """Markdown in ``Text`` blocks becomes elements: no pipe table is left as text."""
    for block in soup.select(".bf-text"):
        match = _PIPE_TABLE_DELIMITER.search(block.get_text())
        assert match is None, f"markdown table left as text: {match.group(0).strip()!r}"


def check_document_head(soup: Tag) -> None:
    """The page has exactly one ``<title>`` and declares its language."""
    # SVG <title> elements are tooltips, not the document title.
    titles = [t for t in soup.find_all("title") if t.find_parent("svg") is None]
    assert len(titles) == 1, f"expected one <title>, found {len(titles)}"
    html = soup.find("html")
    assert isinstance(html, Tag), "no <html> element"
    assert html.get("lang"), "<html> has no lang attribute"


def check_generator_meta(soup: Tag) -> None:
    """The page names the briefing version in ``<meta name="generator">`` (#23)."""
    import briefing

    meta = soup.find("meta", attrs={"name": "generator"})
    assert isinstance(meta, Tag), 'no <meta name="generator">'
    assert attr(meta, "content") == f"briefing {briefing.__version__}", f"generator is {meta.get('content')!r}"


#: The rules that inspect one parsed report, by name.
RULES: dict[str, Callable[[Tag], None]] = {
    "no_external_urls": check_no_external_urls,
    "unique_ids": check_unique_ids,
    "aria_references": check_aria_references,
    "json_scripts_parse": check_json_scripts_parse,
    "markdown_rendered": check_markdown_rendered,
    "document_head": check_document_head,
    "generator_meta": check_generator_meta,
}


def check_deterministic(render: Callable[[], str]) -> None:
    """Two calls to *render* give byte-identical output (run with ``SOURCE_DATE_EPOCH`` set)."""
    first, second = render(), render()
    if first != second:
        pairs = enumerate(zip(first, second, strict=False))
        at = next((i for i, (a, b) in pairs if a != b), min(len(first), len(second)))
        raise AssertionError(f"renders differ at byte {at}: {first[at - 40:at + 40]!r} vs {second[at - 40:at + 40]!r}")


# ── fragments (#122): one <div class="bf-embed"> that keeps to itself ─────────

_CSS_COMMENT = re.compile(r"/\*.*?\*/", re.S)
_CSS_STRING = re.compile(r""""[^"]*"|'[^']*'""")


def fragment_root(soup: Tag) -> Tag:
    """The fragment's root: its one top-level element, a ``div.bf-embed``."""
    tops = [child for child in soup.children if isinstance(child, Tag)]
    assert len(tops) == 1 and tops[0].name == "div" and "bf-embed" in classes(tops[0]), (
        f"a fragment is one <div class=bf-embed>, not {[t.name for t in tops]}"
    )
    return tops[0]


def css_selectors(css: str) -> list[str]:
    """Every selector of a stylesheet, at-rule bodies included."""
    css = _CSS_STRING.sub('""', _CSS_COMMENT.sub("", css))
    selectors = []
    for prelude in re.findall(r"([^{};]+)\{", css):
        if prelude.strip().startswith("@"):
            continue
        depth, start = 0, 0
        for i, char in enumerate(prelude + ","):
            depth += (char in "([") - (char in ")]")
            if char == "," and depth == 0:
                selectors.append(" ".join(prelude[start:i].split()))
                start = i + 1
    return [s for s in selectors if s]


def check_fragment_shape(soup: Tag) -> None:
    """No ``<html>``, ``<head>`` or ``<body>``: one root ``<div>`` naming the briefing version."""
    import briefing

    assert soup.find(["html", "head", "body"]) is None, "a fragment has no <html>, <head> or <body>"
    root = fragment_root(soup)
    assert attr(root, "id"), "the fragment's root has no id"
    assert attr(root, "data-bf-version") == briefing.__version__


def check_fragment_selectors(soup: Tag) -> None:
    """Every CSS selector starts at the fragment: ``.bf-embed``, or an id that starts with its embed id."""
    embed_id = re.escape(attr(fragment_root(soup), "id"))
    scoped = re.compile(rf"(?:\.bf-embed|#{embed_id}(?:-[\w-]*)?)(?![\w-])")
    for sheet in soup.find_all("style"):
        loose = [s for s in css_selectors(sheet.get_text()) if not scoped.match(s)]
        assert not loose, f"selectors that reach outside the fragment: {loose[:5]}"


def check_fragment_ids(soup: Tag) -> None:
    """Every id starts with the embed id (the root's id), SVG ids included."""
    embed_id = attr(fragment_root(soup), "id")
    ids = [attr(tag, "id") for tag in soup.find_all(id=True)]
    stray = [i for i in ids if i != embed_id and not i.startswith(f"{embed_id}-")]
    assert not stray, f"ids that don't start with {embed_id!r}: {stray[:5]}"


#: The rules every fragment follows: the report rules that apply to a part of a page, and its own.
FRAGMENT_RULES: dict[str, Callable[[Tag], None]] = {
    "no_external_urls": check_no_external_urls,
    "unique_ids": check_unique_ids,
    "aria_references": check_aria_references,
    "json_scripts_parse": check_json_scripts_parse,
    "markdown_rendered": check_markdown_rendered,
    "fragment_shape": check_fragment_shape,
    "fragment_selectors": check_fragment_selectors,
    "fragment_ids": check_fragment_ids,
}
