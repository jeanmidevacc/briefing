"""Code blocks show token colours that follow the theme (#5)."""
from __future__ import annotations

import pytest
from playwright.sync_api import Page

import briefing as bf
from tests.test_browser.conftest import CONTRAST_JS, Viewer

_THEMES = {
    "default": bf.Formatting(),
    "dark": bf.Formatting.dark(),
    "corporate": bf.Formatting.corporate(),
    "minimal": bf.Formatting.minimal(),
    "ocean": bf.Formatting.ocean(),
    "warm": bf.Formatting.warm(),
}
_PYTHON = "def area(r):\n    # circle\n    return 3.14 * r ** 2  # 'pi r squared'\nprint(area(2), 'done')"
_SQL = "SELECT name, COUNT(*) FROM users WHERE id > 10 AND name = 'x' -- recent"



def _token_colours(page: Page, nth: int) -> dict[str, str]:
    colours: dict[str, str] = page.locator(".bf-code code").nth(nth).evaluate(
        "code => Object.fromEntries(Array.from(code.querySelectorAll('span')).map("
        "s => [s.className, getComputedStyle(s).color]))"
    )
    return colours


@pytest.mark.parametrize("theme", list(_THEMES))
def test_tokens_are_coloured_and_readable(viewer: Viewer, theme: str) -> None:
    report = bf.Briefing(bf.Code(_PYTHON, language="python"), bf.Code(_SQL, language="sql"))
    page = viewer.open(report, formatting=_THEMES[theme])
    background = page.locator(".bf-code").first.evaluate("e => getComputedStyle(e).backgroundColor")
    plain = page.locator(".bf-code code").first.evaluate("e => getComputedStyle(e).color")
    for nth, language in enumerate(["python", "sql"]):
        colours = _token_colours(page, nth)
        for cls in ("k", "s1", "c1" if language == "python" else "c1"):
            assert cls in colours, f"{language}: no .{cls} token"
        # keywords, strings and comments each get their own colour, unlike plain text
        assert len({colours["k"], colours["s1"], colours["c1"], plain}) == 4, (language, colours)
        for cls, colour in colours.items():
            ratio = page.evaluate(CONTRAST_JS, [colour, background])
            assert ratio >= 4.5, f"{theme}/{language}: .{cls} {colour} on {background} has contrast {ratio:.2f}"


def test_colours_follow_the_theme(viewer: Viewer) -> None:
    light = _token_colours(viewer.open(bf.Briefing(bf.Code(_PYTHON))), 0)
    dark = _token_colours(viewer.open(bf.Briefing(bf.Code(_PYTHON)), formatting=bf.Formatting.dark()), 0)
    assert light["k"] != dark["k"] and light["s1"] != dark["s1"]
