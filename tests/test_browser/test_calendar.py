"""lab.CalendarHeatmap as a reader sees it (#19)."""
from __future__ import annotations

import pandas as pd
import pytest

import briefing as bf
from tests.test_browser.conftest import Viewer


@pytest.mark.parametrize("theme", ["default", "dark"])
def test_zero_no_data_and_below_target_are_visibly_different(viewer: Viewer, df_pipeline_log: pd.DataFrame,
                                                             theme: str) -> None:
    formatting = bf.Formatting.dark() if theme == "dark" else bf.Formatting()
    block = bf.lab.CalendarHeatmap(df_pipeline_log, date="run_at", value="rows", expected=500)
    page = viewer.open(bf.Briefing(block), formatting=formatting)

    def look(day: str) -> dict[str, str]:
        style: dict[str, str] = page.locator(f'rect[data-date="{day}"]').evaluate(
            "e => { const s = getComputedStyle(e); return {fill: s.fill, stroke: s.stroke, dash: s.strokeDasharray}; }")
        return style

    background = page.evaluate("() => getComputedStyle(document.body).backgroundColor")
    zero, empty, ok = look("2025-12-04"), look("2026-01-17"), look("2025-11-18")
    assert zero["fill"] not in ("none", background)  # a zero is a filled grey cell
    assert empty["fill"] == "none"  # no data is an outline only
    assert look("2026-01-03")["stroke"] == "rgb(220, 38, 38)"  # a failed run is flagged red
    assert ok["stroke"] in ("none", "")  # a normal day has no outline


def test_the_calendar_fits_its_cells(viewer: Viewer, df_pipeline_log: pd.DataFrame) -> None:
    page = viewer.open(bf.Briefing(bf.lab.CalendarHeatmap(df_pipeline_log, date="run_at")))
    box = page.locator('rect[data-date="2026-01-05"]').bounding_box()
    assert box is not None and box["width"] == pytest.approx(11, abs=0.5)
