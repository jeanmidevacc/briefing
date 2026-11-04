"""A hovered toggle header stays readable in every theme (#73)."""
from __future__ import annotations

import pytest

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


@pytest.mark.parametrize("theme", list(_THEMES))
def test_hovered_header_keeps_contrast(viewer: Viewer, theme: str) -> None:
    page = viewer.open(bf.Briefing(bf.Toggle(bf.Text("body"), label="Details")), formatting=_THEMES[theme])
    header = page.locator(".bf-toggle__header")
    header.hover()
    page.wait_for_timeout(100)
    fg, bg = header.evaluate("e => { const s = getComputedStyle(e); return [s.color, s.backgroundColor]; }")
    ratio = page.evaluate(CONTRAST_JS, [fg, bg])
    assert ratio >= 4.5, f"{theme}: hovered header {fg} on {bg} has contrast {ratio:.2f}"


def test_default_theme_hover_looks_as_before(viewer: Viewer) -> None:
    page = viewer.open(bf.Briefing(bf.Toggle(bf.Text("body"), label="Details")))
    header = page.locator(".bf-toggle__header")
    header.hover()
    page.wait_for_timeout(100)
    # color-mix() computes to oklab(...); a canvas turns any CSS colour into sRGB bytes.
    channels: list[int] = header.evaluate(
        "e => { const c = document.createElement('canvas').getContext('2d');"
        " c.fillStyle = getComputedStyle(e).backgroundColor; c.fillRect(0, 0, 1, 1);"
        " return Array.from(c.getImageData(0, 0, 1, 1).data).slice(0, 3); }"
    )
    before = (0xF3, 0xF4, 0xF6)  # 0.1.1's hard-coded #f3f4f6
    assert max(abs(a - b) for a, b in zip(channels, before, strict=True)) <= 8, channels
