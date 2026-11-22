"""In a dark theme, table stripes and the header hover come from the theme, not from fixed light greys (#150)."""
from __future__ import annotations

import pandas as pd

import briefing as bf
from tests.test_browser.conftest import Viewer


def test_dark_theme_tables_stay_dark(viewer: Viewer) -> None:
    frame = pd.DataFrame({"n": [1, 2, 3, 4]})
    page = viewer.open(bf.Briefing(bf.DataTable(frame), bf.Table(frame), bf.Text("| a |\n|---|\n| 1 |\n| 2 |")),
                       formatting=bf.Formatting.dark())
    surface = page.evaluate("getComputedStyle(document.querySelector('.bf-report')).getPropertyValue('--bf-surface')")
    stripes = page.locator("tr:nth-child(even) td").evaluate_all(
        "cells => cells.map(c => getComputedStyle(c).backgroundColor)")
    probe = page.evaluate("c => { const d = document.createElement('div'); d.style.color = c; document.body.append(d);"
                          " const v = getComputedStyle(d).color; d.remove(); return v; }", surface.strip())
    assert stripes and set(stripes) == {probe}  # every stripe is the theme's surface colour
    header = page.locator(".bf-dt__th").first
    header.hover()
    lightness = header.evaluate("""h => {  // the computed colour may be oklab(): read it back as RGB
        const c = document.createElement('canvas').getContext('2d');
        c.fillStyle = getComputedStyle(h).backgroundColor; c.fillRect(0, 0, 1, 1);
        const [r, g, b] = c.getImageData(0, 0, 1, 1).data;
        return (Math.max(r, g, b) + Math.min(r, g, b)) / 510; }""")
    assert lightness < 0.5  # a dark hover, not #f0f0f0
