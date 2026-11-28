"""A DataTable as the receiver of a linked selection (#238), and the range and all tests."""
from __future__ import annotations

import math
import typing as t
from pathlib import Path

import pandas as pd
import pytest
from playwright.sync_api import Locator, Page, expect

import briefing as bf
from tests.test_browser.conftest import Viewer

_DF = pd.DataFrame({
    "score": [float(i % 20 * 5) for i in range(120)] + [math.inf, None],
    "team": (["red", "blue", "green"] * 40) + ["red", "blue"],
    "when": pd.to_datetime("2026-01-01") + pd.to_timedelta([i % 30 for i in range(122)], unit="D"),
})
_DAY = 86_400_000
_RED = int((_DF["team"] == "red").sum())  # 41
#: How many rows a DataDive highlights.
_MATCHED_JS = ("d => { let n = 0; for (let i = 0; i < d.briefingDive.total; i++) n += d.briefingDive.matched(i); "
               "return n; }")


def _table(page: Page, name: str = "rows") -> Locator:
    return page.locator(f'.bf-datatable[id="{name}"]')


def _rows(page: Page, name: str = "rows") -> int:
    """How many rows the table keeps, from its count ("41 rows")."""
    text = _table(page, name).locator(".bf-dt__count").inner_text()
    return int(text.split()[0].replace(",", ""))


def _bar(page: Page, column: str, pick: str, block: str = ".bf-profile") -> Locator:
    return page.locator(f'{block} [data-bf-column="{column}"] .bf-sel__hit[data-bf-pick="{pick}"]')


def _send(page: Page, tests: list[dict[str, t.Any]], targets: tuple[str, ...] = ("rows",)) -> None:
    """A selection as a sender would send it: one test per pick (lab/_select.py lists the kinds)."""
    page.evaluate(
        """([tests, targets]) => document.dispatchEvent(new CustomEvent('bf:select', {detail: {
            targets, source: 'test', from: 'test', column: 'x', any: tests, picks: tests.map((_, i) => String(i)),
            labels: tests.map((_, i) => 'pick ' + i)}}))""",
        [tests, list(targets)],
    )


def _profile_and_table(**table: t.Any) -> bf.Briefing:
    return bf.Briefing(bf.lab.DataProfile(_DF, selects="rows"), bf.DataTable(_DF, name="rows", **table))


def test_a_profile_bar_filters_a_table_and_its_chip_clears_it(viewer: Viewer) -> None:
    page = viewer.open(_profile_and_table())
    assert _rows(page) == 122
    _bar(page, "team", "blue").click()
    assert _rows(page) == 41
    chip = _table(page).locator(".bf-sel__chip")
    expect(chip).to_have_text("team blue · from profile×")
    expect(_table(page).locator("tbody tr").first).to_contain_text("blue")
    chip.get_by_role("button", name="Clear the selection from profile").click()
    assert _rows(page) == 122
    expect(chip).to_have_count(0)
    expect(_bar(page, "team", "blue")).to_have_attribute("aria-pressed", "false")


def test_search_and_sort_work_within_the_selection(viewer: Viewer) -> None:
    page = viewer.open(_profile_and_table())
    _bar(page, "team", "red").click()
    _table(page).locator(".bf-dt__search").fill("2026-01-01")
    assert _rows(page) == int(((_DF["team"] == "red") & (_DF["when"] == "2026-01-01")).sum())
    _table(page).locator(".bf-dt__search").fill("")
    assert _rows(page) == _RED


def test_the_csv_button_downloads_only_the_selection(viewer: Viewer) -> None:
    page = viewer.open(_profile_and_table(download=True))
    _bar(page, "team", "green").click()
    with page.expect_download() as caught:
        _table(page).locator(".bf-dt__csv").click()
    lines = Path(caught.value.path()).read_bytes().decode("utf-8-sig").strip().splitlines()
    assert len(lines) == 1 + 40 and all(",green," in line for line in lines[1:])


def test_a_histogram_bar_finds_the_same_rows_in_a_table_and_a_dive(viewer: Viewer) -> None:
    page = viewer.open(bf.Briefing(
        bf.lab.DataProfile(_DF, selects=["rows", "dive"]),
        bf.DataTable(_DF, name="rows"),
        bf.lab.DataDive(_DF, x="score", name="dive"),
    ))
    for pick in ("0", "7", "19"):
        _bar(page, "score", pick).click()
        dive: int = page.locator(".bf-datadive").evaluate(_MATCHED_JS)
        assert _rows(page) == dive, pick


def test_a_big_tables_packed_rows_are_selected(viewer: Viewer) -> None:
    big = pd.DataFrame({"team": [("red", "blue", "green")[i % 3] for i in range(3000)], "n": range(3000)})
    page = viewer.open(bf.Briefing(bf.lab.DataProfile(big, selects="rows"), bf.DataTable(big, name="rows")))
    assert _rows(page) == 3000
    _bar(page, "team", "green").click()
    assert _rows(page) == 1000
    expect(_table(page).locator("tbody tr").first).to_contain_text("green")


def test_a_range_keeps_its_rows_ends_as_stated(viewer: Viewer) -> None:
    page = viewer.open(_profile_and_table())
    _send(page, [{"kind": "range", "column": "score", "min": 10, "max": 20}])
    assert _rows(page) == int(_DF["score"].between(10, 20, inclusive="left").sum())
    _send(page, [{"kind": "range", "column": "score", "min": 10, "max": 20, "closed": "both"}])
    assert _rows(page) == int(_DF["score"].between(10, 20).sum())  # inf and missing are in no range
    start = int(pd.Timestamp("2026-01-03").value // 1_000_000)
    _send(page, [{"kind": "range", "column": "when", "min": start, "max": start + _DAY}])
    assert _rows(page) == int((_DF["when"] == "2026-01-03").sum())


def test_all_needs_every_test_and_any_pick_is_enough(viewer: Viewer) -> None:
    page = viewer.open(_profile_and_table())
    red_low = {"kind": "all", "tests": [{"kind": "value", "column": "team", "value": "red"},
                                        {"kind": "range", "column": "score", "min": 0, "max": 25}]}
    _send(page, [red_low])
    expected = (_DF["team"] == "red") & _DF["score"].between(0, 25, inclusive="left")
    assert _rows(page) == int(expected.sum())
    _send(page, [red_low, {"kind": "value", "column": "team", "value": "blue"}])
    assert _rows(page) == int((expected | (_DF["team"] == "blue")).sum())


@pytest.mark.parametrize("tests", [
    [],  # an empty selection clears
    [{"kind": "value", "column": "absent", "value": "x"}],  # a column the table lacks: no filter
    [{"kind": "range", "column": "team", "min": 0, "max": 1}],  # categories hold no range
])
def test_a_selection_that_does_not_apply_keeps_every_row(viewer: Viewer, tests: list[dict[str, t.Any]]) -> None:
    page = viewer.open(_profile_and_table())
    _send(page, [{"kind": "value", "column": "team", "value": "red"}])
    assert _rows(page) == _RED
    _send(page, tests)
    assert _rows(page) == 122
    expect(_table(page).locator(".bf-sel__chip")).to_have_count(0)


def test_a_dive_keeps_the_same_rows_for_range_and_all(viewer: Viewer) -> None:
    page = viewer.open(bf.Briefing(bf.lab.DataProfile(_DF, selects="dive"),
                                   bf.lab.DataDive(_DF, x="score", name="dive")))
    blue_high = [{"kind": "value", "column": "team", "value": "blue"},
                 {"kind": "range", "column": "score", "min": 50, "max": 95, "closed": "both"}]
    _send(page, [{"kind": "all", "tests": blue_high}], targets=("dive",))
    matched: int = page.locator(".bf-datadive").evaluate(_MATCHED_JS)
    assert matched == int(((_DF["team"] == "blue") & _DF["score"].between(50, 95)).sum())


def test_a_selection_stays_in_its_own_embed(viewer: Viewer) -> None:
    def fragment(embed_id: str) -> str:
        return bf.stringify(_profile_and_table(), full_html=False, embed_id=embed_id, include_assets=False)

    blocks = [bf.lab.DataProfile(_DF, selects="rows"), bf.DataTable(_DF, name="rows")]
    page = viewer.open(f"<!doctype html><html><head>{bf.embed_assets(blocks)}</head>"
                       f"<body>{fragment('one')}{fragment('two')}</body></html>")
    page.locator("#one .bf-sel__hit[data-bf-pick='red']").click()
    counts = [page.locator(f"#{root} .bf-dt__count").inner_text() for root in ("one", "two")]
    assert counts == [f"{_RED} rows", "122 rows"]
