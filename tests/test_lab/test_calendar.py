"""lab.CalendarHeatmap, day view (#19)."""
from __future__ import annotations

import datetime as dt
import typing as t

import pandas as pd
import pytest
from bs4 import BeautifulSoup, Tag

import briefing as bf
from briefing.lab import CalendarHeatmap
from briefing.lab._render_calendar import GITHUB, _fmt, render_calendar
from tests.html_helpers import attr, classes, find_one

# The hour view is deprecated (#111) but still supported: its tests keep running without the warning.
pytestmark = pytest.mark.filterwarnings("ignore:CalendarHeatmap. the hour view:DeprecationWarning")


def _soup(block: CalendarHeatmap) -> BeautifulSoup:
    return BeautifulSoup(render_calendar(block), "html.parser")


def _cells(soup: BeautifulSoup) -> dict[str, Tag]:
    return {attr(c, "data-date"): c for c in soup.select("rect.bf-cal__day")}


# ── input checks ───────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("kwargs", "match"),
    [
        ({"date": "nope"}, "column 'nope'"),
        ({"value": "nope"}, "column 'nope'"),
        ({"agg": "mode"}, "agg"),
        ({"week_start": "friday"}, "week_start"),
        ({"colors": "viridis"}, "colors"),
        ({"colors": ["#000"]}, "colors"),
        ({"center": 0, "colors": ["#ff0000", "#00ff00"]}, "three"),
        ({"center": 0, "colors": ["red", "white", "blue"]}, "hex"),
        ({"group": "nope"}, "column 'nope'"),
    ],
)
def test_bad_arguments(df_pipeline_log: pd.DataFrame, kwargs: dict[str, object], match: str) -> None:
    args: dict[str, object] = {"date": "run_at", **kwargs}
    with pytest.raises(bf.BriefingError, match=match):
        CalendarHeatmap(df_pipeline_log, **args)  # type: ignore[arg-type]


def test_bad_expected_and_events(df_pipeline_log: pd.DataFrame) -> None:
    with pytest.raises(bf.BriefingError, match="expected"):
        CalendarHeatmap(df_pipeline_log, date="run_at", expected=pd.DataFrame({"x": [1]}))
    with pytest.raises(bf.BriefingError, match="events"):
        CalendarHeatmap(df_pipeline_log, date="run_at", events=pd.DataFrame({"when": ["2026-01-01"]}))


# ── day view ──────────────────────────────────────────────────────────────────


def test_one_cell_per_day_in_github_green(df_pipeline_log: pd.DataFrame) -> None:
    soup = _soup(CalendarHeatmap(df_pipeline_log, date="run_at"))
    cells = _cells(soup)
    first, last = dt.date(2025, 11, 17), dt.date(2026, 2, 15)
    assert len(cells) == (last - first).days + 1
    assert min(cells) == first.isoformat() and max(cells) == last.isoformat()
    fills = {attr(c, "fill") for c in cells.values() if "bf-cal__day--empty" not in classes(c)}
    assert fills <= set(GITHUB)  # counts of 1 or 2 runs, in GitHub's green levels


def test_colors_replace_the_scale(df_pipeline_log: pd.DataFrame) -> None:
    palette = ["#eeeeee", "#999999", "#333333"]
    soup = _soup(CalendarHeatmap(df_pipeline_log, date="run_at", value="rows", colors=palette))
    fills = {attr(c, "fill") for c in soup.select("rect.bf-cal__day:not(.bf-cal__day--empty)")}
    assert fills <= set(palette) and len(fills) > 1


def test_no_data_looks_different_from_zero(df_pipeline_log: pd.DataFrame) -> None:
    cells = _cells(_soup(CalendarHeatmap(df_pipeline_log, date="run_at", value="rows")))
    empty, zero = cells["2025-12-25"], cells["2025-12-03"]  # no run; a failed run (rows == 0)
    assert "bf-cal__day--empty" in classes(empty) and "bf-cal__day--zero" not in classes(empty)
    assert "bf-cal__day--zero" in classes(zero) and "bf-cal__day--empty" not in classes(zero)
    assert "no data" in find_one(empty, "title").get_text()
    assert "0" in find_one(zero, "title").get_text()


@pytest.mark.parametrize("form", ["number", "series", "frame"])
def test_days_below_expected_are_flagged(df_pipeline_log: pd.DataFrame, form: str) -> None:
    days = pd.date_range("2025-11-17", "2026-02-15", freq="D")
    expected: t.Any = {
        "number": 500,
        "series": pd.Series(500, index=days),
        "frame": pd.DataFrame({"run_at": days, "expected": 500}),
    }[form]
    cells = _cells(_soup(CalendarHeatmap(df_pipeline_log, date="run_at", value="rows", expected=expected)))
    below = {d for d, c in cells.items() if "bf-cal__day--below" in classes(c)}
    assert {"2025-12-03", "2026-01-03", "2026-02-03"} <= below  # days whose only run failed
    assert {"2025-12-25", "2026-01-01", "2026-01-17"} <= below  # no run at all
    assert "2025-12-04" not in below and "below target 500" in find_one(cells["2025-12-03"], "title").get_text()


def test_expected_frame_per_group(df_pipeline_log: pd.DataFrame) -> None:
    days = pd.date_range("2025-11-17", "2026-02-15", freq="D")
    targets = pd.concat([pd.DataFrame({"run_at": days, "team": "ingest", "expected": 900}),
                         pd.DataFrame({"run_at": days, "team": "export", "expected": 0})])
    soup = _soup(CalendarHeatmap(df_pipeline_log, date="run_at", value="rows", group="team", expected=targets))
    export, ingest = soup.select("svg.bf-cal__days")  # groups are sorted
    assert ingest.select("rect.bf-cal__day--below") and not export.select("rect.bf-cal__day--below")


def test_single_and_multi_day_events(df_pipeline_log: pd.DataFrame, df_events: pd.DataFrame) -> None:
    soup = _soup(CalendarHeatmap(df_pipeline_log, date="run_at", events=df_events))
    bands = soup.select(".bf-cal__event--span")
    markers = soup.select(".bf-cal__event--day")
    assert len(bands) == 2 and len(markers) == 1
    assert "Incident" in find_one(markers[0], "title").get_text()
    legend = find_one(soup, ".bf-cal__legend").get_text(" ")
    assert "Holiday freeze (2025-12-22 to 2026-01-02)" in legend and "Incident (2026-02-03)" in legend
    cells = _cells(soup)
    assert "bf-cal__day--event" in classes(cells["2025-12-30"]) and "bf-cal__day--event" in classes(cells["2026-02-03"])
    assert "bf-cal__day--event" not in classes(cells["2026-02-10"])


def test_events_as_single_dates(df_pipeline_log: pd.DataFrame) -> None:
    soup = _soup(CalendarHeatmap(df_pipeline_log, date="run_at", events=["2026-01-05", dt.date(2026, 1, 9)]))
    assert len(soup.select(".bf-cal__event--day")) == 2


def test_center_gives_a_diverging_scale(df_signed: pd.DataFrame) -> None:
    df = pd.concat([df_signed, pd.DataFrame({"day": [pd.Timestamp("2026-05-01")], "balance": [0.0]})])
    soup = _soup(CalendarHeatmap(df, date="day", value="balance", center=0,
                                 colors=["#ff0000", "#ffffff", "#0000ff"]))
    cells = _cells(soup)
    def rgb(cell: Tag) -> tuple[int, int, int]:
        h = attr(cell, "fill").lstrip("#")
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    values = df.set_index(df["day"].dt.date.astype(str))["balance"]
    assert attr(cells["2026-05-01"], "fill") == "#ffffff"  # zero sits at the midpoint
    for day, value in values.items():
        r, g, b = rgb(cells[str(day)])
        if value < 0:
            assert r >= b, day
        elif value > 0:
            assert b >= r, day


def test_year_boundary_is_one_continuous_grid(df_pipeline_log: pd.DataFrame) -> None:
    soup = _soup(CalendarHeatmap(df_pipeline_log, date="run_at"))
    assert len(soup.select("svg.bf-cal__days")) == 1
    years = [t.get_text() for t in soup.select(".bf-cal__year")]
    assert years == ["2025", "2026"]
    xs = sorted({float(attr(c, "x")) for c in soup.select("rect.bf-cal__day")})
    steps = {round(b - a, 3) for a, b in zip(xs, xs[1:], strict=False)}
    assert len(steps) == 1  # weeks follow each other with no gap at the new year
    assert [t.get_text() for t in soup.select(".bf-cal__month")][:4] == ["Nov", "Dec", "Jan", "Feb"]


def test_groups_stack_and_share_one_scale(df_pipeline_log: pd.DataFrame) -> None:
    soup = _soup(CalendarHeatmap(df_pipeline_log, date="run_at", group="team"))
    assert [g.get_text() for g in soup.select(".bf-cal__group")] == ["export", "ingest"]
    assert len(soup.select("svg.bf-cal__days")) == 2


@pytest.mark.parametrize(("week_start", "weekday"), [("monday", 0), ("sunday", 6)])
def test_week_start(df_pipeline_log: pd.DataFrame, week_start: str, weekday: int) -> None:
    soup = _soup(CalendarHeatmap(df_pipeline_log, date="run_at", week_start=week_start))
    top_row = [c for c in soup.select("rect.bf-cal__day") if float(attr(c, "y")) == min(
        float(attr(x, "y")) for x in soup.select("rect.bf-cal__day"))]
    assert {dt.date.fromisoformat(attr(c, "data-date")).weekday() for c in top_row} == {weekday}


def test_tooltips_show_date_and_value(df_pipeline_log: pd.DataFrame) -> None:
    cells = _cells(_soup(CalendarHeatmap(df_pipeline_log, date="run_at", value="rows", agg="sum")))
    title = find_one(cells["2025-12-07"], "title").get_text()
    assert title.startswith("Sun 2025-12-07 · ") and "rows" in title  # weekday first, for the tooltip (#109)


def test_labels_are_escaped(df_pipeline_log: pd.DataFrame) -> None:
    df = df_pipeline_log.assign(team="<script>x()</script>")
    events = pd.DataFrame({"start": ["2026-01-05"], "label": ["<img src=x onerror=y()>"]})
    soup = _soup(CalendarHeatmap(df, date="run_at", group="team", events=events))
    assert soup.find("script") is None and soup.find("img") is None


def test_in_a_report(df_pipeline_log: pd.DataFrame) -> None:
    html = bf.stringify(bf.Briefing(CalendarHeatmap(df_pipeline_log, date="run_at")))
    assert "bf-cal__days" in html


def test_event_labels_only_go_inside_bands_that_fit_them(df_pipeline_log: pd.DataFrame) -> None:
    events = pd.DataFrame({"start": ["2025-12-01", "2026-01-26"], "end": ["2026-02-15", "2026-01-28"],
                           "label": ["Long migration window", "A label far too long for three days"]})
    soup = _soup(CalendarHeatmap(df_pipeline_log, date="run_at", events=events))
    wide, narrow = soup.select(".bf-cal__event--span")
    assert wide.find("text") is not None and narrow.find("text") is None


# ── time zones and the hour view (part 3b) ────────────────────────────────────


def _day_values(soup: BeautifulSoup) -> dict[str, str]:
    """Day → tooltip, for days with data."""
    return {attr(c, "data-date"): find_one(c, "title").get_text()
            for c in soup.select("svg.bf-cal__days rect.bf-cal__day:not(.bf-cal__day--empty)")}


def test_tz_converts_aware_timestamps(df_timestamps_near_midnight: pd.DataFrame) -> None:
    montreal = _day_values(_soup(CalendarHeatmap(df_timestamps_near_midnight, date="aware", tz="America/Montreal")))
    assert set(montreal) == {"2026-01-09", "2026-01-10", "2026-01-11"}  # 03:30 UTC is the previous evening
    utc = _day_values(_soup(CalendarHeatmap(df_timestamps_near_midnight, date="aware")))
    assert set(utc) == {"2026-01-10", "2026-01-12"}  # without tz, aware stamps keep their own (UTC) date


@pytest.mark.parametrize("column", ["naive", "plain"])
def test_tz_leaves_naive_timestamps_and_dates_alone(df_timestamps_near_midnight: pd.DataFrame, column: str) -> None:
    days = _day_values(_soup(CalendarHeatmap(df_timestamps_near_midnight, date=column, tz="America/Montreal")))
    assert set(days) == {"2026-01-10", "2026-01-12"}
    assert "2 rows" in days["2026-01-10"]  # midnight never moves to the previous day


def test_unknown_time_zone(df_timestamps_near_midnight: pd.DataFrame) -> None:
    with pytest.raises(bf.BriefingError, match="time zone"):
        CalendarHeatmap(df_timestamps_near_midnight, date="aware", tz="Mars/Olympus")


def test_hour_view_is_a_7_by_24_grid(df_pipeline_log: pd.DataFrame) -> None:
    soup = _soup(CalendarHeatmap(df_pipeline_log, date="run_at", views=("hours",)))
    cells = soup.select("svg.bf-cal__hours rect.bf-cal__hour")
    assert len(cells) == 7 * 24 and not soup.select("svg.bf-cal__days")
    runs = {attr(c, "data-hour"): find_one(c, "title").get_text() for c in cells
            if "bf-cal__hour--empty" not in classes(c)}
    assert set(runs) <= {f"{d}-{h}" for d in range(7) for h in (6, 14)}  # runs start at 06:00 or 14:00
    assert any(t.startswith("Mon 06:00") for t in runs.values())


def test_hour_view_follows_tz(df_timestamps_near_midnight: pd.DataFrame) -> None:
    soup = _soup(CalendarHeatmap(df_timestamps_near_midnight, date="aware", tz="America/Montreal", views=("hours",)))
    hours = {attr(c, "data-hour") for c in soup.select("rect.bf-cal__hour:not(.bf-cal__hour--empty)")}
    assert hours == {"4-22", "5-7", "6-23"}  # Fri 22:30, Sat 07:00, Sun 23:59 in Montréal (Mon = 0)


def test_both_views_are_tabs(df_pipeline_log: pd.DataFrame) -> None:
    soup = _soup(CalendarHeatmap(df_pipeline_log, date="run_at", views=("days", "hours")))
    tabs = soup.select(".bf-calendar .bf-select__tab")
    assert [t.get_text() for t in tabs] == ["Days", "Hours"]
    panels = soup.select(".bf-calendar .bf-select__panel")
    assert panels[0].select("svg.bf-cal__days") and panels[1].select("svg.bf-cal__hours")


def test_hour_view_needs_times(df_timestamps_near_midnight: pd.DataFrame) -> None:
    with pytest.raises(bf.BriefingError, match="time of day"):
        CalendarHeatmap(df_timestamps_near_midnight, date="plain", views=("days", "hours"))


def test_bad_views(df_pipeline_log: pd.DataFrame) -> None:
    with pytest.raises(bf.BriefingError, match="views"):
        CalendarHeatmap(df_pipeline_log, date="run_at", views=("weeks",))


# ── on_click="rows" (part 3c) ─────────────────────────────────────────────────


def _rows(soup: BeautifulSoup) -> dict[str, t.Any]:
    import json

    data: dict[str, t.Any] = json.loads(find_one(soup, 'script.bf-cal__rows[type="application/json"]').get_text())
    return data


def test_rows_data_only_with_on_click(df_pipeline_log: pd.DataFrame) -> None:
    assert _soup(CalendarHeatmap(df_pipeline_log, date="run_at")).select("script.bf-cal__rows") == []
    with pytest.raises(bf.BriefingError, match="on_click"):
        CalendarHeatmap(df_pipeline_log, date="run_at", on_click="line")


def test_rows_behind_each_day_and_hour(df_pipeline_log: pd.DataFrame) -> None:
    soup = _soup(CalendarHeatmap(df_pipeline_log, date="run_at", views=("days", "hours"), on_click="rows"))
    data = _rows(soup)
    assert data["columns"] == ["run_at", "team", "rows"]
    day = data["cells"]["d|2025-12-07"]  # two runs that day
    assert day["total"] == 2 and len(day["rows"]) == 2
    assert day["rows"][0][1] == "ingest"
    assert data["cells"]["h|0-6"]["total"] > 0  # Mondays at 06:00
    cell = soup.select_one('rect[data-date="2025-12-07"]')
    assert cell is not None and attr(cell, "role") == "button" and attr(cell, "tabindex") == "0"


def test_rows_per_cell_are_capped(df_pipeline_log: pd.DataFrame) -> None:
    many = pd.DataFrame({"run_at": [pd.Timestamp("2026-01-05 09:00")] * 120, "n": range(120)})
    data = _rows(_soup(CalendarHeatmap(many, date="run_at", on_click="rows")))
    cell = data["cells"]["d|2026-01-05"]
    assert cell["total"] == 120 and len(cell["rows"]) == CalendarHeatmap.ROWS_PER_CELL == 50


def test_rows_are_keyed_by_group(df_pipeline_log: pd.DataFrame) -> None:
    soup = _soup(CalendarHeatmap(df_pipeline_log, date="run_at", group="team", on_click="rows"))
    data = _rows(soup)
    assert data["cells"]["d|2025-12-07|export"]["total"] == 1
    assert [attr(c, "data-group") for c in soup.select(".bf-cal__calendar")] == ["export", "ingest"]


def test_rows_json_cannot_close_its_script(df_pipeline_log: pd.DataFrame) -> None:
    df = pd.DataFrame({"run_at": [pd.Timestamp("2026-01-05")], "note": ["</script><img src=x onerror=y()>"]})
    soup = _soup(CalendarHeatmap(df, date="run_at", on_click="rows"))
    assert soup.find("img") is None and "<" not in find_one(soup, "script.bf-cal__rows").get_text()
    assert _rows(soup)["cells"]["d|2026-01-05"]["rows"][0][1] == "</script><img src=x onerror=y()>"


# ── exact values in tooltips and the legend (#109) ────────────────────────────


@pytest.mark.parametrize(("value", "shown"), [
    (3, "3"), (1234, "1,234"), (12345.67, "12,345.67"), (-12345.678, "-12,345.68"), (1234.5, "1,234.5"),
    (10_000_000.5, "10,000,000.5"), (0.12345, "0.1235"), (-0.5, "-0.5"), (0.00001234, "1.23e-05"),
])
def test_values_are_shown_exactly(value: float, shown: str) -> None:
    assert _fmt(value) == shown


def test_a_large_fractional_value_has_no_exponent_in_tooltip_or_legend() -> None:
    df = pd.DataFrame({"day": pd.to_datetime(["2026-01-05", "2026-01-06"]), "amount": [12345.67, 20000.25]})
    soup = _soup(CalendarHeatmap(df, date="day", value="amount", colors=["#eee", "#333"]))
    tip = find_one(find_one(soup, 'rect[data-date="2026-01-05"]'), "title").get_text()
    assert tip == "Mon 2026-01-05 · 12,345.67 amount"
    legend = find_one(soup, ".bf-cal__legend").get_text()
    assert "e+0" not in legend and "12,345.67" in legend
