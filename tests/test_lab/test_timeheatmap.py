"""lab.TimeHeatmap (#111): two time units crossed, counts and sums averaged per occurrence.

The browser side (tooltips, the rows panel, width fitting) is in tests/test_browser/test_timeheatmap.py.
"""
from __future__ import annotations

import json
import re
import typing as t

import pandas as pd
import pytest
from bs4 import Tag

import briefing as bf
from tests.html_helpers import attr, find_one, parse


def _runs() -> pd.DataFrame:
    """Two Mondays (5 and 12 Jan 2026) and one Tuesday: 3 + 1 runs on Mondays at 09:00, 2 on the Tuesday."""
    stamps = ["2026-01-05 09:10", "2026-01-05 09:20", "2026-01-05 09:30", "2026-01-12 09:05",
              "2026-01-06 14:00", "2026-01-06 14:30"]
    return pd.DataFrame({"run_at": pd.to_datetime(stamps), "rows": [10, 20, 30, 40, 5, 0],
                         "team": ["a", "a", "b", "a", "b", "b"]})


def _cells(block: bf.lab.TimeHeatmap) -> dict[str, Tag]:
    soup = parse(bf.stringify(block))
    return {attr(rect, "data-cell"): rect for rect in soup.select("rect.bf-cal__cell")}


def _tip(rect: Tag) -> str:
    title = rect.find("title")
    assert title is not None
    return title.get_text()


def test_counts_are_averaged_per_occurrence() -> None:
    cells = _cells(bf.lab.TimeHeatmap(_runs(), date="run_at", rows="weekday", columns="hour"))
    assert _tip(cells["0-9"]) == "Mon 09:00 · 2 rows on average · 4 over 2 hours"  # 4 runs over 2 Mondays at 9
    assert _tip(cells["1-14"]) == "Tue 14:00 · 2 rows on average · 2 over 1 hour"  # the range ends on Monday 12
    assert "no data" in _tip(cells["2-9"]) and "bf-cal__cell--empty" in attr(cells["2-9"], "class")


def test_sums_are_averaged_and_means_are_not() -> None:
    sums = _cells(bf.lab.TimeHeatmap(_runs(), date="run_at", rows="weekday", columns="hour", value="rows"))
    assert _tip(sums["0-9"]) == "Mon 09:00 · 50 rows on average · 100 over 2 hours"
    means = _cells(bf.lab.TimeHeatmap(_runs(), date="run_at", rows="weekday", columns="hour", value="rows",
                                      agg="mean"))
    assert _tip(means["0-9"]) == "Mon 09:00 · 25 mean rows"  # (10 + 20 + 30 + 40) / 4
    assert "bf-cal__cell--zero" not in attr(means["1-14"], "class")
    zero = _cells(bf.lab.TimeHeatmap(_runs().iloc[5:], date="run_at", rows="weekday", columns="hour", value="rows"))
    assert "bf-cal__cell--zero" in attr(zero["1-14"], "class")


def test_cells_that_cant_exist_are_left_blank() -> None:
    days = pd.DataFrame({"day": pd.date_range("2024-01-01", "2024-12-31", freq="D")})
    html = bf.stringify(bf.lab.TimeHeatmap(days, date="day", rows="day", columns="month"))
    cells = {attr(r, "data-cell") for r in parse(html).select("rect.bf-cal__cell")}
    assert "29-2" in cells and "30-2" not in cells and "31-4" not in cells and "31-12" in cells
    assert len(cells) == 31 * 12 - 2 - 4  # 30-31 February, the 31st of April, June, September and November
    assert "no such date" in find_one(parse(html), ".bf-cal__legend").get_text()
    hours = bf.stringify(bf.lab.TimeHeatmap(_runs(), date="run_at", rows="weekday", columns="hour"))
    assert "no such date" not in hours  # every hour of every weekday exists
    by_year = bf.stringify(bf.lab.TimeHeatmap(days, date="day", rows="month", columns="year"))
    assert "no such date" not in by_year  # every month of every year exists, so nothing is blank


def test_the_axes_follow_their_units() -> None:
    def labels(block: bf.lab.TimeHeatmap, cls: str) -> list[str]:
        return [x.get_text() for x in parse(bf.stringify(block)).select(f"svg.bf-cal__grid text.{cls}")]

    sunday = bf.lab.TimeHeatmap(_runs(), date="run_at", rows="weekday", columns="hour", week_start="sunday")
    assert labels(sunday, "bf-cal__weekday") == ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
    assert labels(sunday, "bf-cal__month")[:3] == ["00", "03", "06"]  # every third hour, so labels don't overlap
    years = pd.DataFrame({"day": pd.to_datetime(["2020-03-01", "2023-07-01"])})
    by_year = bf.lab.TimeHeatmap(years, date="day", rows="quarter", columns="year")
    assert labels(by_year, "bf-cal__weekday") == ["Q1", "Q2", "Q3", "Q4"]
    assert labels(by_year, "bf-cal__month") == ["2020", "2022"]  # every other one: four digits need two cells
    assert {key.split("-")[1] for key in _cells(by_year)} == {"2020", "2021", "2022", "2023"}  # every year between
    weeks = bf.lab.TimeHeatmap(years, date="day", rows="week", columns="year")
    assert labels(weeks, "bf-cal__weekday")[-1] == "W53"  # 2020 has an ISO week 53


def test_groups_stack_on_one_scale_and_the_rows_panel_knows_each_cell() -> None:
    html = bf.stringify(bf.lab.TimeHeatmap(_runs(), date="run_at", rows="weekday", columns="hour", group="team",
                                           on_click="rows"))
    soup = parse(html)
    assert [g.get_text() for g in soup.select(".bf-cal__group")] == ["a", "b"]
    assert [attr(c, "data-group") for c in soup.select(".bf-cal__calendar")] == ["a", "b"]
    rows = json.loads(find_one(soup, "script.bf-cal__rows").get_text())
    assert rows["cells"]["c|0-9|a"]["total"] == 3 and rows["cells"]["c|1-14|b"]["total"] == 2
    assert all(attr(r, "role") == "button" for r in soup.select("rect.bf-cal__cell"))


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"rows": "minute"}, r"rows must be one of hour, weekday, day, week, month, quarter, year, not 'minute'"),
        ({"columns": "weekday"}, r"rows and columns must be two different units, not both 'weekday'"),
        ({"date": "when"}, r"column 'when' \(passed as date=\) not found"),
        ({"value": "nope"}, r"column 'nope' \(passed as value=\) not found"),
        ({"agg": "total"}, r"agg must be one of"),
        ({"on_click": "line"}, r"on_click must be 'rows' or None"),
        ({"week_start": "friday"}, r"week_start must be 'monday' or 'sunday'"),
        ({"tz": "Mars/Base"}, r"TimeHeatmap: unknown time zone 'Mars/Base'"),
        ({"center": 0}, r"TimeHeatmap: center= needs colors= as three hex colours"),
    ],
)
def test_options_that_dont_fit_say_what_to_pass(kwargs: dict[str, t.Any], message: str) -> None:
    options = {"date": "run_at", "rows": "weekday", "columns": "month", **kwargs}
    with pytest.raises(bf.BriefingError, match=message):
        bf.lab.TimeHeatmap(_runs(), **options)


def test_an_hour_axis_needs_a_time_of_day() -> None:
    dates = pd.DataFrame({"day": pd.to_datetime(["2026-01-05", "2026-01-06"])})
    with pytest.raises(bf.BriefingError, match=r"an hour axis needs a time of day, but 'day' holds dates only"):
        bf.lab.TimeHeatmap(dates, date="day", rows="weekday", columns="hour")


def test_no_dates_is_a_placeholder() -> None:
    empty = pd.DataFrame({"day": pd.to_datetime(pd.Series([None, None]))})
    html = bf.stringify(bf.lab.TimeHeatmap(empty, date="day", rows="weekday", columns="month"))
    assert re.search(r"TimeHeatmap: no dates to display", html)
