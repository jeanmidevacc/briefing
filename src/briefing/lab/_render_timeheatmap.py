"""TimeHeatmap rendering (#111): a grid crossing two time units of one date column, drawn as SVG.

It shares the calendar's look and script (``calendar.js``: width fitting, the instant
tooltip, ``on_click="rows"``): cells are ``rect.bf-cal__cell`` with a ``<title>`` and a
``data-cell`` key, in an ``svg.bf-cal__grid`` inside a ``figure.bf-calendar``.

Counts and sums are averaged per occurrence: each cell's total is divided by how many
distinct periods of the finer of its two units (hours, days, weeks…) fall in the data's
date range. Cells that can't exist (31 February, ISO week 53 of a 52-week year) are left
blank; cells with no data have a dashed outline, as in the calendar.
"""
from __future__ import annotations

import html as _html
import math
import typing as t
from collections.abc import Callable

from briefing.lab._render_calendar import (
    _MONTHS,
    _PANEL,
    _WEEKDAYS,
    _aggregate,
    _clickable,
    _fmt,
    _group_attr,
    _legend,
    _scale,
    _stamps,
    _svg_open,
    _what,
)
from briefing.renderers.script_json import script_json

if t.TYPE_CHECKING:
    from briefing.lab._blocks import TimeHeatmap

_CELL = 13
_STEP = 16
_TOP = 18
_CHAR = 6  # the width of a label character, roughly, at the grid's font size

#: How fine each unit is: an occurrence of a cell is a period of the finer of its two units.
_LEVEL = {"hour": 0, "weekday": 1, "day": 1, "week": 2, "month": 3, "quarter": 4, "year": 5}
_PERIODS = {0: "hour", 1: "day", 2: "week", 3: "month", 4: "quarter", 5: "year"}

#: Averaged per occurrence: totals that grow with how often a cell occurs.
_ADDITIVE = ("sum", "count")


def _unit(stamps: t.Any, unit: str) -> t.Any:
    """Each timestamp's value in *unit*, as integers (weekday 0 is Monday)."""
    dt = stamps.dt
    if unit == "week":
        return dt.isocalendar().week.astype("Int64")
    attribute = {"hour": "hour", "weekday": "day_of_week", "day": "day", "month": "month",
                 "quarter": "quarter", "year": "year"}[unit]
    return getattr(dt, attribute)


def _period(stamps: t.Any, level: int) -> t.Any:
    """An id for each timestamp's period at *level*: its hour, day, ISO week, month, quarter or year."""
    dt = stamps.dt
    if level == 0:
        return dt.floor("h")
    if level == 1:
        return dt.normalize()
    if level == 2:
        iso = dt.isocalendar()
        return iso.year.astype("int64") * 100 + iso.week.astype("int64")
    if level == 3:
        return dt.year * 100 + dt.month
    if level == 4:
        return dt.year * 10 + dt.quarter
    return dt.year


def _range(stamps: t.Any, hourly: bool) -> t.Any:
    """Every hour (or day) from the first timestamp to the last, as a Series of timestamps."""
    import pandas as pd

    known = stamps.dropna()
    unit = "h" if hourly else "D"
    first, last = known.min().floor(unit), known.max().floor(unit)
    return pd.Series(pd.date_range(first, last, freq=unit))


def _occurrences(block: TimeHeatmap, stamps: t.Any) -> dict[tuple[int, int], int]:
    """How many periods of the finer unit each cell covers in the data's date range."""
    import pandas as pd

    instants = _range(stamps, "hour" in (block.rows, block.columns))
    level = min(_LEVEL[block.rows], _LEVEL[block.columns])
    frame = pd.DataFrame({"r": _unit(instants, block.rows), "c": _unit(instants, block.columns),
                          "p": _period(instants, level)})
    counts = frame.groupby(["r", "c"])["p"].nunique()
    pairs = t.cast("dict[tuple[int, int], int]", counts.to_dict())
    return {(int(r), int(c)): int(n) for (r, c), n in pairs.items()}


def _possible(block: TimeHeatmap, years: list[int]) -> set[tuple[int, int]] | None:
    """The cells that can exist (``None``: all of them), from a long run of days."""
    import pandas as pd

    units = (block.rows, block.columns)
    if "hour" in units:
        return None  # every hour of every day exists
    start, end = (f"{min(years)}-01-01", f"{max(years)}-12-31") if "year" in units else ("2000-01-01", "2027-12-31")
    days = pd.Series(pd.date_range(start, end, freq="D"))
    pairs = pd.DataFrame({"r": _unit(days, block.rows), "c": _unit(days, block.columns)}).drop_duplicates()
    return {(int(r), int(c)) for r, c in pairs.itertuples(index=False)}


def _axis(block: TimeHeatmap, unit: str, seen: set[int], years: list[int]) -> list[int]:
    """The values of *unit* along an axis, in order."""
    if unit == "hour":
        return list(range(24))
    if unit == "weekday":
        return [(d + (6 if block.week_start == "sunday" else 0)) % 7 for d in range(7)]
    if unit == "day":
        return list(range(1, 32))
    if unit == "week":
        return list(range(1, 54 if 53 in seen or ("year" in (block.rows, block.columns) and _has_53(years)) else 53))
    if unit == "month":
        return list(range(1, 13))
    if unit == "quarter":
        return [1, 2, 3, 4]
    return list(range(min(years), max(years) + 1))


def _has_53(years: list[int]) -> bool:
    import datetime as dt

    return any(dt.date(y, 12, 28).isocalendar()[1] == 53 for y in years)


def _label(unit: str, value: int) -> str:
    """How an axis names a value: ``09``, ``Mon``, ``31``, ``W12``, ``Jan``, ``Q1``, ``2024``."""
    return {"hour": f"{value:02d}", "weekday": _WEEKDAYS[value % 7], "day": str(value), "week": f"W{value}",
            "month": _MONTHS[(value - 1) % 12], "quarter": f"Q{value}", "year": str(value)}[unit]


def _labelled(unit: str, value: int, index: int, every: int) -> bool:
    """Whether a column gets a label: every third hour, round days and weeks, else as many as fit."""
    if unit == "hour":
        return value % 3 == 0
    if unit in ("day", "week"):
        return value == 1 or value % (5 if unit == "day" else 4) == 0
    return index % every == 0


def _place(unit: str, value: int) -> str:
    """How a tooltip names a value: as on the axis, but ``09:00`` for an hour."""
    return f"{value:02d}:00" if unit == "hour" else _label(unit, value)


# ── drawing ───────────────────────────────────────────────────────────────────


def _grid_svg(
    block: TimeHeatmap,
    rows: list[int],
    columns: list[int],
    cells: dict[tuple[int, int], tuple[float, float | None]],
    occurs: dict[tuple[int, int], int],
    possible: set[tuple[int, int]] | None,
    colour: Callable[[float], tuple[str, str]],
) -> str:
    left = max(24, _CHAR * max(len(_label(block.rows, r)) for r in rows) + 8)
    every = max(1, math.ceil((_CHAR * max(len(_label(block.columns, c)) for c in columns) + 4) / _STEP))
    width, height = left + len(columns) * _STEP, _TOP + len(rows) * _STEP
    title = f"{_what(block)} by {block.rows} and {block.columns}"
    parts = [_svg_open("bf-cal__grid", width, height, title)]
    for j, column in enumerate(columns):
        if _labelled(block.columns, column, j, every):
            parts.append(f'<text class="bf-cal__month" x="{left + j * _STEP}" y="12">'
                         f"{_html.escape(_label(block.columns, column))}</text>")
    what, period = _what(block), _PERIODS[min(_LEVEL[block.rows], _LEVEL[block.columns])]
    for i, row in enumerate(rows):
        y = _TOP + i * _STEP
        name = _html.escape(_label(block.rows, row))
        parts.append(f'<text class="bf-cal__weekday" x="0" y="{y + _CELL - 2}">{name}</text>')
        for j, column in enumerate(columns):
            key = (row, column)
            if possible is not None and key not in possible:
                continue  # no such date: left blank
            place = f"{_place(block.rows, row)} {_place(block.columns, column)}"
            cls, fill = ["bf-cal__cell"], ""
            if key not in cells:
                cls.append("bf-cal__cell--empty")
                tip = f"{place} · no data"
            else:
                shown, total = cells[key]
                fill, extra = colour(shown)
                if extra:
                    cls.append(extra.replace("day", "cell"))
                if total is None:
                    tip = f"{place} · {_fmt(shown)} {what}"
                else:
                    n = occurs.get(key, 0)
                    tip = (f"{place} · {_fmt(shown)} {what} on average · "
                           f"{_fmt(total)} over {n} {period}{'' if n == 1 else 's'}")
            fill_attr = f' fill="{fill}"' if fill else ""
            parts.append(f'<rect class="{" ".join(cls)}" x="{left + j * _STEP}" y="{y}" width="{_CELL}" '
                         f'height="{_CELL}" rx="2"{fill_attr}{_clickable(block)} data-cell="{row}-{column}">'
                         f"<title>{_html.escape(tip)}</title></rect>")
    parts.append("</svg>")
    return "".join(parts)


def _rows_data(block: TimeHeatmap, stamps: t.Any) -> str:
    """The rows behind each cell (up to ROWS_PER_CELL each), for the click panel."""
    from briefing.renderers.table import _fmt as cell_text

    df = block.df.assign(_r=_unit(stamps, block.rows), _c=_unit(stamps, block.columns)).dropna(subset=["_r", "_c"])
    cells: dict[str, dict[str, t.Any]] = {}
    for key, rows in df.groupby(["_r", "_c"] + ([block.group] if block.group else []), sort=True):
        parts: tuple[t.Any, ...] = key if isinstance(key, tuple) else (key,)
        name = "|".join(["c", f"{int(parts[0])}-{int(parts[1])}"] + ([str(parts[2])] if block.group else []))
        head = rows[block.df.columns].head(block.ROWS_PER_CELL)
        cells[name] = {"total": len(rows),
                       "rows": [[cell_text(v) for v in r] for r in head.itertuples(index=False, name=None)]}
    payload = script_json({"columns": [str(c) for c in block.df.columns], "cells": cells})
    return f'<script type="application/json" class="bf-cal__rows">{payload}</script>'


def render_timeheatmap(block: TimeHeatmap) -> str:
    """Render a :class:`~briefing.lab.TimeHeatmap` block to HTML with inline SVG."""
    stamps = _stamps(block)
    if stamps.dropna().empty:
        return '<div class="bf-block bf-placeholder">⚠ TimeHeatmap: no dates to display.</div>'
    keys = {"_r": _unit(stamps, block.rows), "_c": _unit(stamps, block.columns)}
    totals = _aggregate(block, keys)
    occurs = _occurrences(block, stamps)
    averaged = block.value is None or block.agg in _ADDITIVE
    groups: dict[str | None, dict[tuple[int, int], tuple[float, float | None]]] = {}
    for group, data in totals.items():
        groups[group] = {}
        for (r, c), v in data.items():
            key = (int(r), int(c))
            groups[group][key] = (v / max(occurs.get(key, 1), 1), v) if averaged else (v, None)
    years = sorted({int(y) for y in stamps.dt.year.dropna()})
    seen_rows = {r for cells in groups.values() for r, _ in cells}
    seen_columns = {c for cells in groups.values() for _, c in cells}
    rows = _axis(block, block.rows, seen_rows, years)
    columns = _axis(block, block.columns, seen_columns, years)
    possible = _possible(block, years)
    values = [shown for cells in groups.values() for shown, _ in cells.values()]
    colour = _scale(block, values)
    grids = []
    for group, cells in groups.items():
        title = f'<div class="bf-cal__group">{_html.escape(group)}</div>' if group is not None else ""
        svg = _grid_svg(block, rows, columns, cells, occurs, possible, colour)
        grids.append(f'<div class="bf-cal__calendar"{_group_attr(block, group)}>{title}'
                     f'<div class="bf-cal__scroll">{svg}</div></div>')
    blank = possible is not None and any((r, c) not in possible for r in rows for c in columns)
    legend = _legend(block, values, colour, [], targets=False, blank=blank)
    extra = _PANEL + _rows_data(block, stamps) if block.on_click == "rows" else ""
    return f'<figure class="bf-block bf-calendar bf-timeheatmap">{"".join(grids)}{legend}{extra}</figure>'


__all__ = ["render_timeheatmap"]
