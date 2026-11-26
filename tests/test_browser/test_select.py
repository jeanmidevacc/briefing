"""Linked selection as a reader uses it: a bar of a profile or a comparison highlights rows in a DataDive (#21)."""
from __future__ import annotations

import math
import typing as t

import pandas as pd
from playwright.sync_api import Locator, Page, expect

import briefing as bf
from tests.test_browser.conftest import Viewer

# Values on the bins' edges on purpose: 0, 5, 10… with 20 bins from 0 to 95 put many on an edge.
_DF = pd.DataFrame({
    "score": [float(i % 20 * 5) for i in range(120)] + [math.inf, None],
    "team": (["red", "blue", "green"] * 40) + ["red", "blue"],
    "when": pd.to_datetime("2026-01-01") + pd.to_timedelta([i % 30 for i in range(122)], unit="D"),
})


def _profile_report(**kwargs: t.Any) -> bf.Briefing:
    return bf.Briefing(bf.lab.DataProfile(_DF, selects="dive", **kwargs), bf.lab.DataDive(_DF, x="score", name="dive"))


def _dive(page: Page) -> Locator:
    return page.locator(".bf-datadive")


#: How many rows match, drawn or not (matches() counts the dots drawn: a row without an x has none).
_MATCHED_JS = ("d => { let n = 0; for (let i = 0; i < d.briefingDive.total; i++) n += d.briefingDive.matched(i); "
               "return n; }")


def _matches(page: Page) -> int:
    count: int = _dive(page).evaluate(_MATCHED_JS)
    return count


def _selections(page: Page) -> list[dict[str, t.Any]]:
    found: list[dict[str, t.Any]] = _dive(page).evaluate("d => d.briefingDive.selections()")
    return found


def _bar(page: Page, column: str, pick: str, block: str = ".bf-profile") -> Locator:
    return page.locator(f'{block} [data-bf-column="{column}"] .bf-sel__hit[data-bf-pick="{pick}"]')


def _python_bins(values: pd.Series, bins: int = 20) -> list[int]:
    """How DataProfile counted *values* in each bar (its _histogram_svg), for the expected matches."""
    finite = [float(v) for v in values.dropna() if math.isfinite(v)]
    low, high = min(finite), max(finite)
    counts = [0] * bins
    for v in finite:
        counts[min(int((v - low) / (high - low) * bins), bins - 1)] += 1
    return counts


def test_each_bar_highlights_exactly_the_rows_python_counted_in_it(viewer: Viewer) -> None:
    page = viewer.open(_profile_report())
    expected = _python_bins(_DF["score"])
    for i in range(20):
        _bar(page, "score", str(i)).click()
        if expected[i]:
            assert _matches(page) == expected[i], f"bar {i}"
        _bar(page, "score", str(i)).click()  # again: cleared
    assert _selections(page) == []


def test_a_category_bar_selects_its_value_and_says_so_on_a_chip(viewer: Viewer) -> None:
    page = viewer.open(_profile_report())
    _bar(page, "team", "blue").click()
    assert _matches(page) == 41
    chip = _dive(page).locator(".bf-dd__chip--select")
    expect(chip).to_have_text("team blue · from profile×")
    expect(_bar(page, "team", "blue")).to_have_attribute("aria-pressed", "true")


def test_shift_adds_a_bar_of_the_same_column_and_another_column_replaces(viewer: Viewer) -> None:
    page = viewer.open(_profile_report())
    _bar(page, "team", "blue").click()
    _bar(page, "team", "red").click(modifiers=["Shift"])
    assert _matches(page) == 82
    assert _selections(page)[0]["labels"] == ["red", "blue"] or set(_selections(page)[0]["labels"]) == {"red", "blue"}
    _bar(page, "score", "0").click(modifiers=["Shift"])  # another column: starts again
    assert [s["column"] for s in _selections(page)] == ["score"]
    expect(_bar(page, "team", "blue")).to_have_attribute("aria-pressed", "false")


def test_the_chips_cross_clears_the_selection_and_the_bar(viewer: Viewer) -> None:
    page = viewer.open(_profile_report())
    _bar(page, "team", "green").click()
    _dive(page).get_by_role("button", name="Clear the selection from profile").click()
    assert _selections(page) == [] and _matches(page) == 122
    expect(_bar(page, "team", "green")).to_have_attribute("aria-pressed", "false")


def test_escape_clears(viewer: Viewer) -> None:
    page = viewer.open(_profile_report())
    _bar(page, "team", "green").click()
    page.keyboard.press("Escape")
    assert _selections(page) == []
    expect(_dive(page).locator(".bf-dd__chip--select")).to_have_count(0)


def test_bars_work_by_keyboard(viewer: Viewer) -> None:
    page = viewer.open(_profile_report())
    _bar(page, "team", "red").focus()
    page.keyboard.press("Enter")
    assert [s["labels"] for s in _selections(page)] == [["red"]]


def test_two_senders_add_two_chips_and_filter_mode_hides_the_rest(viewer: Viewer) -> None:
    page = viewer.open(bf.Briefing(
        bf.lab.DataProfile(_DF, selects="dive", name="first"),
        bf.lab.DataProfile(_DF, selects="dive", name="second"),
        bf.lab.DataDive(_DF, x="score", name="dive"),
    ))
    page.locator('[data-bf-from="first"] [data-bf-column="team"] .bf-sel__hit[data-bf-pick="red"]').click()
    page.locator('[data-bf-from="second"] [data-bf-column="score"] .bf-sel__hit[data-bf-pick="0"]').click()
    expect(_dive(page).locator(".bf-dd__chip--select")).to_have_count(2)
    red_zero = int(((_DF["team"] == "red") & (_DF["score"] == 0)).sum())
    assert _matches(page) == red_zero
    _dive(page).get_by_role("button", name="Filter").click()
    shown: int = _dive(page).evaluate("d => d.briefingDive.shown()")
    assert shown == red_zero  # every red row with a score of 0 has an x


def test_a_comparisons_bars_select_numbers_and_dates(viewer: Viewer) -> None:
    other = _DF.assign(score=_DF["score"] + 2)
    page = viewer.open(bf.Briefing(
        bf.lab.DataCompare({"a": _DF, "b": other}, selects="dive"),
        bf.lab.DataDive(_DF, x="score", name="dive"),
    ))
    _bar(page, "when", "0", ".bf-compare").click()
    first_days = int((_DF["when"] < pd.Timestamp("2026-01-01") + pd.Timedelta(days=29) / 20).sum())
    assert _matches(page) == first_days
    _bar(page, "score", "19", ".bf-compare").click()  # the last bin is closed: it holds the maximum
    assert _matches(page) == int(_DF["score"].between(97 - 97 / 20, 97).sum())  # inf is in no bar
    page.get_by_role("button", name="counts").click()  # a redraw keeps the bars clickable
    _bar(page, "team", "red", ".bf-compare").click()
    assert _matches(page) == 41


def test_a_column_the_dive_lacks_is_not_clickable_and_says_why(viewer: Viewer) -> None:
    page = viewer.open(bf.Briefing(
        bf.lab.DataProfile(_DF, selects="dive"),
        bf.lab.DataDive(_DF.drop(columns="team"), x="score", name="dive"),
    ))
    chart = page.locator(".bf-profile__chart[data-bf-unselectable]")
    expect(chart).to_have_count(1)
    expect(chart).to_have_attribute("title", "The DataDive 'dive' has no column 'team'.")
    expect(chart.locator(".bf-sel__hit")).to_have_count(0)


def test_a_selection_stays_in_its_own_embed(viewer: Viewer) -> None:
    def fragment(embed_id: str) -> str:
        report = bf.Briefing(bf.lab.DataProfile(_DF, selects="dive"), bf.lab.DataDive(_DF, x="score", name="dive"))
        return bf.stringify(report, full_html=False, embed_id=embed_id, include_assets=False)

    blocks = [bf.lab.DataProfile(_DF, selects="dive"), bf.lab.DataDive(_DF, name="dive")]
    html = (f"<!doctype html><html><head>{bf.embed_assets(blocks)}</head>"
            f"<body>{fragment('one')}{fragment('two')}</body></html>")
    page = viewer.open(html)
    page.locator("#one .bf-sel__hit[data-bf-pick='red']").click()
    one: int = page.locator("#one .bf-datadive").evaluate(_MATCHED_JS)
    two: int = page.locator("#two .bf-datadive").evaluate(_MATCHED_JS)
    assert (one, two) == (41, 122)
