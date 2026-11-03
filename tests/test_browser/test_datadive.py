"""DataDive draws one dot per row and redraws when an axis changes."""
from __future__ import annotations

import pandas as pd

import briefing as bf
from tests.test_browser.conftest import Viewer


def test_one_dot_per_row_and_redraw_on_axis_change(viewer: Viewer) -> None:
    df = pd.DataFrame({"a": range(40), "b": [(i * 7) % 40 for i in range(40)], "c": [i % 3 for i in range(40)]})
    page = viewer.open(bf.Briefing(bf.lab.DataDive(df, x="a", y="b")))
    dots = page.locator(".bf-dd__dot")
    assert dots.count() == 40
    before = dots.evaluate_all("ds => ds.map(d => d.getAttribute('cx'))")
    page.locator('select[data-axis="x"]').select_option("b")
    after = dots.evaluate_all("ds => ds.map(d => d.getAttribute('cx'))")
    assert dots.count() == 40
    assert before != after
