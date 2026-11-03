"""HTML blocks get the same typography as Text blocks (#47)."""
from __future__ import annotations

import pytest
from playwright.sync_api import Page

import briefing as bf
from tests.test_browser.conftest import Viewer

_MARKDOWN = (
    "## Heading\n\nFirst paragraph with a [link](#x) and `code`.\n\nSecond paragraph.\n\n"
    "- one\n- two\n\n1. first\n\n> quoted"
)
_MARKUP = (
    '<h2>Heading</h2><p>First paragraph with a <a href="#x">link</a> and <code>code</code>.</p>'
    "<p>Second paragraph.</p><ul><li>one</li><li>two</li></ul><ol><li>first</li></ol>"
    "<blockquote><p>quoted</p></blockquote>"
)
_PROPS = [
    "marginTop", "marginBottom", "paddingLeft", "paddingTop", "fontSize", "fontWeight", "lineHeight",
    "color", "backgroundColor", "borderLeftWidth", "textDecorationLine", "fontFamily",
]
_SELECTORS = ["h2", "p", "ul", "ol", "li", "a", "code", "blockquote"]
_THEMES = {
    "default": bf.Formatting(),
    "dark": bf.Formatting.dark(),
    "corporate": bf.Formatting.corporate(),
    "minimal": bf.Formatting.minimal(),
    "ocean": bf.Formatting.ocean(),
    "warm": bf.Formatting.warm(),
}


def _styles(page: Page, selector: str) -> dict[str, str]:
    js = f"e => {{ const s = getComputedStyle(e); return Object.fromEntries({_PROPS!r}.map(p => [p, s[p]])); }}"
    styles: dict[str, str] = page.locator(selector).first.evaluate(js)
    return styles


@pytest.mark.parametrize("theme", list(_THEMES))
def test_html_block_matches_text_block(viewer: Viewer, theme: str) -> None:
    page = viewer.open(bf.Briefing(bf.Text(_MARKDOWN), bf.HTML(_MARKUP)), formatting=_THEMES[theme])
    for selector in _SELECTORS:
        assert _styles(page, f".bf-html {selector}") == _styles(page, f".bf-text {selector}"), selector


def test_inline_styles_in_html_still_win(viewer: Viewer) -> None:
    markup = '<p style="margin-bottom: 40px; color: rgb(255, 0, 0)">custom</p><ul style="padding-left: 0">x</ul>'
    page = viewer.open(bf.Briefing(bf.HTML(markup)))
    p, ul = _styles(page, ".bf-html p"), _styles(page, ".bf-html ul")
    assert (p["marginBottom"], p["color"], ul["paddingLeft"]) == ("40px", "rgb(255, 0, 0)", "0px")


def test_text_block_spacing_is_unchanged(viewer: Viewer) -> None:
    # The values measured in #47 before the fix.
    page = viewer.open(bf.Briefing(bf.Text(_MARKDOWN)))
    assert _styles(page, ".bf-text p")["marginBottom"] == "12px"
    assert _styles(page, ".bf-text ul")["paddingLeft"] == "24px"
