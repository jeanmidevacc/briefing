"""``briefing.lab`` blocks: DataProfile, DataDive.

DataProfile  — per-column statistics with inline SVG mini-charts.
DataDive     — interactive dot explorer drawn with hand-rolled SVG + vanilla JS.

These live in ``briefing.lab`` (``pip install briefing[lab]``) to keep the core
grammar small. The classes here define the public API surface; rendering logic
lives in ``briefing/lab/_render_profile.py`` and ``briefing/lab/_render_datadive.py``.
"""
from __future__ import annotations

import datetime as dt
import functools
import typing as t
import warnings
from collections.abc import Mapping

from briefing._colors import CSS_COLOR
from briefing._error import BriefingError
from briefing._frames import to_pandas
from briefing.blocks.base import Block, BlockId
from briefing.scale import Scale

if t.TYPE_CHECKING:
    import pandas as pd


class DataProfile(Block):
    """Per-column statistical profiling block.

    For each column in the DataFrame, renders:

    - dtype, row count, missing % (highlighted in red when > 20 %)
    - **Numeric columns**: mean, std, min / quartiles / max + inline SVG histogram
    - **Categorical columns**: n_unique, top values + inline SVG bar chart
    - **Datetime columns**: range, gap detection

    Mini-charts are pure SVG — no plotting dependency.

    Args:
        df: The data, as any dataframe briefing accepts.
        missing_threshold: Share of missing values (0–1) above which a column's
            missing count is highlighted in red.
        max_categories: Most frequent values shown for categorical columns.
        name: Stable block id (letters, digits, ``_`` and ``-``), its link in the report (``#page/name``).
        label: Tab or dropdown label when the block is inside a ``Select``.

    Example::

        bf.lab.DataProfile(df)
        bf.lab.DataProfile(df, missing_threshold=0.10)  # red at >10% missing
    """

    embed_noun: t.ClassVar[str | None] = "profile"

    def __init__(
        self,
        df: pd.DataFrame | t.Any,
        missing_threshold: float = 0.20,
        max_categories: int = 20,
        name: BlockId | None = None,
        label: str | None = None,
    ) -> None:
        if not 0.0 <= missing_threshold <= 1.0:
            raise BriefingError("'missing_threshold' must be between 0.0 and 1.0.")
        super().__init__(name=name, label=label)
        self.df = to_pandas(df, block="DataProfile")
        self.missing_threshold = missing_threshold
        self.max_categories = max_categories


class DataDive(Block):
    """Interactive dot explorer — similar to Google's Facets Dive.

    Each row in the DataFrame becomes a dot in a 2-D space. Dropdowns let the
    viewer dynamically reassign which columns drive X position, Y position and
    colour. The legend under them filters: a click hides or shows a category's
    dots, and Alt+click shows that category alone. Clicking a dot opens a card
    with its whole row; **Pin** keeps it, so two rows can be compared side by side.

    ``facet_row`` and ``facet_col`` split the dots into small multiples, one panel
    per value, on shared scales; the viewer can change or remove them too.

    Fully self-contained: the dots are drawn on a canvas with vanilla JS (no Vega,
    D3, or CDN), from the data embedded in the page, packed by column.

    Args:
        df: The data, as any dataframe briefing accepts.
        x: Column on the X axis at first (the viewer can change it).
        y: Column on the Y axis at first.
        color: Column that colours the dots at first.
        facet_row: Column that splits the dots into rows of panels at first.
        facet_col: Column that splits the dots into columns of panels at first.
        buckets: How many groups a column makes when it splits the dots (a facet, or a
            ``"tile"`` axis): a number is cut into that many bins with round edges, and
            categories keep their most frequent values plus an "other". One number for
            every column, or ``{"age": 4}`` per column (the others keep 5).
        layout: ``"scatter"`` (two axes) or ``"tile"`` (packed dots per cell).
        colors: A :class:`~briefing.Scale` for the dots' colours, so they match the other
            blocks of the report. A categorical scale colours the categories it names
            (others take the theme's palette); a numeric one colours numbers and dates.
            Without it, categories take the theme's palette and numbers a ramp to its accent.
        title: Column that names each dot: the heading of its tooltip and of the card that
            opens when the dot is clicked. Without it, a card is headed by its row number.
        max_rows: Larger frames are sampled down to this many rows, with a warning.
        name: Stable block id (letters, digits, ``_`` and ``-``), its link in the report (``#page/name``).
        label: Tab or dropdown label when the block is inside a ``Select``.

    Example::

        bf.lab.DataDive(df)
        bf.lab.DataDive(df, x="revenue", y="units", color="region", max_rows=5_000)
        bf.lab.DataDive(df, color="region", colors=bf.Scale(["#d71920", "#1a4782"], domain=["East", "West"]))
    """

    embed_noun: t.ClassVar[str | None] = "chart"
    packs_data: t.ClassVar[bool] = True

    #: DataFrames larger than this are sampled with a warning: the canvas stays responsive up to it (#16).
    MAX_ROWS: t.ClassVar[int] = 100_000

    def __init__(
        self,
        df: pd.DataFrame | t.Any,
        x: str | None = None,
        y: str | None = None,
        color: str | None = None,
        facet_row: str | None = None,
        facet_col: str | None = None,
        buckets: int | Mapping[str, int] = 5,
        layout: str = "scatter",
        colors: Scale | Mapping[str, t.Any] | None = None,
        title: str | None = None,
        max_rows: int = MAX_ROWS,
        name: BlockId | None = None,
        label: str | None = None,
    ) -> None:
        if layout not in ("scatter", "tile"):
            raise BriefingError(f"DataDive: 'layout' must be 'scatter' or 'tile', got {layout!r}.")

        super().__init__(name=name, label=label)
        df = to_pandas(df, block="DataDive")

        if len(df) > max_rows:
            warnings.warn(
                f"DataDive: DataFrame has {len(df):,} rows — sampling to {max_rows:,}. "
                "Increase 'max_rows' to include more points.",
                stacklevel=2,
            )
            df = df.sample(max_rows, random_state=42)

        # Validate that explicitly requested columns exist.
        for col_name, col_val in [
            ("x", x), ("y", y), ("color", color),
            ("facet_row", facet_row), ("facet_col", facet_col), ("title", title),
        ]:
            if col_val is not None and col_val not in df.columns:
                raise BriefingError(
                    f"DataDive: column {col_val!r} (passed as '{col_name}') "
                    f"not found in DataFrame. Available: {list(df.columns)}"
                )

        self.buckets = _check_buckets(buckets, df.columns)

        self.df = df
        self.x = x
        self.y = y
        self.color = color
        self.facet_row = facet_row
        self.facet_col = facet_col
        self.layout = layout
        self.colors = Scale.of(colors) if isinstance(colors, Mapping) else colors
        if self.colors is not None and not isinstance(self.colors, Scale):
            raise BriefingError(f"DataDive: colors must be a bf.Scale, not {colors!r}.")
        self.title = title
        self.max_rows = max_rows


def _check_buckets(buckets: t.Any, columns: t.Any) -> int | dict[str, int]:
    """``buckets=`` as a whole number of 1 or more, or such a number per column name."""
    def whole(value: t.Any, where: str) -> int:
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise BriefingError(f"DataDive: {where} must be a whole number of groups, 1 or more; got {value!r}.")
        return value

    if isinstance(buckets, Mapping):
        unknown = [str(k) for k in buckets if k not in columns]
        if unknown:
            raise BriefingError(f"DataDive: buckets names {unknown[0]!r}, which isn't a column. "
                                f"Available: {list(columns)}")
        return {str(k): whole(v, f"buckets[{k!r}]") for k, v in buckets.items()}
    return whole(buckets, "buckets")


#: The hour view, deprecated in 0.2.2, was removed in 0.5.0 (#111).
HOURS_VIEW_REMOVED = (
    "CalendarHeatmap: the hour view (views=('hours',) or ('days', 'hours')) was removed in briefing 0.5.0. "
    "Use bf.lab.TimeHeatmap(df, date=..., rows='weekday', columns='hour') for the weekday-by-hour grid, "
    "next to the calendar in a bf.Select or bf.Group if you want both; the calendar is the day view alone."
)


#: The heatmaps' center= gave way to bf.Scale(center=) (#175), and was removed in 0.8.0 (#196).
CENTER_REMOVED = (
    "{block}: center= was removed in briefing 0.8.0 (deprecated since 0.6.0). Pass "
    "colors=bf.Scale([below, at, above], center=...) instead: the same diverging scale, mixed in OKLab, "
    "and one you can share between blocks."
)

_P = t.ParamSpec("_P")


def _without_center(init: t.Callable[_P, None]) -> t.Callable[_P, None]:
    """Reject the removed center= with what to pass instead, rather than a bare TypeError (#196)."""

    @functools.wraps(init)
    def checked(*args: _P.args, **kwargs: _P.kwargs) -> None:
        if "center" in kwargs:
            raise BriefingError(CENTER_REMOVED.format(block=type(args[0]).__name__))
        init(*args, **kwargs)

    return checked


class CalendarHeatmap(Block):
    """GitHub-style calendar heatmap: one cell per day, weeks as columns.

    Counts the rows per day, or aggregates a value column, and colours each day.
    Days without data look different from days with a zero; the grid runs
    continuously across a year boundary, with month labels and a year marker.
    The calendar fits the width available (the report or a ``Group`` column),
    between 0.6x and 2x its natural size; below that it scrolls sideways.
    Hovering a cell shows its date and exact value.

    Args:
        df: The data, as any dataframe briefing accepts (pandas, polars, pyarrow…).
        date: Column holding the date or timestamp of each row.
        value: Column to aggregate per day; ``None`` counts the rows.
        agg: How to aggregate ``value``: ``"sum"``, ``"mean"``, ``"median"``,
            ``"min"``, ``"max"`` or ``"count"``.
        group: Column to split by: one calendar per group, stacked, on one shared colour scale.
        views: Only ``("days",)``; the hour view was removed in 0.5.0 (use :class:`TimeHeatmap`).
        tz: A time zone such as ``"America/Montreal"``. Converts timezone-aware
            timestamps only; naive timestamps and plain dates are taken as already local.
        colors: ``"github"``, a list of CSS colours (low to high, spread over the data), or a
            :class:`~briefing.Scale` (the same colours for the same values everywhere).
        week_start: ``"monday"`` or ``"sunday"``: the first row of the grid.
        expected: A target per day, flagged when a day is below it (days with no
            data count as below): a number, a Series indexed by date, or a
            DataFrame with the ``date`` column, an ``expected`` column and, with
            ``group``, the group column.
        events: Dates to mark: a list of dates, or a DataFrame with ``start`` and optional
            ``end``, ``label`` and ``color`` (a CSS colour; the accent by default) columns.
            A day is outlined and dotted, a span drawn as a band.
        on_click: ``"rows"`` lists the rows behind a day in a panel
            when it is clicked (up to ``ROWS_PER_CELL`` per cell); ``None`` for none.
        start: The first day shown (``"2026-05-19"`` or a date), whatever the data
            covers; ``None`` starts at the first day with data or an event. Rows
            before it are left out, with a warning.
        end: The last day shown; ``None`` ends at the last day with data or an
            event. Rows after it are left out, with a warning. Calendars with the
            same ``start`` and ``end`` line up week for week.
        group_order: Group names to draw first, in this order (e.g.
            ``["Worldwide", "United States"]``); other groups follow by name.
            Needs ``group``; a name that isn't a group is an error.
        legend: ``False`` hides this block's legend (show one :class:`~briefing.Legend` instead).
        name: Stable block id (letters, digits, ``_`` and ``-``), its link in the report (``#page/name``).
        label: Tab or dropdown label when the block is inside a ``Select``.

    Example::

        bf.lab.CalendarHeatmap(runs, date="run_at", value="rows", expected=1000)
        bf.lab.CalendarHeatmap(searches, date="day", value="interest",
                               start="2026-05-19", end="2026-12-31")
        bf.lab.CalendarHeatmap(ledger, date="day", value="balance",
                               colors=bf.Scale(["#dc2626", "#f3f4f6", "#16a34a"], center=0))
    """

    embed_noun: t.ClassVar[str | None] = "calendar"

    AGGS: t.ClassVar[tuple[str, ...]] = ("sum", "mean", "median", "min", "max", "count")
    #: Rows embedded per day or hour for on_click="rows"; the panel says when there are more.
    ROWS_PER_CELL: t.ClassVar[int] = 50

    @_without_center
    def __init__(
        self,
        df: pd.DataFrame | t.Any,
        date: str,
        value: str | None = None,
        agg: str = "sum",
        group: str | None = None,
        views: tuple[str, ...] | list[str] = ("days",),
        tz: str | None = None,
        colors: str | list[str] | Scale | Mapping[str, t.Any] = "github",
        week_start: str = "monday",
        expected: float | pd.Series | pd.DataFrame | None = None,
        events: t.Any = None,
        on_click: str | None = None,
        start: str | dt.date | None = None,
        end: str | dt.date | None = None,
        group_order: list[str] | None = None,
        legend: bool = True,
        name: BlockId | None = None,
        label: str | None = None,
    ) -> None:
        super().__init__(name=name, label=label)
        frame = to_pandas(df, block="CalendarHeatmap")
        for role, column in (("date", date), ("value", value), ("group", group)):
            if column is not None and column not in frame.columns:
                raise BriefingError(
                    f"CalendarHeatmap: column {column!r} (passed as {role}=) not found. "
                    f"Available: {list(frame.columns)}"
                )
        if agg not in self.AGGS:
            raise BriefingError(f"CalendarHeatmap: agg must be one of {', '.join(self.AGGS)}, not {agg!r}.")
        if on_click not in (None, "rows"):
            raise BriefingError(f"CalendarHeatmap: on_click must be 'rows' or None, not {on_click!r}.")
        views = tuple(views)
        if "hours" in views:
            raise BriefingError(HOURS_VIEW_REMOVED)
        if views != ("days",):
            raise BriefingError(f"CalendarHeatmap: views is ('days',), the day calendar, not {views!r}.")
        if tz is not None:
            _check_tz(tz)
        if week_start not in ("monday", "sunday"):
            raise BriefingError(f"CalendarHeatmap: week_start must be 'monday' or 'sunday', not {week_start!r}.")
        self.colors = _check_colors(colors)
        self.df = frame
        self.date, self.value, self.agg, self.group = date, value, agg, group
        self.week_start = week_start
        self.views, self.tz = views, tz
        self.on_click = on_click
        self.expected = _check_expected(expected, date, group)
        self.events = _check_events(events)
        self.group_order = _check_group_order(frame, group, group_order, "CalendarHeatmap")
        self.legend = _check_flag(legend, "CalendarHeatmap: legend")
        self.start, self.end = _check_day(start, "start"), _check_day(end, "end")
        if self.start and self.end and self.start > self.end:
            raise BriefingError(f"CalendarHeatmap: start ({self.start}) is after end ({self.end}).")
        if self.start or self.end:
            self.df = _within_span(self)


class TimeHeatmap(Block):
    """When something usually happens: a grid that crosses two units of one date column.

    Where :class:`CalendarHeatmap` shows what happened on which date, this shows a time
    pattern: weekday by hour (when do runs happen?), weekday by month (seasonality), day
    of the month by month (month-end effects), month by year (year over year). Counts and
    sums are averaged per occurrence of their cell in the data's date range ("Monday
    09:00" occurs once per Monday), so a weekday that appears five times in a month
    doesn't outweigh one that appears four times; means, medians, minimums and maximums
    aggregate the cell's rows directly. Cells that can't exist (31 February), cells with
    no data and zeros look different. Hovering a cell shows its value, its total and how
    many times it occurs.

    Args:
        df: The data, as any dataframe briefing accepts (pandas, polars, pyarrow…).
        date: Column holding the date or timestamp of each row.
        rows: The unit down the side: ``"hour"`` (0–23), ``"weekday"``, ``"day"`` (of the
            month), ``"week"`` (ISO week), ``"month"``, ``"quarter"`` or ``"year"``.
        columns: The unit across the top, one of the same, and not the same as ``rows``.
        value: Column to aggregate per cell; ``None`` counts the rows.
        agg: How to aggregate ``value``: ``"sum"``, ``"mean"``, ``"median"``, ``"min"``,
            ``"max"`` or ``"count"``. Sums and counts are averaged per occurrence.
        group: Column to split by: one grid per group, stacked, on one shared colour scale.
        tz: A time zone such as ``"America/Montreal"``. Converts timezone-aware
            timestamps only; naive timestamps and plain dates are taken as already local.
        colors: ``"github"``, a list of CSS colours (low to high, spread over the data), or a
            :class:`~briefing.Scale` (the same colours for the same values everywhere).
        week_start: ``"monday"`` or ``"sunday"``: the first weekday of a ``weekday`` axis.
        on_click: ``"rows"`` lists the rows behind a cell in a panel when it is clicked
            (up to ``ROWS_PER_CELL`` per cell); ``None`` for none.
        group_order: Group names to draw first, in this order (e.g.
            ``["Worldwide", "United States"]``); other groups follow by name.
            Needs ``group``; a name that isn't a group is an error.
        legend: ``False`` hides this block's legend (show one :class:`~briefing.Legend` instead).
        name: Stable block id (letters, digits, ``_`` and ``-``), its link in the report (``#page/name``).
        label: Tab or dropdown label when the block is inside a ``Select``.

    Example::

        bf.lab.TimeHeatmap(runs, date="run_at", rows="weekday", columns="hour")
        bf.lab.TimeHeatmap(sales, date="day", rows="month", columns="year", value="revenue")
    """

    embed_noun: t.ClassVar[str | None] = "heatmap"

    UNITS: t.ClassVar[tuple[str, ...]] = ("hour", "weekday", "day", "week", "month", "quarter", "year")
    AGGS: t.ClassVar[tuple[str, ...]] = CalendarHeatmap.AGGS
    #: Rows embedded per cell for on_click="rows"; the panel says when there are more.
    ROWS_PER_CELL: t.ClassVar[int] = 50

    @_without_center
    def __init__(
        self,
        df: pd.DataFrame | t.Any,
        date: str,
        rows: str,
        columns: str,
        value: str | None = None,
        agg: str = "sum",
        group: str | None = None,
        tz: str | None = None,
        colors: str | list[str] | Scale | Mapping[str, t.Any] = "github",
        week_start: str = "monday",
        on_click: str | None = None,
        group_order: list[str] | None = None,
        legend: bool = True,
        name: BlockId | None = None,
        label: str | None = None,
    ) -> None:
        super().__init__(name=name, label=label)
        frame = to_pandas(df, block="TimeHeatmap")
        for role, column in (("date", date), ("value", value), ("group", group)):
            if column is not None and column not in frame.columns:
                raise BriefingError(
                    f"TimeHeatmap: column {column!r} (passed as {role}=) not found. Available: {list(frame.columns)}"
                )
        for role, unit in (("rows", rows), ("columns", columns)):
            if unit not in self.UNITS:
                raise BriefingError(f"TimeHeatmap: {role} must be one of {', '.join(self.UNITS)}, not {unit!r}.")
        if rows == columns:
            raise BriefingError(f"TimeHeatmap: rows and columns must be two different units, not both {rows!r}.")
        if agg not in self.AGGS:
            raise BriefingError(f"TimeHeatmap: agg must be one of {', '.join(self.AGGS)}, not {agg!r}.")
        if on_click not in (None, "rows"):
            raise BriefingError(f"TimeHeatmap: on_click must be 'rows' or None, not {on_click!r}.")
        if week_start not in ("monday", "sunday"):
            raise BriefingError(f"TimeHeatmap: week_start must be 'monday' or 'sunday', not {week_start!r}.")
        if tz is not None:
            _check_tz(tz, "TimeHeatmap")
        if "hour" in (rows, columns) and not _has_times(frame[date]):
            raise BriefingError(
                f"TimeHeatmap: an hour axis needs a time of day, but {date!r} holds dates only. "
                "Pass timestamps, or other units."
            )
        self.colors = _check_colors(colors, "TimeHeatmap")
        self.df = frame
        self.date, self.rows, self.columns = date, rows, columns
        self.value, self.agg, self.group = value, agg, group
        self.tz, self.week_start, self.on_click = tz, week_start, on_click
        self.group_order = _check_group_order(frame, group, group_order, "TimeHeatmap")
        self.legend = _check_flag(legend, "TimeHeatmap: legend")




def _check_tz(tz: str, block: str = "CalendarHeatmap") -> None:
    import zoneinfo

    try:
        zoneinfo.ZoneInfo(tz)
    except (zoneinfo.ZoneInfoNotFoundError, ValueError) as exc:
        raise BriefingError(
            f"{block}: unknown time zone {tz!r}; use an IANA name such as 'Europe/Paris'."
        ) from exc


def _has_times(column: t.Any) -> bool:
    """Whether a column holds timestamps with a time of day (not dates only)."""
    import pandas as pd

    if not (pd.api.types.is_datetime64_any_dtype(column) or pd.api.types.is_string_dtype(column)):
        return False
    stamps = pd.to_datetime(column, errors="coerce").dropna()
    return bool(len(stamps)) and bool((stamps.dt.normalize() != stamps).any())


def _check_colors(colors: t.Any, block: str = "CalendarHeatmap") -> str | list[str] | Scale:
    if isinstance(colors, Mapping):
        colors = Scale.of(colors)
    if isinstance(colors, Scale):
        if colors.categorical:
            raise BriefingError(f"{block}: a categorical Scale colours categories; a heatmap needs one over numbers, "
                                "with domain=(low, high) or none.")
        return colors
    if colors == "github":
        return "github"
    if isinstance(colors, str) or not isinstance(colors, list | tuple) or len(colors) < 2:
        raise BriefingError(
            f"{block}: colors must be 'github', a list of at least two colours or a bf.Scale, not {colors!r}."
        )
    return [str(c) for c in colors]


def _check_expected(expected: t.Any, date: str, group: str | None) -> t.Any:
    import pandas as pd

    if expected is None or isinstance(expected, int | float | pd.Series):
        return expected
    if isinstance(expected, pd.DataFrame):
        needed = [date, "expected", *([group] if group else [])]
        missing = [c for c in needed if c not in expected.columns]
        if missing:
            raise BriefingError(
                f"CalendarHeatmap: the expected DataFrame needs the columns {needed}; missing {missing}."
            )
        return expected
    raise BriefingError(
        "CalendarHeatmap: expected must be a number, a Series indexed by date, or a DataFrame "
        f"with the date column and an 'expected' column; got {type(expected).__name__}."
    )


def _check_group_order(frame: pd.DataFrame, group: str | None, order: t.Any, block: str) -> list[str] | None:
    """``group_order=``: distinct names of existing groups (#154)."""
    if order is None:
        return None
    if isinstance(order, str) or not all(isinstance(name, str) for name in order):
        raise BriefingError(f"{block}: group_order must be a list of group names, not {order!r}.")
    if group is None:
        raise BriefingError(f"{block}: group_order needs group=, the column to split by.")
    names = sorted({str(x) for x in frame[group].dropna().unique()})
    unknown = [name for name in order if name not in names]
    if unknown:
        raise BriefingError(f"{block}: group_order lists {unknown!r}, which aren't values of {group!r}. "
                            f"Pass names from {names!r}.")
    if len(set(order)) != len(order):
        raise BriefingError(f"{block}: group_order names a group twice: {list(order)!r}.")
    return list(order)


def _check_day(day: t.Any, role: str) -> str | None:
    """A day for ``start=`` or ``end=``, as an ISO string (so the JSON form is plain text)."""
    import pandas as pd

    if day is None:
        return None
    try:
        stamp = pd.Timestamp(day)
    except (TypeError, ValueError) as exc:
        raise BriefingError(f"CalendarHeatmap: {role} must be a date such as '2026-05-19', not {day!r}.") from exc
    if pd.isna(stamp):
        raise BriefingError(f"CalendarHeatmap: {role} must be a date such as '2026-05-19', not {day!r}.")
    return stamp.date().isoformat()


def _within_span(block: CalendarHeatmap) -> pd.DataFrame:
    """The block's rows whose local day is within ``start``…``end`` (rows without a date stay), warning if any go."""
    import pandas as pd

    stamps = pd.to_datetime(block.df[block.date])  # as the renderer reads them: aware ones in tz
    if block.tz is not None and getattr(stamps.dt, "tz", None) is not None:
        stamps = stamps.dt.tz_convert(block.tz)
    days = stamps.dt.strftime("%Y-%m-%d")  # ISO strings compare in date order; NaT stays NaN
    outside = days.notna() & (((days < block.start) if block.start else False) |
                              ((days > block.end) if block.end else False))
    count = int(outside.sum())
    if count:
        span = f"{block.start or '…'} to {block.end or '…'}"
        warnings.warn(f"CalendarHeatmap: {count} row{'s' if count != 1 else ''} outside {span} left out.",
                      stacklevel=3)
    return block.df[~outside]


def _check_events(events: t.Any) -> t.Any:
    import pandas as pd

    if events is None:
        return None
    if isinstance(events, pd.DataFrame):
        if "start" not in events.columns:
            raise BriefingError(
                "CalendarHeatmap: an events DataFrame needs a 'start' column (and optional 'end', 'label', 'color')."
            )
        if "color" in events.columns:
            for color in events["color"].dropna():
                if not isinstance(color, str) or not CSS_COLOR.match(color.strip()):
                    raise BriefingError(f"CalendarHeatmap: event colours are CSS colours such as '#2dd4bf', "
                                        f"'teal' or 'rgb(45, 212, 191)', not {color!r}.")
        return events
    try:
        starts = pd.to_datetime(list(events))
    except (TypeError, ValueError) as exc:
        raise BriefingError("CalendarHeatmap: events must be a list of dates or a DataFrame with 'start'.") from exc
    return pd.DataFrame({"start": starts})


def _check_flag(value: object, where: str) -> bool:
    if not isinstance(value, bool):
        raise BriefingError(f"{where} is True or False, not {value!r}.")
    return value


class Legend(Block):
    """One legend for the blocks that share a :class:`~briefing.Scale`, such as a page of calendars.

    It shows the scale as the heatmaps do (a gradient, or its classes), a "no data" swatch
    and any events; give the blocks themselves ``legend=False``.

    Args:
        scale: A :class:`~briefing.Scale` with a ``domain``: the values its colours stand for,
            or the categories of a named palette (one swatch each).
        title: A short line above the legend, with inline Markdown as in captions.
        events: Dates to list, as ``CalendarHeatmap(events=)`` takes them, with their colours.
        name: Stable block id (letters, digits, ``_`` and ``-``), its link in the report (``#page/name``).
        label: Tab or dropdown label when the block is inside a ``Select``.

    Example::

        interest = bf.Scale(["#1b2c80", "#f5479a", "#ffc46b"], domain=(0, 100))
        bf.Legend(interest, title="Interest, 0 to 100", events=releases)
        bf.lab.CalendarHeatmap(df, date="day", value="interest", colors=interest, legend=False)
    """

    def __init__(
        self,
        scale: Scale | Mapping[str, t.Any],
        title: str | None = None,
        events: t.Any = None,
        name: BlockId | None = None,
        label: str | None = None,
    ) -> None:
        super().__init__(name=name, label=label)
        if isinstance(scale, Mapping):
            scale = Scale.of(scale)
        if not isinstance(scale, Scale):
            raise BriefingError(f"Legend: scale is a bf.Scale(...), not {scale!r}.")
        if scale.domain is None:
            raise BriefingError("Legend: the scale needs a domain=(low, high): without one its colours mean "
                                "different values in each block, and there is nothing fixed to show.")
        if title is not None and not isinstance(title, str):
            raise BriefingError(f"Legend: title is text, not {title!r}.")
        self.scale = scale
        self.colors = scale  # read by the heatmaps' legend code
        self.title = title.strip() or None if title else None
        self.events = _check_events(events)


# ── public re-exports ─────────────────────────────────────────────────────────

__all__: list[str] = ["CalendarHeatmap", "DataDive", "DataProfile", "Legend", "TimeHeatmap"]
