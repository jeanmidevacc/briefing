"""HTML blocks get the same typography as Text blocks (#47)."""
from __future__ import annotations

import pytest
from playwright.sync_api import Page

import briefing as bf
from tests.test_browser.conftest import Viewer

_MARKDOWN = "## Heading\n\nFirst paragraph.\n\nSecond paragraph.\n\n- one\n- two\n\n> quoted"
_MARKUP = "<h2>Heading</h2><p>First paragraph.</p><p>Second paragraph.</p><ul><li>one</li><li>two</li></ul>" \
          "<blockquote><p>quoted</p></blockquote>"
_PROPS = ["marginTop", "marginBottom", "paddingLeft", "fontSize", "lineHeight"]


def _styles(page: Page, block: str, selector: str) -> dict[str, str]:
    props = repr(_PROPS)
    styles: dict[str, str] = page.locator(f".{block} {selector}").first.evaluate(
        f"e => {{ const s = getComputedStyle(e); return Object.fromEntries({props}.map(p => [p, s[p]])); }}"
    )
    return styles


@pytest.mark.xfail(reason="#47: the CSS reset strips spacing from HTML blocks", strict=True)
@pytest.mark.parametrize("selector", ["h2", "p", "ul", "blockquote"])
def test_html_block_matches_text_block(viewer: Viewer, selector: str) -> None:
    page = viewer.open(bf.Briefing(bf.Text(_MARKDOWN), bf.HTML(_MARKUP)))
    assert _styles(page, "bf-html", selector) == _styles(page, "bf-text", selector)
