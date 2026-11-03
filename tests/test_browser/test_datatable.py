"""DataTable sorting, search and paging, as a reader sees them (#1, #2)."""
from __future__ import annotations

import pandas as pd
from playwright.sync_api import Page

import briefing as bf
from tests.test_browser.conftest import Viewer

#: 1..60 in a scrambled order (37 is coprime with 60, so this is a permutation).
SCRAMBLED = [(i * 37) % 60 + 1 for i in range(60)]


def _table(values: list[int] | None = None) -> bf.Briefing:
    values = SCRAMBLED if values is None else values
    return bf.Briefing(bf.DataTable(pd.DataFrame({"n": values, "label": [f"row {v}" for v in values]})))


def visible_column(page: Page, col: int = 0) -> list[str]:
    """Text of column *col* in the rows a reader can see, top to bottom."""
    rows = page.locator(".bf-dt__table tbody tr:not([hidden])")
    return [str(text).strip() for text in rows.evaluate_all(f"rs => rs.map(r => r.cells[{col}].textContent)")]


def sort_by(page: Page, col: int) -> None:
    page.locator(f'.bf-dt__th[data-col="{col}"]').click()


def _ints(cells: list[str]) -> list[int]:
    return [int(c) for c in cells]


# ── behaviour that works in 0.1.0 ─────────────────────────────────────────────


def test_first_page_shows_25_rows(viewer: Viewer) -> None:
    page = viewer.open(_table())
    assert _ints(visible_column(page)) == SCRAMBLED[:25]
    assert page.locator(".bf-dt__page-info").inner_text() == "1–25 of 60"
    assert page.locator('.bf-dt__page-btn[data-dir="-1"]').is_disabled()


def test_next_page_shows_the_next_rows(viewer: Viewer) -> None:
    page = viewer.open(_table())
    page.locator('.bf-dt__page-btn[data-dir="1"]').click()
    assert _ints(visible_column(page)) == SCRAMBLED[25:50]
    assert page.locator(".bf-dt__page-info").inner_text() == "26–50 of 60"


def test_search_filters_rows(viewer: Viewer) -> None:
    page = viewer.open(_table())
    page.locator(".bf-dt__search").fill("row 1")
    expected = [v for v in SCRAMBLED if str(v).startswith("1")]  # row 1, row 10–19
    assert _ints(visible_column(page)) == expected
    assert page.locator(".bf-dt__count").inner_text() == f"{len(expected)} rows"


# ── #1: sorting must move rows ────────────────────────────────────────────────


def test_sort_orders_page_one_ascending_then_descending(viewer: Viewer) -> None:
    page = viewer.open(_table())
    sort_by(page, 0)
    assert _ints(visible_column(page)) == list(range(1, 26))
    sort_by(page, 0)
    assert _ints(visible_column(page)) == list(range(60, 35, -1))


def test_sort_reorders_a_single_page_table(viewer: Viewer) -> None:
    page = viewer.open(_table([3, 1, 2, 5, 4]))
    sort_by(page, 0)
    assert _ints(visible_column(page)) == [1, 2, 3, 4, 5]


def test_sort_combines_with_search_and_paging(viewer: Viewer) -> None:
    page = viewer.open(_table())
    page.locator(".bf-dt__search").fill("row")  # matches all 60 rows
    sort_by(page, 0)
    page.locator('.bf-dt__page-btn[data-dir="1"]').click()
    assert _ints(visible_column(page)) == list(range(26, 51))
    page.locator(".bf-dt__search").fill("row 5")  # row 5, row 50–59; sort is kept
    assert _ints(visible_column(page)) == [5, *range(50, 60)]
    page.locator(".bf-dt__search").fill("")  # clearing the search keeps the sort
    assert _ints(visible_column(page)) == list(range(1, 26))


# ── #2: sort by the real value ────────────────────────────────────────────────


def test_dates_sort_chronologically(viewer: Viewer) -> None:
    dates = pd.to_datetime(["2023-12-15", "2022-06-01", "2023-01-02", "2021-03-04"])
    page = viewer.open(bf.Briefing(bf.DataTable(pd.DataFrame({"when": dates}))))
    sort_by(page, 0)
    assert [c[:10] for c in visible_column(page)] == ["2021-03-04", "2022-06-01", "2023-01-02", "2023-12-15"]


def test_empty_cells_sort_last_both_ways(viewer: Viewer) -> None:
    page = viewer.open(bf.Briefing(bf.DataTable(pd.DataFrame({"x": [3.0, None, 1.0, 2.0]}))))
    sort_by(page, 0)
    assert visible_column(page) == ["1", "2", "3", ""]
    sort_by(page, 0)
    assert visible_column(page) == ["3", "2", "1", ""]


def test_numbers_sort_by_value_not_by_display(viewer: Viewer) -> None:
    # Both display as 1.23457e+06; only the data-sort key tells them apart.
    page = viewer.open(bf.Briefing(bf.DataTable(pd.DataFrame({"x": [1234568.25, 1234567.5, 99.0]}))))
    sort_by(page, 0)
    assert visible_column(page) == ["99", "1.23457e+06", "1.23457e+06"]
    assert page.locator(".bf-dt__table tbody tr:not([hidden]) td").evaluate_all(
        "tds => tds.map(td => td.dataset.sort)"
    ) == [None, "1234567.5", "1234568.25"]  # no key where it would equal the text


def test_numbers_shown_with_separators_sort_numerically(viewer: Viewer) -> None:
    page = viewer.open(bf.Briefing(bf.DataTable(pd.DataFrame({"amount": ["1,200", "950", "12,000", "", "-3"]}))))
    sort_by(page, 0)
    assert visible_column(page) == ["-3", "950", "1,200", "12,000", ""]
    sort_by(page, 0)
    assert visible_column(page) == ["12,000", "1,200", "950", "-3", ""]


def test_text_sorts_alphabetically(viewer: Viewer) -> None:
    page = viewer.open(bf.Briefing(bf.DataTable(pd.DataFrame({"s": ["pear", "apple", "fig"]}))))
    sort_by(page, 0)
    assert visible_column(page) == ["apple", "fig", "pear"]
