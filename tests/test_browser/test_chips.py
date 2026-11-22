"""Chips and BigNumber accents take the theme's colours and stay readable (#27)."""
from __future__ import annotations

import typing as t

import pytest

import briefing as bf
from tests.test_browser.conftest import Viewer
from tests.test_browser.test_alert_colours import _COLOURS, _PRESETS, _contrast

_RGB = """e => { const c = document.createElement('canvas').getContext('2d');
  c.fillStyle = getComputedStyle(e).boxShadow.match(/(rgb|oklab|#)[^)]*\\)?/)[0]; c.fillRect(0, 0, 1, 1);
  return Array.from(c.getImageData(0, 0, 1, 1).data.slice(0, 3)); }"""


@pytest.mark.parametrize("preset", list(_PRESETS))
def test_every_chip_reads_in_every_preset(viewer: Viewer, preset: str) -> None:
    chips = bf.Chips(["Plain", bf.Chip("Up", color="up"), bf.Chip("Down", color="down"),
                      bf.Chip("Accent", color="accent"), bf.Chip("Teal", color="#0d9488")])
    page = viewer.open(bf.Briefing(chips), formatting=_PRESETS[preset])
    for chip in page.locator(".bf-chip").all():
        background, text = t.cast("list[list[int]]", chip.evaluate(_COLOURS))
        assert _contrast(background, text) >= 4.5, (preset, chip.inner_text(), background, text)


def test_the_accent_stripe_takes_the_theme_up_colour(viewer: Viewer) -> None:
    page = viewer.open(bf.Briefing(bf.BigNumber("Up", 14, accent="up")),
                       formatting=bf.Formatting(up_color="#e8692a"))
    assert page.locator(".bf-bignumber").evaluate(_RGB) == [232, 105, 42]


def test_the_arrows_take_the_theme_colours(viewer: Viewer) -> None:
    # An arrow without a verdict takes the theme's up colour; is_positive_intent stays green or red.
    page = viewer.open(bf.Briefing(bf.BigNumber("Up", 2, change="+1", is_upward_change=True)),
                       formatting=bf.Formatting(up_color="rgb(1, 2, 3)"))
    assert page.locator(".bf-bignumber__change").evaluate("e => getComputedStyle(e).color") == "rgb(1, 2, 3)"
