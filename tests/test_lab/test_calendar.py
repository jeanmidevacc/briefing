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
    # Only the single-day event outlines its day: a span's days keep their data colours in view (#152).
    assert "bf-cal__day--event" in classes(cells["2026-02-03"])
    assert "bf-cal__day--event" not in classes(cells["2025-12-30"])
    assert "bf-cal__day--event" not in classes(cells["2026-02-10"])
    # A span's days still name it in their tooltip.
    assert "Holiday freeze" in find_one(cells["2025-12-30"], "title").get_text()


def test_event_colours(df_pipeline_log: pd.DataFrame, df_events: pd.DataFrame) -> None:
    events = df_events.assign(color=pd.Series(["#2dd4bf", None, "rgb(96, 165, 250)"]))  # freeze, migration, incident
    soup = _soup(CalendarHeatmap(df_pipeline_log, date="run_at", events=events))
    freeze, migration = soup.select(".bf-cal__event--span")
    (incident,) = soup.select(".bf-cal__event--day")
    assert attr(freeze, "style") == "--bf-event: #2dd4bf"
    assert migration.get("style") is None  # no colour: the theme's accent
    assert attr(incident, "style") == "--bf-event: rgb(96, 165, 250)"
    assert attr(_cells(soup)["2026-02-03"], "style") == "--bf-event: rgb(96, 165, 250)"  # its outline
    swatches = [s.get("style") for s in soup.select(".bf-cal__swatch--event-day, .bf-cal__swatch--event-span")]
    assert sorted(map(str, swatches)) == ["--bf-event: #2dd4bf", "--bf-event: rgb(96, 165, 250)", "None"]


@pytest.mark.parametrize("color", ["red; } body { display: none", "url(x)", "#12", "#12345", "var(--x)", 3])
def test_event_colour_must_be_a_plain_css_colour(df_pipeline_log: pd.DataFrame, color: t.Any) -> None:
    events = pd.DataFrame({"start": ["2026-01-05"], "color": [color]})
    with pytest.raises(bf.BriefingError, match="CSS colours"):
        CalendarHeatmap(df_pipeline_log, date="run_at", events=events)


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


# ── weekday labels (#113) ─────────────────────────────────────────────────────


@pytest.mark.parametrize("week_start", ["monday", "sunday"])
def test_every_weekday_is_named_on_its_own_row(week_start: str) -> None:
    df = pd.DataFrame({"d": pd.date_range("2026-01-05", "2026-01-18")})  # two full weeks from a Monday
    soup = _soup(CalendarHeatmap(df, date="d", week_start=week_start))
    row_of_day = {float(attr(r, "y")): pd.Timestamp(attr(r, "data-date")).strftime("%a")
                  for r in soup.select("rect.bf-cal__day")}
    labels = soup.select("svg.bf-cal__days text.bf-cal__weekday")
    assert [t.get_text() for t in labels] == ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    for label in labels:  # a label's baseline sits inside its row: y = row top + cell - 1
        row_top = float(attr(label, "y")) - 10
        assert row_of_day[row_top] == label.get_text()
    tops = sorted(float(attr(t, "y")) for t in labels)
    first = "Sun" if week_start == "sunday" else "Mon"
    assert next(t.get_text() for t in labels if float(attr(t, "y")) == tops[0]) == first


# ── start and end (#153) ──────────────────────────────────────────────────────


def _days(soup: BeautifulSoup) -> list[str]:
    return sorted(_cells(soup))


def test_start_and_end_fix_the_grid_whatever_the_data_covers(df_signed: pd.DataFrame) -> None:
    soup = _soup(CalendarHeatmap(df_signed, date="day", start="2026-02-15", end=dt.date(2026, 6, 30)))
    days = _days(soup)
    assert days[0] == "2026-02-15" and days[-1] == "2026-06-30"
    cells = _cells(soup)
    assert "bf-cal__day--empty" in classes(cells["2026-02-20"])  # before the data: no data
    assert "bf-cal__day--empty" in classes(cells["2026-06-01"])  # after it


def test_either_edge_alone(df_signed: pd.DataFrame) -> None:
    days = _days(_soup(CalendarHeatmap(df_signed, date="day", start="2026-02-01")))
    assert (days[0], days[-1]) == ("2026-02-01", "2026-04-29")  # to the last day of data
    assert _days(_soup(CalendarHeatmap(df_signed, date="day", end="2026-05-31")))[0] == "2026-03-01"


def test_rows_outside_the_span_are_left_out_with_a_warning(df_signed: pd.DataFrame) -> None:
    with pytest.warns(UserWarning, match=r"^CalendarHeatmap: 40 rows outside 2026-03-11 to 2026-03-30 left out\.$"):
        block = CalendarHeatmap(df_signed, date="day", start="2026-03-11", end="2026-03-30")
    assert len(block.df) == 20 and block.df["day"].min() == pd.Timestamp("2026-03-11")
    with pytest.warns(UserWarning, match=r"1 row outside … to 2026-04-28"):
        CalendarHeatmap(df_signed, date="day", end="2026-04-28")


def test_no_warning_when_every_row_is_inside(df_signed: pd.DataFrame, recwarn: pytest.WarningsRecorder) -> None:
    CalendarHeatmap(df_signed, date="day", start="2026-01-01", end="2026-12-31")
    assert not recwarn.list


def test_the_span_uses_local_days(df_timestamps_near_midnight: pd.DataFrame) -> None:
    # 2026-01-10 03:30 UTC is 2026-01-09 in Montréal: inside a span that ends on the 9th.
    with pytest.warns(UserWarning, match="2 rows outside"):
        block = CalendarHeatmap(df_timestamps_near_midnight, date="aware", tz="America/Montreal", end="2026-01-09")
    assert len(block.df) == 1


def test_calendars_with_the_same_span_line_up(df_signed: pd.DataFrame, df_pipeline_log: pd.DataFrame) -> None:
    start, end = "2026-01-01", "2026-04-30"
    with pytest.warns(UserWarning):
        a = _cells(_soup(CalendarHeatmap(df_pipeline_log, date="run_at", start=start, end=end)))
    b = _cells(_soup(CalendarHeatmap(df_signed, date="day", start=start, end=end)))
    assert a.keys() == b.keys()
    assert all((attr(a[d], "x"), attr(a[d], "y")) == (attr(b[d], "x"), attr(b[d], "y")) for d in a)


def test_events_outside_the_span_are_not_shown(df_pipeline_log: pd.DataFrame, df_events: pd.DataFrame) -> None:
    with pytest.warns(UserWarning):
        soup = _soup(CalendarHeatmap(df_pipeline_log, date="run_at", events=df_events,
                                     start="2025-12-28", end="2026-01-31"))
    legend = find_one(soup, ".bf-cal__legend").get_text(" ")
    assert "Holiday freeze" in legend and "Migration" in legend and "Incident" not in legend
    assert len(soup.select(".bf-cal__event")) == 2


def test_an_empty_span_draws_an_empty_calendar(df_empty: pd.DataFrame) -> None:
    frame = pd.DataFrame({"d": pd.to_datetime(pd.Series([], dtype="object"))})
    soup = _soup(CalendarHeatmap(frame, date="d", start="2026-01-01", end="2026-01-31"))
    days = _days(soup)
    assert len(days) == 31 and all("bf-cal__day--empty" in classes(c) for c in _cells(soup).values())
    assert "no dates" in render_calendar(CalendarHeatmap(frame, date="d", start="2026-01-01"))


@pytest.mark.parametrize(("kwargs", "match"), [
    ({"start": "soon"}, "start must be a date"),
    ({"end": 12.5j}, "end must be a date"),
    ({"start": "2026-05-01", "end": "2026-04-01"}, r"start \(2026-05-01\) is after end \(2026-04-01\)"),
])
def test_bad_spans(df_signed: pd.DataFrame, kwargs: dict[str, t.Any], match: str) -> None:
    with pytest.raises(bf.BriefingError, match=match):
        CalendarHeatmap(df_signed, date="day", **kwargs)


# ── group order (#154) ────────────────────────────────────────────────────────


def _groups(block: CalendarHeatmap) -> list[str]:
    return [g.get_text() for g in _soup(block).select(".bf-cal__group")]


def test_group_order_puts_the_listed_groups_first(df_pipeline_log: pd.DataFrame) -> None:
    frame = df_pipeline_log.assign(team=df_pipeline_log["team"].replace({"export": "z-export"}))
    frame.loc[frame.index[:5], "team"] = "middle"
    assert _groups(CalendarHeatmap(frame, date="run_at", group="team")) == ["ingest", "middle", "z-export"]
    assert _groups(CalendarHeatmap(frame, date="run_at", group="team", group_order=["z-export"])) == [
        "z-export", "ingest", "middle"]  # the rest by name
    assert _groups(CalendarHeatmap(frame, date="run_at", group="team",
                                   group_order=["middle", "z-export", "ingest"])) == ["middle", "z-export", "ingest"]


def test_group_order_and_the_rows_panel(df_pipeline_log: pd.DataFrame) -> None:
    soup = _soup(CalendarHeatmap(df_pipeline_log, date="run_at", group="team", group_order=["ingest"],
                                 on_click="rows"))
    assert [attr(c, "data-group") for c in soup.select(".bf-cal__calendar")] == ["ingest", "export"]


def test_group_order_with_numeric_groups() -> None:
    frame = pd.DataFrame({"d": pd.date_range("2026-01-01", periods=6), "year": [2024, 2025, 2026] * 2})
    assert _groups(CalendarHeatmap(frame, date="d", group="year", group_order=["2026"])) == ["2026", "2024", "2025"]


def test_unknown_group_names_say_which_groups_exist(df_pipeline_log: pd.DataFrame) -> None:
    with pytest.raises(bf.BriefingError, match=r"\['Ingest'\], which aren't values of 'team'. "
                                               r"Pass names from \['export', 'ingest'\]"):
        CalendarHeatmap(df_pipeline_log, date="run_at", group="team", group_order=["Ingest"])
