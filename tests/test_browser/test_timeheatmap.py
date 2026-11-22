"""lab.TimeHeatmap as a reader sees it (#111): the calendar's tooltip, rows panel and width fitting."""
from __future__ import annotations

import pandas as pd
from playwright.sync_api import expect

import briefing as bf
from tests.test_browser.conftest import Viewer


def _block(**kwargs: object) -> bf.lab.TimeHeatmap:
    stamps = pd.to_datetime(["2026-01-05 09:10", "2026-01-05 09:20", "2026-01-12 09:05", "2026-01-06 14:00"])
    runs = pd.DataFrame({"run_at": stamps, "rows": [10, 20, 40, 5], "team": ["a", "a", "a", "b"]})
    return bf.lab.TimeHeatmap(runs, date="run_at", rows="weekday", columns="hour", **kwargs)  # type: ignore[arg-type]


def test_hovering_a_cell_shows_its_average_and_total(viewer: Viewer) -> None:
    page = viewer.open(_block())
    page.locator('rect[data-cell="0-9"]').hover()
    tip = page.locator(".bf-cal__tip")
    expect(tip).to_be_visible()
    assert tip.inner_text().splitlines() == ["Mon 09:00", "1.5 rows on average", "3 over 2 hours"]


def test_no_data_and_values_look_different(viewer: Viewer) -> None:
    page = viewer.open(_block())

    def fill(cell: str) -> str:
        value: str = page.locator(f'rect[data-cell="{cell}"]').evaluate("e => getComputedStyle(e).fill")
        return value

    assert fill("2-9") == "none"  # no data: an outline
    assert fill("0-9") not in ("none", "")


def test_clicking_a_cell_lists_its_rows(viewer: Viewer) -> None:
    page = viewer.open(_block(group="team", on_click="rows"))
    panel = page.locator(".bf-cal__panel")
    expect(panel).to_be_hidden()
    page.locator('.bf-cal__calendar[data-group="a"] rect[data-cell="0-9"]').click()
    expect(panel).to_be_visible()
    assert panel.locator(".bf-cal__panel-title").inner_text() == "Mon 09:00 · a · 3 rows"
    assert panel.locator("tbody tr").count() == 3
    page.locator('.bf-cal__calendar[data-group="b"] rect[data-cell="1-14"]').focus()
    page.keyboard.press("Enter")
    assert panel.locator(".bf-cal__panel-title").inner_text() == "Tue 14:00 · b · 1 row"


def test_the_grid_fills_the_width_of_its_block(viewer: Viewer) -> None:
    page = viewer.open(_block())
    widths = page.locator("svg.bf-cal__grid").evaluate(
        "s => [s.getBoundingClientRect().width, Number(s.getAttribute('width')),"
        " s.closest('.bf-block').getBoundingClientRect().width]")
    shown, natural, block = widths
    assert shown == min(block, 2 * natural)  # up to twice its natural size, as the calendar does (#106)
    k = page.locator("figure.bf-timeheatmap").evaluate("f => f.style.getPropertyValue('--bf-cal-k')")
    assert abs(float(k) - shown / natural) < 1e-6


def test_the_rows_panel_follows_each_group_in_a_custom_order(viewer: Viewer) -> None:
    page = viewer.open(_block(group="team", group_order=["b"], on_click="rows"))
    assert page.locator(".bf-cal__group").all_inner_texts() == ["b", "a"]
    panel = page.locator(".bf-cal__panel")
    page.locator('.bf-cal__calendar[data-group="a"] rect[data-cell="0-9"]').click()
    assert panel.locator(".bf-cal__panel-title").inner_text() == "Mon 09:00 · a · 3 rows"
    page.locator('.bf-cal__calendar[data-group="b"] rect[data-cell="1-14"]').click()
    assert panel.locator(".bf-cal__panel-title").inner_text() == "Tue 14:00 · b · 1 row"
