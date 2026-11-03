"""A formula displays as typeset math, offline and without JavaScript (#3)."""
from __future__ import annotations

import briefing as bf
from tests.test_browser.conftest import Viewer


def test_fraction_is_typeset(viewer: Viewer) -> None:
    page = viewer.open(bf.Briefing(bf.Formula(r"\frac{a}{b}")))
    num = page.locator("mfrac > :first-child").bounding_box()
    den = page.locator("mfrac > :last-child").bounding_box()
    assert num is not None and den is not None
    assert num["y"] + num["height"] <= den["y"] + 1  # numerator sits above the denominator
    assert page.locator(".bf-formula").inner_text().strip() not in (r"\frac{a}{b}", r"\(\frac{a}{b}\)")
