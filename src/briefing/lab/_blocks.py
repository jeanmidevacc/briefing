"""``briefing.lab`` blocks: DataProfile, DataDive.

DataProfile  — per-column statistics with inline SVG mini-charts.
DataDive     — interactive dot explorer drawn with hand-rolled SVG + vanilla JS.

These live in ``briefing.lab`` (``pip install briefing[lab]``) to keep the core
grammar small. The classes here define the public API surface; rendering logic
lives in ``briefing/lab/_render_profile.py`` and ``briefing/lab/_render_datadive.py``.
"""
from __future__ import annotations

import re
import typing as t
import warnings

from briefing._error import BriefingError
from briefing._frames import to_pandas
from briefing.blocks.base import Block, BlockId

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

    Example::

        bf.lab.DataProfile(df)
        bf.lab.DataProfile(df, missing_threshold=0.10)  # red at >10% missing
    """

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
    colour.

    ``facet_row`` and ``facet_col`` are accepted but not drawn yet: passing one
    emits a ``UserWarning``. Faceting is planned for DataDive v2 (#16).

    Fully self-contained: the plot is drawn with hand-rolled SVG and vanilla JS
    (no Vega, D3, or CDN). The row data is embedded in the page as JSON.

    Example::

        bf.lab.DataDive(df)
        bf.lab.DataDive(df, x="revenue", y="units", color="region", max_rows=5_000)
    """

    #: DataFrames larger than this are sampled with a warning.
    MAX_ROWS: t.ClassVar[int] = 10_000

    def __init__(
        self,
        df: pd.DataFrame | t.Any,
        x: str | None = None,
        y: str | None = None,
        color: str | None = None,
        facet_row: str | None = None,
        facet_col: str | None = None,
        layout: str = "scatter",
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
            ("facet_row", facet_row), ("facet_col", facet_col),
        ]:
            if col_val is not None and col_val not in df.columns:
                raise BriefingError(
                    f"DataDive: column {col_val!r} (passed as '{col_name}') "
                    f"not found in DataFrame. Available: {list(df.columns)}"
                )

        facets = [p for p, v in (("facet_row", facet_row), ("facet_col", facet_col)) if v is not None]
        if facets:
            warnings.warn(
                f"DataDive: {' and '.join(facets)} {'are' if len(facets) > 1 else 'is'} accepted but not drawn "
                "yet; the dots are not split into facets. Faceting is planned for DataDive v2 "
                "(https://github.com/jeanmidevacc/briefing/issues/16).",
                UserWarning,
                stacklevel=2,
            )

        self.df = df
        self.x = x
        self.y = y
        self.color = color
        self.facet_row = facet_row
        self.facet_col = facet_col
        self.layout = layout
        self.max_rows = max_rows


class CalendarHeatmap(Block):
    """GitHub-style calendar heatmap: one cell per day, weeks as columns.

    Counts the rows per day, or aggregates a value column, and colours each day.
    Days without data look different from days with a zero; the grid runs
    continuously across a year boundary, with month labels and a year marker.

    Args:
        df: The data, as any dataframe briefing accepts (pandas, polars, pyarrow…).
        date: Column holding the date or timestamp of each row.
        value: Column to aggregate per day; ``None`` counts the rows.
        agg: How to aggregate ``value``: ``"sum"``, ``"mean"``, ``"median"``,
            ``"min"``, ``"max"`` or ``"count"``.
        group: Column to split by: one calendar per group, stacked, on one shared colour scale.
        views: ``("days",)``, ``("hours",)`` or ``("days", "hours")``: the day calendar
            and/or a 7 × 24 weekday-by-hour grid; with both, tabs switch between them.
            The hour view needs timestamps with a time of day.
        tz: A time zone such as ``"America/Montreal"``. Converts timezone-aware
            timestamps only; naive timestamps and plain dates are taken as already
            local, so a date at midnight never moves to the previous day.
        colors: ``"github"`` (GitHub's green scale) or a list of CSS colours, low to high.
        center: A midpoint for a diverging scale (e.g. ``0`` for values that go
            negative); ``colors`` is then three hex colours: below, at and above it.
        week_start: ``"monday"`` or ``"sunday"``: the first row of the grid.
        expected: A target per day, flagged when a day is below it (days with no
            data count as below): a number, a Series indexed by date, or a
            DataFrame with the ``date`` column, an ``expected`` column and, with
            ``group``, the group column.
        events: Dates to mark: a list of dates, or a DataFrame with ``start``,
            optional ``end`` and ``label`` columns; spans draw as bands.
        on_click: ``"rows"`` lists the rows behind a day or an hour in a panel
            when it is clicked (up to ``ROWS_PER_CELL`` rows per cell, embedded in
            the report); ``None`` (default) for no click action.
        name: Stable block id.
        label: Tab or dropdown label when the block is inside a ``Select``.

    Example::

        bf.lab.CalendarHeatmap(runs, date="run_at", value="rows", expected=1000)
        bf.lab.CalendarHeatmap(ledger, date="day", value="balance", center=0)
    """

    AGGS: t.ClassVar[tuple[str, ...]] = ("sum", "mean", "median", "min", "max", "count")
    #: Rows embedded per day or hour for on_click="rows"; the panel says when there are more.
    ROWS_PER_CELL: t.ClassVar[int] = 50

    def __init__(
        self,
        df: pd.DataFrame | t.Any,
        date: str,
        value: str | None = None,
        agg: str = "sum",
        group: str | None = None,
        views: tuple[str, ...] | list[str] = ("days",),
        tz: str | None = None,
        colors: str | list[str] = "github",
        center: float | None = None,
        week_start: str = "monday",
        expected: float | pd.Series | pd.DataFrame | None = None,
        events: t.Any = None,
        on_click: str | None = None,
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
        if not views or any(v not in ("days", "hours") for v in views) or len(set(views)) != len(views):
            raise BriefingError(
                f"CalendarHeatmap: views must be ('days',), ('hours',) or ('days', 'hours'), not {views!r}."
            )
        if tz is not None:
            _check_tz(tz)
        if "hours" in views and not _has_times(frame[date]):
            raise BriefingError(
                f"CalendarHeatmap: the hour view needs a time of day, but {date!r} holds dates only. "
                "Pass timestamps, or views=('days',)."
            )
        if week_start not in ("monday", "sunday"):
            raise BriefingError(f"CalendarHeatmap: week_start must be 'monday' or 'sunday', not {week_start!r}.")
        self.colors = _check_colors(colors, center)
        self.df = frame
        self.date, self.value, self.agg, self.group = date, value, agg, group
        self.center, self.week_start = center, week_start
        self.views, self.tz = views, tz
        self.on_click = on_click
        self.expected = _check_expected(expected, date, group)
        self.events = _check_events(events)


_HEX = re.compile(r"^#(?:[0-9a-fA-F]{3}){1,2}$")


def _check_tz(tz: str) -> None:
    import zoneinfo

    try:
        zoneinfo.ZoneInfo(tz)
    except (zoneinfo.ZoneInfoNotFoundError, ValueError) as exc:
        raise BriefingError(
            f"CalendarHeatmap: unknown time zone {tz!r}; use an IANA name such as 'Europe/Paris'."
        ) from exc


def _has_times(column: t.Any) -> bool:
    """Whether a column holds timestamps with a time of day (not dates only)."""
    import pandas as pd

    if not (pd.api.types.is_datetime64_any_dtype(column) or pd.api.types.is_string_dtype(column)):
        return False
    stamps = pd.to_datetime(column, errors="coerce").dropna()
    return bool(len(stamps)) and bool((stamps.dt.normalize() != stamps).any())


def _check_colors(colors: str | list[str], center: float | None) -> str | list[str]:
    if colors == "github":
        if center is not None:
            raise BriefingError("CalendarHeatmap: center= needs colors= as three hex colours: below, at and above it.")
        return colors
    if isinstance(colors, str) or not isinstance(colors, list | tuple) or len(colors) < 2:
        raise BriefingError(
            f"CalendarHeatmap: colors must be 'github' or a list of at least two colours, not {colors!r}."
        )
    if center is not None:
        if len(colors) != 3:
            raise BriefingError(
                "CalendarHeatmap: with center=, colors must be exactly three colours: below, at, above."
            )
        if not all(isinstance(c, str) and _HEX.match(c) for c in colors):
            raise BriefingError("CalendarHeatmap: with center=, colors must be hex colours such as '#d73027'.")
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


def _check_events(events: t.Any) -> t.Any:
    import pandas as pd

    if events is None:
        return None
    if isinstance(events, pd.DataFrame):
        if "start" not in events.columns:
            raise BriefingError(
                "CalendarHeatmap: an events DataFrame needs a 'start' column (and optional 'end', 'label')."
            )
        return events
    try:
        starts = pd.to_datetime(list(events))
    except (TypeError, ValueError) as exc:
        raise BriefingError("CalendarHeatmap: events must be a list of dates or a DataFrame with 'start'.") from exc
    return pd.DataFrame({"start": starts})


# ── public re-exports ─────────────────────────────────────────────────────────

__all__: list[str] = ["CalendarHeatmap", "DataDive", "DataProfile"]
