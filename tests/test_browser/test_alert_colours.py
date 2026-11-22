"""Alerts take the theme's colours, keeping each level's hue, and stay readable (#167)."""
from __future__ import annotations

import typing as t

import pytest

import briefing as bf
from tests.test_browser.conftest import Viewer

_LEVELS = ("info", "success", "warning", "error")
_PRESETS = {"default": bf.Formatting(), "dark": bf.Formatting.dark(), "corporate": bf.Formatting.corporate(),
            "minimal": bf.Formatting.minimal(), "ocean": bf.Formatting.ocean(), "warm": bf.Formatting.warm()}

#: An element's background and text colours as RGB, read back through a canvas (they may be oklab()).
_COLOURS = """a => { const c = document.createElement('canvas').getContext('2d', {willReadFrequently: true});
  const rgb = v => { c.clearRect(0, 0, 1, 1); c.fillStyle = v; c.fillRect(0, 0, 1, 1);
    return Array.from(c.getImageData(0, 0, 1, 1).data.slice(0, 3)); };
  const s = getComputedStyle(a); return [rgb(s.backgroundColor), rgb(s.color)]; }"""


def _luminance(rgb: list[int]) -> float:
    def channel(v: int) -> float:
        c = v / 255
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (channel(v) for v in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _contrast(a: list[int], b: list[int]) -> float:
    hi, lo = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


@pytest.mark.parametrize("preset", list(_PRESETS))
def test_every_level_reads_in_every_preset(viewer: Viewer, preset: str) -> None:
    report = bf.Briefing(*(bf.Alert(f"A {level} message.", level=level, title=level.title()) for level in _LEVELS))
    page = viewer.open(report, formatting=_PRESETS[preset])
    page_bg = _luminance(t.cast("list[int]", page.locator("body").evaluate(_COLOURS)[0]))
    for alert in page.locator(".bf-alert").all():
        background, text = t.cast("list[list[int]]", alert.evaluate(_COLOURS))
        assert _contrast(background, text) >= 4.5, (preset, alert.get_attribute("class"), background, text)
        # The alert's background stays on the side of the page's: dark in dark themes, light in light ones.
        assert (_luminance(background) < 0.2) == (page_bg < 0.2), (preset, background)
