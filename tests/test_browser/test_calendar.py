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


def test_a_tab_switches_between_the_day_and_hour_views(viewer: Viewer, df_pipeline_log: pd.DataFrame) -> None:
    page = viewer.open(bf.Briefing(bf.lab.CalendarHeatmap(df_pipeline_log, date="run_at", views=("days", "hours"))))
    days, hours = page.locator("svg.bf-cal__days"), page.locator("svg.bf-cal__hours")
    assert days.is_visible() and not hours.is_visible()
    page.get_by_role("tab", name="Hours").click()
    assert hours.is_visible() and not days.is_visible()
    assert page.locator("rect.bf-cal__hour").count() == 7 * 24


def test_hour_view_labels_are_small(viewer: Viewer, df_pipeline_log: pd.DataFrame) -> None:
    page = viewer.open(bf.Briefing(bf.lab.CalendarHeatmap(df_pipeline_log, date="run_at", views=("hours",))))
    size = page.locator("svg.bf-cal__hours text").first.evaluate("e => getComputedStyle(e).fontSize")
    assert size == "9px"


def test_clicking_a_day_lists_its_rows(viewer: Viewer, df_pipeline_log: pd.DataFrame) -> None:
    page = viewer.open(bf.Briefing(bf.lab.CalendarHeatmap(df_pipeline_log, date="run_at", on_click="rows")))
    panel = page.locator(".bf-cal__panel")
    assert not panel.is_visible()
    page.locator('rect[data-date="2025-12-07"]').click()
    assert panel.is_visible()
    assert "2025-12-07" in panel.locator(".bf-cal__panel-title").inner_text()
    assert panel.locator("tbody tr").count() == 2
    assert panel.locator("thead th").all_inner_texts() == ["run_at", "team", "rows"]
    panel.get_by_role("button", name="Close").click()
    assert not panel.is_visible()


def test_keyboard_opens_the_rows_of_an_hour(viewer: Viewer, df_pipeline_log: pd.DataFrame) -> None:
    block = bf.lab.CalendarHeatmap(df_pipeline_log, date="run_at", views=("hours",), on_click="rows")
    page = viewer.open(bf.Briefing(block))
    page.locator('rect[data-hour="0-6"]').focus()
    page.keyboard.press("Enter")
    assert "Mon 06:00" in page.locator(".bf-cal__panel-title").inner_text()


def test_capped_cells_say_so_and_values_stay_text(viewer: Viewer) -> None:
    df = pd.DataFrame({"run_at": [pd.Timestamp("2026-01-05 09:00")] * 120,
                       "note": ["<img src=x onerror=window.__hit=1>"] * 120})
    page = viewer.open(bf.Briefing(bf.lab.CalendarHeatmap(df, date="run_at", on_click="rows")))
    page.locator('rect[data-date="2026-01-05"]').click()
    panel = page.locator(".bf-cal__panel")
    assert panel.locator("tbody tr").count() == 50
    assert "first 50 of 120 rows" in panel.inner_text()
    assert panel.locator("img").count() == 0 and page.evaluate("() => window.__hit") is None
