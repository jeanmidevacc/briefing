"""Group breakpoints and min_width (#27): how many cells sit on a row at each width."""
from __future__ import annotations

import pytest
from playwright.sync_api import Page

import briefing as bf
from tests.test_browser.conftest import Viewer


def _per_row(page: Page) -> int:
    """How many cells of the first Group share its first row."""
    tops: list[float] = page.locator(".bf-group").first.evaluate(
        "g => Array.from(g.children).map(c => Math.round(c.getBoundingClientRect().top))")
    return tops.count(tops[0])


def _cells(n: int) -> list[bf.Block]:
    return [bf.BigNumber(f"KPI {i}", i) for i in range(n)]


@pytest.mark.parametrize(("width", "expected"), [(1280, 4), (800, 2), (500, 1)])
def test_four_columns_on_desktop_tablet_and_phone(viewer: Viewer, width: int, expected: int) -> None:
    page = viewer.open(bf.Briefing(bf.Group(*_cells(4), columns=4)))
    page.set_viewport_size({"width": width, "height": 800})
    assert _per_row(page) == expected


def test_two_columns_stay_two_on_tablets(viewer: Viewer) -> None:
    page = viewer.open(bf.Briefing(bf.Group(*_cells(2), columns=2)))
    page.set_viewport_size({"width": 800, "height": 800})
    assert _per_row(page) == 2


def test_print_keeps_every_column(viewer: Viewer) -> None:
    page = viewer.open(bf.Briefing(bf.Group(*_cells(4), columns=4)))
    page.set_viewport_size({"width": 800, "height": 800})
    page.emulate_media(media="print")
    assert _per_row(page) == 4


@pytest.mark.parametrize(("width", "columns", "expected"), [
    (1280, 1, 4),   # 16rem cells in a 1200px report: four fit
    (1280, 3, 3),   # ... but columns=3 caps them
    (800, 1, 2),
    (500, 1, 1),
])
def test_min_width_fits_as_many_as_it_can(viewer: Viewer, width: int, columns: int, expected: int) -> None:
    page = viewer.open(bf.Briefing(bf.Group(*_cells(6), columns=columns, min_width="16rem")))
    page.set_viewport_size({"width": width, "height": 900})
    assert _per_row(page) == expected
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")


def test_min_width_wider_than_the_report_is_one_column(viewer: Viewer) -> None:
    page = viewer.open(bf.Briefing(bf.Group(*_cells(3), min_width=2000)))
    page.set_viewport_size({"width": 1000, "height": 900})
    assert _per_row(page) == 1 and page.evaluate("document.documentElement.scrollWidth <= innerWidth")
