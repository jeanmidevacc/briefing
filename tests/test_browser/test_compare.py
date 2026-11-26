"""DataCompare as a reader uses it: sort, search and filter the columns, redraw the charts (#17)."""
from __future__ import annotations

import re
import typing as t

import pandas as pd
from playwright.sync_api import Locator, Page, expect

import briefing as bf
from tests.test_browser.conftest import Viewer

_TRAIN = pd.DataFrame({
    "age": [20, 30, 40, 50, 60, 0, 35, 45],
    "plan": ["basic", "pro", "basic", "pro", "basic", "team", "pro", "<b>vip</b>"],
    "city": [f"city {i}" for i in range(8)],
    "day": pd.to_datetime(["2026-01-01"] * 4 + ["2026-02-01"] * 4),
})
_TEST = pd.DataFrame({
    "age": [25, 35, 45, 55, 65, 75, 85, 95, 105, 115],
    "plan": ["pro"] * 6 + ["trial"] * 4,
    "city": [f"city {i % 30}" for i in range(10)],
    "day": pd.to_datetime(["2026-03-01"] * 10),
})


def _report(**kwargs: t.Any) -> bf.Briefing:
    return bf.Briefing(bf.lab.DataCompare({"train": _TRAIN, "test": _TEST}, **kwargs))


def _names(page: Page) -> list[str]:
    names: list[str] = page.locator(".bf-cmp__row:not([hidden])").evaluate_all(
        "rows => rows.map(r => r.getAttribute('data-name'))")
    return names


def _row(page: Page, name: str) -> Locator:
    return page.locator(f'.bf-cmp__row[data-name="{name}"]')


def _numbers(svg: Locator) -> list[float]:
    """Every number in the chart's markup: its geometry, to compare two drawings."""
    markup: str = svg.evaluate("s => s.innerHTML")
    return [float(n) for n in re.findall(r'(?<=["\s,LM])-?\d+(?:\.\d+)?', markup)]


def test_the_controls_show_once_the_script_runs(viewer: Viewer) -> None:
    page = viewer.open(_report())
    controls = page.locator(".bf-cmp__controls")
    expect(controls).to_be_visible()
    expect(controls.locator(".bf-cmp__sort")).to_have_value("name")
    assert _names(page) == ["age", "city", "day", "plan"]


def test_the_sort_reorders_the_rows(viewer: Viewer) -> None:
    page = viewer.open(_report())
    page.locator(".bf-cmp__sort").select_option("distance")
    distances = [float(_row(page, n).get_attribute("data-distance") or "nan") for n in _names(page)]
    assert distances == sorted(distances, reverse=True)
    page.locator(".bf-cmp__sort").select_option("name")
    assert _names(page) == ["age", "city", "day", "plan"]


def test_the_search_and_the_type_boxes_filter_the_rows(viewer: Viewer) -> None:
    page = viewer.open(_report())
    page.locator(".bf-cmp__search").fill("A")  # case doesn't matter
    assert _names(page) == ["age", "day", "plan"]
    expect(page.locator(".bf-cmp__shown")).to_have_text("3 of 4 columns")
    page.locator(".bf-cmp__search").fill("")
    page.get_by_label("categories").uncheck()
    assert _names(page) == ["age", "day"]
    page.get_by_label("categories").check()
    expect(page.locator(".bf-cmp__shown")).to_have_text("")


def test_counts_redraw_the_charts_and_percentages_bring_back_pythons(viewer: Viewer) -> None:
    page = viewer.open(_report())
    svg = _row(page, "age").locator("svg")
    drawn_by_python = _numbers(svg)
    page.get_by_role("button", name="counts").click()
    expect(page.get_by_role("button", name="counts")).to_have_attribute("aria-pressed", "true")
    # train has 8 ages, test 10: as counts, test's tallest bin is higher than as a share.
    assert _numbers(svg) != drawn_by_python
    page.get_by_role("button", name="%").click()
    again = _numbers(svg)
    assert len(again) == len(drawn_by_python)
    assert all(abs(a - b) <= 0.11 for a, b in zip(again, drawn_by_python, strict=True))


def test_the_log_scale_redraws_bars_and_curves(viewer: Viewer) -> None:
    page = viewer.open(_report())
    bars, curve = _row(page, "plan").locator("svg"), _row(page, "city").locator("svg")
    before_bars, before_curve = _numbers(bars), _numbers(curve)
    page.get_by_label("log scale").check()
    assert _numbers(bars) != before_bars
    assert _numbers(curve) != before_curve
    assert bars.locator("rect").count() == 2 * 5  # basic, pro, team, <b>vip</b>, trial: both datasets


def test_deciles_mark_each_dataset_on_number_charts_only(viewer: Viewer) -> None:
    page = viewer.open(_report())
    page.get_by_label("deciles").check()
    groups = _row(page, "age").locator(".bf-cmp__deciles")
    expect(groups).to_have_count(2)
    expect(groups.first.locator("line")).to_have_count(9)
    expect(_row(page, "day").locator(".bf-cmp__deciles")).to_have_count(0)
    page.get_by_label("deciles").uncheck()
    expect(groups).to_have_count(0)


def test_redrawn_labels_stay_text(viewer: Viewer) -> None:
    page = viewer.open(_report())
    page.get_by_role("button", name="counts").click()
    labels = _row(page, "plan").locator("text").all_text_contents()
    assert "<b>vip</b>" in labels
    expect(_row(page, "plan").locator("svg b")).to_have_count(0)


def test_the_controls_never_print(viewer: Viewer) -> None:
    page = viewer.open(_report())
    page.emulate_media(media="print")
    expect(page.locator(".bf-cmp__controls")).to_be_hidden()
    expect(page.locator(".bf-cmp__row").first).to_be_visible()


def test_two_comparisons_on_a_page_work_apart(viewer: Viewer) -> None:
    page = viewer.open(bf.Briefing(
        bf.lab.DataCompare({"train": _TRAIN, "test": _TEST}),
        bf.lab.DataCompare({"a": _TEST, "b": _TRAIN}),
    ))
    first, second = page.locator(".bf-compare").nth(0), page.locator(".bf-compare").nth(1)
    first.locator(".bf-cmp__search").fill("age")
    expect(first.locator(".bf-cmp__row:not([hidden])")).to_have_count(1)
    expect(second.locator(".bf-cmp__row:not([hidden])")).to_have_count(4)
