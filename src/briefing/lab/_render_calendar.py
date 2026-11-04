"""CalendarHeatmap rendering — a GitHub-style day calendar drawn as SVG in Python.

One cell per day, weeks as columns, rows for weekdays. The grid runs across
year boundaries with month labels and a year marker; days without data are
drawn as an empty outline, distinct from a zero. Tooltips are SVG ``<title>``
elements, so they need no JavaScript and survive printing.
"""
from __future__ import annotations

import datetime as dt
import html as _html
import math
import typing as t
from collections.abc import Callable
from dataclasses import dataclass

from briefing.renderers.registry import IdGen
from briefing.renderers.script_json import script_json

if t.TYPE_CHECKING:
    from briefing.lab._blocks import CalendarHeatmap

#: GitHub's contribution greens, from the lowest non-zero level to the highest.
GITHUB = ["#9be9a8", "#40c463", "#30a14e", "#216e39"]

_CELL = 11
_STEP = 14  # cell + gap
_LEFT = 32  # weekday labels
_TOP = 34  # year and month labels
_LANE = 14  # one event lane
_WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
_MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _svg_open(cls: str, width: int, height: int, label: str) -> str:
    """Open a calendar SVG that scales with its block (#106).

    ``width``/``height`` are the natural size. The CSS stretches the SVG to the block's
    width, between its natural width (``--bf-cal-w``) and twice that.
    """
    return (f'<svg class="{cls}" xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
            f'viewBox="0 0 {width} {height}" style="--bf-cal-w: {width}px" role="img" aria-label="{label}">')


@dataclass(frozen=True)
class _Event:
    start: dt.date
    end: dt.date
    label: str


# ── data ──────────────────────────────────────────────────────────────────────


def _local_dates(series: t.Any) -> t.Any:
    """Calendar dates of a date or timestamp column (aware timestamps keep their own wall date)."""
    import pandas as pd

    stamps = pd.to_datetime(series)
    return stamps.dt.date


def _stamps(block: CalendarHeatmap) -> t.Any:
    """The block's timestamps; with ``tz``, aware ones are converted and naive ones left as local."""
    import pandas as pd

    stamps = pd.to_datetime(block.df[block.date])
    if block.tz is not None and getattr(stamps.dt, "tz", None) is not None:
        stamps = stamps.dt.tz_convert(block.tz)
    return stamps


def _aggregate(block: CalendarHeatmap, keys: dict[str, t.Any]) -> dict[str | None, dict[t.Any, float]]:
    """Per group (or ``None``), the aggregated value of each key (a day, or a weekday-hour)."""
    import pandas as pd

    df = block.df.assign(**keys)
    df = df.dropna(subset=list(keys))
    by = ([block.group] if block.group else []) + list(keys)
    if block.value is None:
        series = df.groupby(by, sort=True).size()
    else:
        values = pd.to_numeric(df[block.value], errors="coerce")
        series = df.assign(_v=values).dropna(subset=["_v"]).groupby(by, sort=True)["_v"].agg(block.agg)
    out: dict[str | None, dict[t.Any, float]] = {}
    for key, v in series.items():
        parts = key if isinstance(key, tuple) else (key,)
        g, rest = (parts[0], parts[1:]) if block.group else (None, parts)
        out.setdefault(None if g is None else str(g), {})[rest[0] if len(rest) == 1 else tuple(rest)] = float(v)
    if block.group:
        for g in sorted({str(x) for x in block.df[block.group].dropna().unique()}):
            out.setdefault(g, {})
    return out or {None: {}}


def _targets(block: CalendarHeatmap, group: str | None) -> Callable[[dt.date], float | None]:
    import pandas as pd

    expected = block.expected
    if expected is None:
        return lambda _day: None
    if isinstance(expected, int | float):
        return lambda _day: float(expected)
    if isinstance(expected, pd.Series):
        table = {d: float(v) for d, v in zip(_local_dates(pd.Series(expected.index)), expected.to_numpy(), strict=True)
                 if pd.notna(v)}
        return table.get
    frame = expected
    if block.group:
        frame = frame[frame[block.group].astype(str) == group]
    table = {d: float(v) for d, v in zip(_local_dates(frame[block.date]), frame["expected"], strict=True)
             if pd.notna(v)}
    return table.get


def _events(block: CalendarHeatmap) -> list[_Event]:
    import pandas as pd

    if block.events is None:
        return []
    frame = block.events
    starts = _local_dates(frame["start"])
    ends = _local_dates(frame["end"]) if "end" in frame.columns else starts
    labels = frame["label"] if "label" in frame.columns else pd.Series([""] * len(frame), index=frame.index)
    events = []
    for start, end, label in zip(starts, ends, labels, strict=True):
        if pd.isna(start):
            continue
        end = start if pd.isna(end) or end < start else end
        events.append(_Event(start, end, "" if pd.isna(label) else str(label)))
    return sorted(events, key=lambda e: (e.start, e.end))


# ── colour ────────────────────────────────────────────────────────────────────


def _hex(c: str) -> tuple[int, int, int]:
    c = c.lstrip("#")
    if len(c) == 3:
        c = "".join(ch * 2 for ch in c)
    return int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)


def _mix(a: str, b: str, f: float) -> str:
    (r1, g1, b1), (r2, g2, b2) = _hex(a), _hex(b)
    return "#{:02x}{:02x}{:02x}".format(*(round(x + (y - x) * f) for x, y in ((r1, r2), (g1, g2), (b1, b2))))


def _scale(block: CalendarHeatmap, values: list[float]) -> Callable[[float], tuple[str, str]]:
    """Map a value to (fill, extra class). ``"github"`` keeps zero (and below) as its own grey level."""
    if not values:
        return lambda v: ("", "bf-cal__day--zero")
    lo, hi = min(values), max(values)
    if block.colors == "github":
        top = max(hi, 0.0)

        def github(v: float) -> tuple[str, str]:
            if v <= 0 or top == 0:
                return "", "bf-cal__day--zero"
            return GITHUB[min(len(GITHUB) - 1, max(0, math.ceil(v / top * len(GITHUB)) - 1))], ""
        return github
    colors = t.cast("list[str]", block.colors)
    if block.center is not None:
        mid = float(block.center)
        reach = max(abs(lo - mid), abs(hi - mid)) or 1.0

        def diverging(v: float) -> tuple[str, str]:
            f = min(1.0, abs(v - mid) / reach)
            return _mix(colors[1], colors[0] if v < mid else colors[2], f), ("bf-cal__day--zero" if v == 0 else "")
        return diverging
    span = hi - lo

    def stepped(v: float) -> tuple[str, str]:
        i = len(colors) - 1 if span == 0 else min(len(colors) - 1, int((v - lo) / span * len(colors)))
        return colors[i], ("bf-cal__day--zero" if v == 0 else "")
    return stepped


# ── drawing ───────────────────────────────────────────────────────────────────


def _clickable(block: CalendarHeatmap) -> str:
    return ' role="button" tabindex="0"' if block.on_click == "rows" else ""


def _group_attr(block: CalendarHeatmap, group: str | None) -> str:
    return f' data-group="{_html.escape(group)}"' if block.on_click == "rows" and group is not None else ""


def _fmt(v: float) -> str:
    """A value as the reader should see it, in the tooltip and the legend (#109).

    Whole numbers get thousands separators; other values of 1 or more are rounded to
    2 decimals (trailing zeros dropped) and never use scientific notation; values
    below 1 keep 4 significant digits, and only those below 0.0001 use an exponent.
    """
    v = float(v)
    if v.is_integer():
        return f"{int(v):,}"
    if abs(v) >= 1:
        return f"{v:,.2f}".rstrip("0").rstrip(".")
    return f"{v:.4g}" if abs(v) >= 1e-4 else f"{v:.2e}"


def _what(block: CalendarHeatmap) -> str:
    if block.value is None:
        return "rows"
    return block.value if block.agg == "sum" else f"{block.agg} {block.value}"


def _days_svg(
    block: CalendarHeatmap,
    first: dt.date,
    last: dt.date,
    data: dict[dt.date, float],
    colour: Callable[[float], tuple[str, str]],
    target: Callable[[dt.date], float | None],
    events: list[_Event],
) -> str:
    shift = 0 if block.week_start == "monday" else 1  # row of a date = (weekday + shift) % 7
    grid_start = first - dt.timedelta(days=(first.weekday() + shift) % 7)
    weeks = (last - grid_start).days // 7 + 1

    def pos(day: dt.date) -> tuple[int, int]:
        offset = (day - grid_start).days
        return offset // 7, (day.weekday() + shift) % 7

    lanes: list[dt.date] = []  # last day used in each event lane
    placed: list[tuple[_Event, int]] = []
    for event in events:
        lane = next((i for i, end in enumerate(lanes) if end < event.start), len(lanes))
        lanes[lane:lane + 1] = [event.end]
        placed.append((event, lane))
    event_days = {e.start + dt.timedelta(days=i) for e in events for i in range((e.end - e.start).days + 1)}

    grid_h = 7 * _STEP
    width = _LEFT + weeks * _STEP
    height = _TOP + grid_h + (len(lanes) * _LANE + 6 if lanes else 0)
    parts = [_svg_open("bf-cal__days", width, height, "Calendar heatmap")]

    for row in (0, 2, 4):  # Mon, Wed, Fri
        name = _WEEKDAYS[(row - shift) % 7]
        y = _TOP + ((row + shift) % 7) * _STEP + _CELL - 1
        parts.append(f'<text class="bf-cal__weekday" x="0" y="{y}">{name}</text>')

    year_shown: int | None = None
    for week in range(weeks):
        days = [grid_start + dt.timedelta(days=week * 7 + i) for i in range(7)]
        firsts = [d for d in days if d.day == 1 and first <= d <= last]
        x = _LEFT + week * _STEP
        # The first column names its month, unless the next month starts too close for both labels.
        next_week_starts_month = any((grid_start + dt.timedelta(days=7 + j)).day == 1 for j in range(7))
        start_label = week == 0 and not next_week_starts_month
        if firsts or start_label:
            month_day = firsts[0] if firsts else first
            parts.append(f'<text class="bf-cal__month" x="{x}" y="{_TOP - 6}">{_MONTHS[month_day.month - 1]}</text>')
            if month_day.year != year_shown:
                if year_shown is not None:
                    parts.append(f'<line class="bf-cal__year-line" x1="{x - 1.5}" y1="{_TOP - 4}" '
                                 f'x2="{x - 1.5}" y2="{_TOP + grid_h - 3}"/>')
                parts.append(f'<text class="bf-cal__year" x="{x}" y="{_TOP - 20}">{month_day.year}</text>')
                year_shown = month_day.year

    what = _what(block)
    day = first
    while day <= last:
        col, row = pos(day)
        x, y = _LEFT + col * _STEP, _TOP + row * _STEP
        value, goal = data.get(day), target(day)
        when = f"{_WEEKDAYS[day.weekday()]} {day.isoformat()}"
        cls = ["bf-cal__day"]
        fill = ""
        if value is None:
            cls.append("bf-cal__day--empty")
            tip = f"{when} · no data"
        else:
            fill, extra = colour(value)
            if extra:
                cls.append(extra)
            tip = f"{when} · {_fmt(value)} {what}"
        # No data falls short of a positive target only: nothing is below a target of 0.
        if goal is not None and ((value is None and goal > 0) or (value is not None and value < goal)):
            cls.append("bf-cal__day--below")
            tip += f" · below target {_fmt(goal)}"
        if day in event_days:
            cls.append("bf-cal__day--event")
            tip += "".join(f" · {e.label}" for e in events if e.start <= day <= e.end and e.label)
        fill_attr = f' fill="{fill}"' if fill else ""
        parts.append(f'<rect class="{" ".join(cls)}" x="{x}" y="{y}" width="{_CELL}" height="{_CELL}" rx="2"'
                     f'{fill_attr}{_clickable(block)} data-date="{day.isoformat()}">'
                     f"<title>{_html.escape(tip)}</title></rect>")
        day += dt.timedelta(days=1)

    for event, lane in placed:
        y = _TOP + grid_h + 4 + lane * _LANE
        c1, _ = pos(max(event.start, first))
        c2, _ = pos(min(event.end, last))
        span = f"{event.start.isoformat()}" + ("" if event.end == event.start else f" to {event.end.isoformat()}")
        tip = _html.escape(f"{event.label} · {span}" if event.label else span)
        if event.end == event.start:
            cx = _LEFT + c1 * _STEP + _CELL / 2
            parts.append(f'<g class="bf-cal__event bf-cal__event--day"><circle cx="{cx}" cy="{y + 5}" r="4"/>'
                         f'<title>{tip}</title></g>')
        else:
            x1 = _LEFT + c1 * _STEP
            w = (c2 - c1) * _STEP + _CELL
            # The label goes inside the band only when it fits (about 5.5 px per character at 9 px);
            # every event is also listed, with its dates, under the calendar.
            fits = event.label and len(event.label) * 5.5 + 8 <= w
            text = f'<text x="{x1 + 4}" y="{y + 8.5}">{_html.escape(event.label)}</text>' if fits else ""
            parts.append(f'<g class="bf-cal__event bf-cal__event--span"><rect x="{x1}" y="{y}" width="{w}" '
                         f'height="{_LANE - 3}" rx="3"/>{text}<title>{tip}</title></g>')
    parts.append("</svg>")
    return "".join(parts)


def _legend(
    block: CalendarHeatmap,
    values: list[float],
    colour: Callable[[float], tuple[str, str]],
    events: list[_Event],
    *,
    targets: bool,
) -> str:
    def swatch(fill: str, cls: str = "") -> str:
        style = f' style="background:{fill}"' if fill else ""
        return f'<span class="bf-cal__swatch {cls}"{style}></span>'

    def item(content: str) -> str:
        return f'<span class="bf-cal__legend-item">{content}</span>'

    items: list[str] = []
    if block.colors == "github":
        items.append(item("Less " + swatch("", "bf-cal__swatch--zero") + "".join(swatch(c) for c in GITHUB) + " More"))
    elif values:
        lo, hi = min(values), max(values)
        steps = [lo + (hi - lo) * i / 4 for i in range(5)]
        items.append(item(f"{_fmt(lo)} " + "".join(swatch(colour(v)[0]) for v in steps) + f" {_fmt(hi)}"))
    items.append(item(swatch("", "bf-cal__swatch--empty") + "no data"))
    if targets:
        items.append(item(swatch("", "bf-cal__swatch--below") + "below target"))
    for event in events:
        when = event.start.isoformat() + ("" if event.end == event.start else f" to {event.end.isoformat()}")
        mark = "bf-cal__swatch--event-day" if event.end == event.start else "bf-cal__swatch--event-span"
        text = f"{_html.escape(event.label)} ({when})" if event.label else when
        items.append(item(swatch("", mark) + text))
    return f'<div class="bf-cal__legend">{"".join(items)}</div>'


def _days_view(block: CalendarHeatmap) -> str:
    stamps = _stamps(block)
    daily = _aggregate(block, {"_day": stamps.dt.date})
    all_days = [d for days in daily.values() for d in days]
    values = [v for days in daily.values() for v in days.values()]
    events = _events(block)
    if not all_days and not events:
        return '<div class="bf-placeholder">⚠ CalendarHeatmap: no dates to display.</div>'
    span = all_days + [d for e in events for d in (e.start, e.end)]
    first, last = min(span), max(span)
    colour = _scale(block, values)
    calendars = []
    for group, data in daily.items():
        title = f'<div class="bf-cal__group">{_html.escape(group)}</div>' if group is not None else ""
        svg = _days_svg(block, first, last, data, colour, _targets(block, group), events)
        calendars.append(f'<div class="bf-cal__calendar"{_group_attr(block, group)}>{title}'
                         f'<div class="bf-cal__scroll">{svg}</div></div>')
    return "".join(calendars) + _legend(block, values, colour, events, targets=block.expected is not None)


_HOUR_STEP = 16


def _hours_svg(block: CalendarHeatmap, data: dict[t.Any, float], colour: Callable[[float], tuple[str, str]]) -> str:
    shift = 0 if block.week_start == "monday" else 1
    width, height = _LEFT + 24 * _HOUR_STEP, 18 + 7 * _HOUR_STEP
    parts = [_svg_open("bf-cal__hours", width, height, "Activity by weekday and hour")]
    for hour in range(0, 24, 3):
        parts.append(f'<text class="bf-cal__month" x="{_LEFT + hour * _HOUR_STEP}" y="12">{hour:02d}</text>')
    what = _what(block)
    for weekday in range(7):
        row = (weekday + shift) % 7
        y = 18 + row * _HOUR_STEP
        parts.append(f'<text class="bf-cal__weekday" x="0" y="{y + _CELL - 1}">{_WEEKDAYS[weekday]}</text>')
        for hour in range(24):
            value = data.get((weekday, hour))
            cls = ["bf-cal__hour"]
            fill = ""
            label = f"{_WEEKDAYS[weekday]} {hour:02d}:00–{(hour + 1) % 24:02d}:00"
            if value is None:
                cls.append("bf-cal__hour--empty")
                tip = f"{label} · no data"
            else:
                fill, extra = colour(value)
                if extra:
                    cls.append(extra.replace("day", "hour"))
                tip = f"{label} · {_fmt(value)} {what}"
            fill_attr = f' fill="{fill}"' if fill else ""
            parts.append(f'<rect class="{" ".join(cls)}" x="{_LEFT + hour * _HOUR_STEP}" y="{y}" width="{_CELL + 2}" '
                         f'height="{_CELL + 2}" rx="2"{fill_attr}{_clickable(block)} data-hour="{weekday}-{hour}">'
                         f"<title>{_html.escape(tip)}</title></rect>")
    parts.append("</svg>")
    return "".join(parts)


def _hours_view(block: CalendarHeatmap) -> str:
    stamps = _stamps(block)
    hourly = _aggregate(block, {"_wd": stamps.dt.day_of_week, "_h": stamps.dt.hour})
    values = [v for cells in hourly.values() for v in cells.values()]
    colour = _scale(block, values)
    grids = []
    for group, data in hourly.items():
        title = f'<div class="bf-cal__group">{_html.escape(group)}</div>' if group is not None else ""
        grids.append(f'<div class="bf-cal__calendar"{_group_attr(block, group)}>{title}<div class="bf-cal__scroll">'
                     f"{_hours_svg(block, data, colour)}</div></div>")
    # Targets are per day, so the hour legend has no "below target" entry.
    return "".join(grids) + _legend(block, values, colour, [], targets=False)


_VIEW_LABELS = {"days": "Days", "hours": "Hours"}

_PANEL = ('<div class="bf-cal__panel" hidden><div class="bf-cal__panel-head"><span class="bf-cal__panel-title"></span>'
          '<button type="button" class="bf-cal__panel-close" aria-label="Close">×</button></div>'
          '<div class="bf-cal__panel-body"></div></div>')


def _rows_data(block: CalendarHeatmap) -> str:
    """The rows behind each day and hour (up to ROWS_PER_CELL each), for the click panel."""
    from briefing.renderers.table import _fmt as cell_text

    stamps = _stamps(block)
    df = block.df.assign(_day=stamps.dt.date, _wd=stamps.dt.day_of_week, _h=stamps.dt.hour)
    df = df[df["_day"].notna()]
    columns = [str(c) for c in block.df.columns]
    cells: dict[str, dict[str, t.Any]] = {}
    keys = {"days": ("d", ["_day"]), "hours": ("h", ["_wd", "_h"])}
    for view in block.views:
        prefix, by = keys[view]
        for key, rows in df.groupby(by + ([block.group] if block.group else []), sort=True):
            parts: tuple[t.Any, ...] = key if isinstance(key, tuple) else (key,)
            where = parts[0].isoformat() if view == "days" else f"{parts[0]}-{parts[1]}"
            name = "|".join([prefix, where] + ([str(parts[-1])] if block.group else []))
            head = rows[block.df.columns].head(block.ROWS_PER_CELL)
            cells[name] = {"total": len(rows),
                           "rows": [[cell_text(v) for v in r] for r in head.itertuples(index=False, name=None)]}
    payload = script_json({"columns": columns, "cells": cells})
    return f'<script type="application/json" class="bf-cal__rows">{payload}</script>'


def render_calendar(block: CalendarHeatmap, idgen: IdGen | None = None) -> str:
    """Render a :class:`~briefing.lab.CalendarHeatmap` block to HTML with inline SVG."""
    views = {"days": _days_view, "hours": _hours_view}
    extra = _PANEL + _rows_data(block) if block.on_click == "rows" else ""
    if len(block.views) == 1:
        return f'<figure class="bf-block bf-calendar">{views[block.views[0]](block)}{extra}</figure>'
    # Both views: the report's own tab markup, so report.js, keyboard navigation and print apply.
    uid = (idgen or IdGen()).next("cal")
    tabs, panels = "", ""
    for i, view in enumerate(block.views):
        tab_id, panel_id = f"{uid}-tab-{i}", f"{uid}-panel-{i}"
        tabs += (f'<button class="bf-select__tab" role="tab" id="{tab_id}" aria-controls="{panel_id}">'
                 f"{_VIEW_LABELS[view]}</button>")
        panels += (f'<div class="bf-select__panel" role="tabpanel" id="{panel_id}" aria-labelledby="{tab_id}">'
                   f"{views[view](block)}</div>")
    return (f'<figure class="bf-block bf-calendar"><div class="bf-select bf-cal__views" id="{uid}">'
            f'<div class="bf-select__tablist" role="tablist">{tabs}</div>{panels}</div>{extra}</figure>')


__all__ = ["GITHUB", "render_calendar"]
