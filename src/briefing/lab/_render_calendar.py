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
from briefing.scale import Scale

if t.TYPE_CHECKING:
    from briefing.lab._blocks import CalendarHeatmap, Legend, TimeHeatmap

    #: The heatmaps that share these helpers: the calendar, and the time-pattern grid (#111).
    Heatmap: t.TypeAlias = "CalendarHeatmap | TimeHeatmap"  # explicit: mypy may read this module first

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
    color: str | None = None  # #152

    @property
    def style(self) -> str:
        """The attribute that gives this event's marks its colour (CSS reads ``--bf-event``)."""
        return f' style="--bf-event: {_html.escape(self.color)}"' if self.color else ""


# ── data ──────────────────────────────────────────────────────────────────────


def _local_dates(series: t.Any) -> t.Any:
    """Calendar dates of a date or timestamp column (aware timestamps keep their own wall date)."""
    import pandas as pd

    stamps = pd.to_datetime(series)
    return stamps.dt.date


def _stamps(block: Heatmap) -> t.Any:
    """The block's timestamps; with ``tz``, aware ones are converted and naive ones left as local."""
    import pandas as pd

    stamps = pd.to_datetime(block.df[block.date])
    if block.tz is not None and getattr(stamps.dt, "tz", None) is not None:
        stamps = stamps.dt.tz_convert(block.tz)
    return stamps


def _aggregate(block: Heatmap, keys: dict[str, t.Any]) -> dict[str | None, dict[t.Any, float]]:
    """Per group (or ``None``), the aggregated value of each key (a day, or a time-pattern cell)."""
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
        # group_order first, in its order; the rest as sorted above (#154).
        first = [g for g in block.group_order or [] if g in out]
        out = {g: out[g] for g in first + [g for g in out if g not in first]}
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


def _events(block: CalendarHeatmap | Legend) -> list[_Event]:
    import pandas as pd

    if block.events is None:
        return []
    frame = block.events
    starts = _local_dates(frame["start"])
    ends = _local_dates(frame["end"]) if "end" in frame.columns else starts
    labels = frame["label"] if "label" in frame.columns else pd.Series([""] * len(frame), index=frame.index)
    colors = frame["color"] if "color" in frame.columns else pd.Series([None] * len(frame), index=frame.index)
    events = []
    for start, end, label, color in zip(starts, ends, labels, colors, strict=True):
        if pd.isna(start):
            continue
        end = start if pd.isna(end) or end < start else end
        events.append(_Event(start, end, "" if pd.isna(label) else str(label),
                             None if color is None or pd.isna(color) else str(color).strip()))
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


def _scale(block: Heatmap, values: list[float]) -> Callable[[float], tuple[str, str]]:
    """Map a value to (fill, extra class). ``"github"`` keeps zero (and below) as its own grey level."""
    if not values:
        return lambda v: ("", "bf-cal__day--zero")
    lo, hi = min(values), max(values)
    if isinstance(block.colors, Scale):  # one meaning in every block (#175): zero is a value like any other
        scale = block.colors
        low, high = scale.bounds(values)
        return lambda v: (scale.at(v, low, high), "")
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


def _clickable(block: Heatmap) -> str:
    return ' role="button" tabindex="0"' if block.on_click == "rows" else ""


def _group_attr(block: Heatmap, group: str | None) -> str:
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


def _what(block: Heatmap) -> str:
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

    grid_h = 7 * _STEP
    width = _LEFT + weeks * _STEP
    height = _TOP + grid_h + (len(lanes) * _LANE + 6 if lanes else 0)
    parts = [_svg_open("bf-cal__days", width, height, "Calendar heatmap")]

    for weekday, name in enumerate(_WEEKDAYS):  # every row named, on its own row (#113)
        y = _TOP + ((weekday + shift) % 7) * _STEP + _CELL - 1
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
        on_day = [e for e in events if e.start <= day <= e.end]
        tip += "".join(f" · {e.label}" for e in on_day if e.label)
        # Only a single-day event outlines its day: a span's band says where it runs, and its days
        # keep their data colours in view (#152).
        single = next((e for e in on_day if e.start == e.end), None)
        if single is not None:
            cls.append("bf-cal__day--event")
        fill_attr = f' fill="{fill}"' if fill else ""
        style = single.style if single is not None else ""
        parts.append(f'<rect class="{" ".join(cls)}" x="{x}" y="{y}" width="{_CELL}" height="{_CELL}" rx="2"'
                     f'{fill_attr}{style}{_clickable(block)} data-date="{day.isoformat()}">'
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
            parts.append(f'<g class="bf-cal__event bf-cal__event--day"{event.style}>'
                         f'<circle cx="{cx}" cy="{y + 5}" r="4"/><title>{tip}</title></g>')
        else:
            x1 = _LEFT + c1 * _STEP
            w = (c2 - c1) * _STEP + _CELL
            # The label goes inside the band only when it fits (about 5.5 px per character at 9 px);
            # every event is also listed, with its dates, under the calendar.
            fits = event.label and len(event.label) * 5.5 + 8 <= w
            text = f'<text x="{x1 + 4}" y="{y + 8.5}">{_html.escape(event.label)}</text>' if fits else ""
            parts.append(f'<g class="bf-cal__event bf-cal__event--span"{event.style}>'
                         f'<rect x="{x1}" y="{y}" width="{w}" height="{_LANE - 3}" rx="3"/>'
                         f'{text}<title>{tip}</title></g>')
    parts.append("</svg>")
    return "".join(parts)


def _legend(
    block: Heatmap | Legend,
    values: list[float],
    colour: Callable[[float], tuple[str, str]],
    events: list[_Event],
    *,
    targets: bool,
    blank: bool = False,
) -> str:
    def swatch(fill: str, cls: str = "", style: str = "") -> str:
        style = style or (f' style="background:{fill}"' if fill else "")
        return f'<span class="bf-cal__swatch {cls}"{style}></span>'

    def item(content: str) -> str:
        return f'<span class="bf-cal__legend-item">{content}</span>'

    items: list[str] = []
    if isinstance(block.colors, Scale):
        if values or block.colors.domain is not None:
            low, high = block.colors.bounds(values)
            ramp = f'<span class="bf-cal__ramp" style="background:{block.colors.gradient(low, high)}"></span>'
            items.append(item(f"{_fmt(low)} {ramp} {_fmt(high)}"))
    elif block.colors == "github":
        items.append(item("Less " + swatch("", "bf-cal__swatch--zero") + "".join(swatch(c) for c in GITHUB) + " More"))
    elif values:
        lo, hi = min(values), max(values)
        steps = [lo + (hi - lo) * i / 4 for i in range(5)]
        items.append(item(f"{_fmt(lo)} " + "".join(swatch(colour(v)[0]) for v in steps) + f" {_fmt(hi)}"))
    items.append(item(swatch("", "bf-cal__swatch--empty") + "no data"))
    if blank:
        items.append(item(swatch("", "bf-cal__swatch--blank") + "no such date"))
    if targets:
        items.append(item(swatch("", "bf-cal__swatch--below") + "below target"))
    for event in events:
        when = event.start.isoformat() + ("" if event.end == event.start else f" to {event.end.isoformat()}")
        mark = "bf-cal__swatch--event-day" if event.end == event.start else "bf-cal__swatch--event-span"
        text = f"{_html.escape(event.label)} ({when})" if event.label else when
        items.append(item(swatch("", mark, event.style) + text))
    return f'<div class="bf-cal__legend">{"".join(items)}</div>'


def render_legend(block: Legend) -> str:
    """A :class:`~briefing.Legend` block (#177): the heatmaps' legend, once for the page."""
    from briefing.renderers.inline import inline_markdown

    title = f'<div class="bf-legend__title">{inline_markdown(block.title)}</div>' if block.title else ""
    colour = _scale(t.cast("Heatmap", block), [])
    return f'<div class="bf-block bf-legend">{title}{_legend(block, [], colour, _events(block), targets=False)}</div>'


def _edge(day: str | None) -> dt.date | None:
    """``start=`` or ``end=`` (an ISO string) as a date."""
    return dt.date.fromisoformat(day) if day else None


def _days_view(block: CalendarHeatmap) -> str:
    stamps = _stamps(block)
    daily = _aggregate(block, {"_day": stamps.dt.date})
    all_days = [d for days in daily.values() for d in days]
    values = [v for days in daily.values() for v in days.values()]
    start, end = _edge(block.start), _edge(block.end)
    # Events outside start…end aren't drawn or listed (#153); those across an edge are clipped when drawn.
    events = [e for e in _events(block) if (start is None or e.end >= start) and (end is None or e.start <= end)]
    span = all_days + [d for e in events for d in (e.start, e.end)]
    if not span and (start is None or end is None):
        return '<div class="bf-placeholder">⚠ CalendarHeatmap: no dates to display.</div>'
    first = start or min(span)
    last = end or max(span)
    colour = _scale(block, values)
    calendars = []
    for group, data in daily.items():
        title = f'<div class="bf-cal__group">{_html.escape(group)}</div>' if group is not None else ""
        svg = _days_svg(block, first, last, data, colour, _targets(block, group), events)
        calendars.append(f'<div class="bf-cal__calendar"{_group_attr(block, group)}>{title}'
                         f'<div class="bf-cal__scroll">{svg}</div></div>')
    legend = _legend(block, values, colour, events, targets=block.expected is not None) if block.legend else ""
    return "".join(calendars) + legend


_PANEL = ('<div class="bf-cal__panel" hidden><div class="bf-cal__panel-head"><span class="bf-cal__panel-title"></span>'
          '<button type="button" class="bf-cal__panel-close" aria-label="Close">×</button></div>'
          '<div class="bf-cal__panel-body"></div></div>')


def _rows_data(block: CalendarHeatmap) -> str:
    """The rows behind each day (up to ROWS_PER_CELL each), for the click panel."""
    from briefing.renderers.table import _fmt as cell_text

    stamps = _stamps(block)
    df = block.df.assign(_day=stamps.dt.date)
    df = df[df["_day"].notna()]
    columns = [str(c) for c in block.df.columns]
    cells: dict[str, dict[str, t.Any]] = {}
    for key, rows in df.groupby(["_day"] + ([block.group] if block.group else []), sort=True):
        parts: tuple[t.Any, ...] = key if isinstance(key, tuple) else (key,)
        name = "|".join(["d", parts[0].isoformat()] + ([str(parts[-1])] if block.group else []))
        head = rows[block.df.columns].head(block.ROWS_PER_CELL)
        cells[name] = {"total": len(rows),
                       "rows": [[cell_text(v) for v in r] for r in head.itertuples(index=False, name=None)]}
    payload = script_json({"columns": columns, "cells": cells})
    return f'<script type="application/json" class="bf-cal__rows">{payload}</script>'


def render_calendar(block: CalendarHeatmap, idgen: IdGen | None = None) -> str:
    """Render a :class:`~briefing.lab.CalendarHeatmap` block to HTML with inline SVG."""
    extra = _PANEL + _rows_data(block) if block.on_click == "rows" else ""
    return f'<figure class="bf-block bf-calendar">{_days_view(block)}{extra}</figure>'


__all__ = ["GITHUB", "render_calendar"]
