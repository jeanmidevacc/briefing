"""DataCompare rendering (#17): one row per column, its statistics per dataset and their distributions.

The statistics come from ``lab/_compare.py``; this module only writes them out:

- a legend naming each dataset in its colour, with its rows, and the distance measure;
- a row per column: its name, kind and badges, a table with one line per dataset, and an
  SVG chart that overlays the datasets (histograms on shared bins for numbers and dates,
  grouped bars of the top values for categories, or a cumulative curve above 20 values);
- the sort keys as ``data-*`` attributes on each row, and each chart's numbers in a
  ``script.bf-cmp__data``, so ``lab/static/compare.js`` can sort, filter and redraw: counts or
  percentages, a log scale, deciles. Its controls stay hidden without it, and the static
  charts (percentages, linear) are what prints and what a page without scripts shows.

Dataset *k* is drawn in ``var(--bf-cmp-k)``: report.css gives the first the theme's
accent and the next ones hues that stay apart from it.
"""
from __future__ import annotations

import datetime as dt
import html as _html
import operator
import typing as t

from briefing.lab._compare import Column, Side
from briefing.lab._render_profile import _fmt_num
from briefing.renderers.script_json import script_json

if t.TYPE_CHECKING:
    from briefing.lab._blocks import DataCompare
    from briefing.lab._select import Targets
    from briefing.renderers.registry import IdGen

#: How many dataset colours report.css defines; more datasets reuse them.
COLORS = 8

#: Category bars drawn per column; the rest go in "other".
BARS = 10

#: Longest category label drawn, in characters.
LABEL = 24

_W, _H = 320, 96  # the chart's viewBox
_PLOT_TOP, _PLOT_BOTTOM = 4, 92

_KIND_NAMES = {"numeric": "number", "datetime": "date", "categorical": "category"}


def _e(text: object) -> str:
    return _html.escape(str(text))


def _color(k: int) -> str:
    return f"var(--bf-cmp-{k % COLORS})"


def _pct(share: float | None) -> str:
    if share is None:
        return "—"
    if 0 < share < 0.001:
        return "&lt;0.1%"
    return f"{share * 100:.1f}%"


def _date(ms: float) -> str:
    stamp = dt.datetime(1970, 1, 1) + dt.timedelta(milliseconds=ms)
    return stamp.strftime("%Y-%m-%d %H:%M") if stamp.hour or stamp.minute else stamp.strftime("%Y-%m-%d")


def _distance(value: float | None, threshold: float | None) -> str:
    if value is None:
        return "—"
    high = threshold is not None and value > threshold
    return f'<span class="bf-cmp__high">{value:.3f}</span>' if high else f"{value:.3f}"


# ── the charts ────────────────────────────────────────────────────────────────


def _svg(inner: str, label: str) -> str:
    return (
        f'<svg class="bf-cmp__svg" viewBox="0 0 {_W} {_H}" preserveAspectRatio="none" role="img" '
        f'aria-label="{_e(label)}">{inner}</svg>'
    )


def _histogram(column: Column, extra: str = "") -> str:
    """Each dataset's share of its values in each shared bin, as a filled step line."""
    shares = [
        [c / side.values for c in side.counts] if side is not None and side.values else None for side in column.sides
    ]
    top = max((s for row in shares if row for s in row), default=0.0)
    if not top:
        return ""
    bins = max(len(row) for row in shares if row)
    step = _W / bins
    height = _PLOT_BOTTOM - _PLOT_TOP
    paths = ""
    for k, row in enumerate(shares):
        if not row:
            continue
        points = [f"M0 {_PLOT_BOTTOM}"]
        for i, share in enumerate(row):
            y = _PLOT_BOTTOM - share / top * height
            points.append(f"L{i * step:.1f} {y:.1f}L{(i + 1) * step:.1f} {y:.1f}")
        points.append(f"L{_W} {_PLOT_BOTTOM}Z")
        paths += (
            f'<path d="{"".join(points)}" fill="{_color(k)}" fill-opacity="0.16" stroke="{_color(k)}" '
            f'stroke-width="1.5" vector-effect="non-scaling-stroke"/>'
        )
    axis = f'<line x1="0" y1="{_PLOT_BOTTOM}" x2="{_W}" y2="{_PLOT_BOTTOM}" class="bf-cmp__axis"/>'
    return _svg(paths + axis + extra, f"{column.name}: distributions overlaid")


def _bar_rows(column: Column) -> tuple[list[str], float]:
    """The values drawn as bars (the "other" bar aside), and the height of a row."""
    values = column.labels[:-1] if column.other else column.labels
    bar = 6.0 if len(column.sides) <= 3 else 4.0
    return values[:BARS], bar * len(column.sides) + 6


def _bars(column: Column, names: list[str], extra: str = "") -> str:
    """Grouped bars of the top values: each dataset's share of its values; the rest in one "other" bar."""
    values = column.labels[:-1] if column.other else column.labels
    drawn = values[:BARS]
    rows: list[tuple[str, bool, list[float | None], list[int | None]]] = []
    for i, label in enumerate(drawn):
        shares, counts = _bar_values(column, operator.itemgetter(i))
        rows.append((label, False, shares, counts))
    if len(column.labels) > len(drawn):
        n = len(drawn)
        shares, counts = _bar_values(column, lambda row: sum(row[n:]))
        rows.append(("other", True, shares, counts))
    if not rows:
        return ""
    datasets = len(column.sides)
    bar = 6.0 if datasets <= 3 else 4.0
    row_h = bar * datasets + 6
    height = row_h * len(rows)
    top = max((s for _, _, shares, _ in rows for s in shares if s is not None), default=0.0) or 1.0
    left, width = 104, _W - 108
    out = ""
    for r, (label, other, shares, counts) in enumerate(rows):
        y0 = r * row_h
        text = _short(label)
        cls = "bf-cmp__label bf-cmp__label--other" if other else "bf-cmp__label"
        out += f'<text x="{left - 6}" y="{y0 + row_h / 2 + 3:.1f}" text-anchor="end" class="{cls}">{_e(text)}</text>'
        for k, (share, count) in enumerate(zip(shares, counts, strict=True)):
            if share is None or count is None:
                continue
            w = share / top * width
            out += (
                f'<rect x="{left}" y="{y0 + 3 + k * bar:.1f}" width="{w:.1f}" height="{bar - 1:.1f}" '
                f'fill="{_color(k)}"><title>{_e(names[k])} · {_e(label)}: {_pct(share)} ({count:,})</title></rect>'
            )
    return (
        f'<svg class="bf-cmp__svg bf-cmp__svg--bars" viewBox="0 0 {_W} {height:.0f}" role="img" '
        f'aria-label="{_e(column.name)}: top values per dataset">{out}{extra}</svg>'
    )


def _bar_values(column: Column, pick: t.Callable[[list[int]], int]) -> tuple[list[float | None], list[int | None]]:
    shares: list[float | None] = []
    counts: list[int | None] = []
    for side in column.sides:
        if side is None or not side.values:
            shares.append(None)
            counts.append(None)
        else:
            n = pick(side.counts)
            shares.append(n / side.values)
            counts.append(n)
    return shares, counts


def _curves(column: Column) -> str:
    """How much of each dataset's values its top *k* values cover, against *k*."""
    longest = max((side.curve[-1][0] for side in column.sides if side is not None and side.curve), default=0)
    if not longest:
        return ""
    height = _PLOT_BOTTOM - _PLOT_TOP
    lines = ""
    for k, side in enumerate(column.sides):
        if side is None or not side.curve:
            continue
        points = " ".join(
            f"{(rank - 1) / max(1, longest - 1) * _W:.1f},{_PLOT_BOTTOM - share * height:.1f}"
            for rank, share in side.curve
        )
        lines += (
            f'<polyline points="{points}" fill="none" stroke="{_color(k)}" stroke-width="1.5" '
            f'vector-effect="non-scaling-stroke"/>'
        )
    axis = f'<line x1="0" y1="{_PLOT_BOTTOM}" x2="{_W}" y2="{_PLOT_BOTTOM}" class="bf-cmp__axis"/>'
    return _svg(lines + axis, f"{column.name}: share of the values the most frequent ones cover")


def _selection(column: Column, targets: Targets | None) -> tuple[str, str]:
    """The chart's attributes and its bar targets, when its bars select rows in a DataDive (#21).

    A cumulative curve and the "other" bar select nothing: they stand for many values.
    """
    from briefing.lab._render_datadive import _text
    from briefing.lab._select import bins_test, chart_attrs, hits

    if targets is None:
        return "", ""
    dive = " or ".join(targets.names)
    if column.kind == "categorical":
        if any(side is not None and side.curve for side in column.sides) or not column.labels:
            return "", ""
        attrs, on = chart_attrs(targets, column.name, "categorical", {"kind": "values"})
        drawn, row_h = _bar_rows(column)
        boxes = [(0.0, r * row_h, float(_W), row_h, _text(label), _text(label)) for r, label in enumerate(drawn)]
        return attrs, hits(column.name, boxes, dive) if on else ""
    if column.binning is None:
        return "", ""
    low, high, scale = column.binning
    bins = len(column.edges) - 1
    unit = 1_000_000 if column.kind == "datetime" else 1  # the DataDive holds dates in milliseconds
    attrs, on = chart_attrs(targets, column.name, column.kind, bins_test(low, high, scale, bins, unit))
    if not on:
        return attrs, ""
    show = _date if column.kind == "datetime" else _fmt_num
    step = _W / bins
    boxes = [(i * step, 0.0, step, float(_H), str(i),
              f"{show(column.edges[i])}–{show(column.edges[i + 1])}" if bins > 1 else str(show(column.edges[0])))
             for i in range(bins)]
    return attrs, hits(column.name, boxes, dive)


def _chart(column: Column, names: list[str], targets: Targets | None = None) -> tuple[str, str, str]:
    """The chart of *column*, the line under it that reads its axis, and the chart's attributes."""
    attrs, extra = _selection(column, targets)
    if column.kind == "categorical":
        if any(side is not None and side.curve for side in column.sides):
            distinct = max(side.stats.get("distinct", 0) for side in column.sides if side is not None)
            curve = f"<span>1</span><span>top values, cumulative</span><span>{distinct:,}</span>"
            return _curves(column), curve, attrs
        return _bars(column, names, extra), "", attrs
    if not column.edges:
        return "", "", ""
    low, high = column.edges[0], column.edges[-1]
    show = _date if column.kind == "datetime" else _fmt_num
    return _histogram(column, extra), f"<span>{_e(show(low))}</span><span>{_e(show(high))}</span>", attrs


# ── the statistics ────────────────────────────────────────────────────────────


def _headers(kind: str) -> list[str]:
    if kind == "numeric":
        return ["count", "missing", "zeros", "mean", "std", "min", "median", "max"]
    if kind == "datetime":
        return ["count", "missing", "first", "last"]
    return ["count", "missing", "distinct", "top", "top share"]


def _cells(side: Side, kind: str, block: DataCompare) -> list[str]:
    missing = side.missing / side.rows if side.rows else None
    high = missing is not None and missing > block.missing_threshold
    cells = [f"{side.rows:,}", _flag(f"{_pct(missing)} ({side.missing:,})", high)]
    stats = side.stats
    if kind == "numeric":
        zeros = (side.zeros or 0) / side.rows if side.rows else None
        cells.append(_flag(f"{_pct(zeros)} ({side.zeros or 0:,})", zeros is not None and zeros > block.zero_threshold))
        cells += [
            _e(_fmt_num(stats[k])) if stats.get(k) is not None else "—" for k in ("mean", "std", "min", "median", "max")
        ]
    elif kind == "datetime":
        cells += [_e(_date(stats[k])) if k in stats else "—" for k in ("first", "last")]
    else:
        top = str(stats["top"]) if "top" in stats else None
        cells += [
            f"{stats.get('distinct', 0):,}",
            f'<span title="{_e(top)}">{_e(_short(top))}</span>' if top else "—",
            _pct(stats.get("top_share")),
        ]
    return cells


def _short(text: str) -> str:
    return text if len(text) <= LABEL else text[: LABEL - 1] + "…"


def _flag(text: str, high: bool) -> str:
    return f'<span class="bf-cmp__high">{text}</span>' if high else text


def _table(column: Column, names: list[str], block: DataCompare) -> str:
    headers = _headers(column.kind)
    head = "".join(f"<th>{h}</th>" for h in ["dataset", *headers, "distance"])
    body = ""
    for k, side in enumerate(column.sides):
        swatch = f'<span class="bf-cmp__swatch" style="background:{_color(k)}"></span>'
        name = f'<th scope="row">{swatch}{_e(names[k])}</th>'
        if side is None:
            body += f'<tr class="bf-cmp__absent">{name}<td colspan="{len(headers) + 1}">not in this dataset</td></tr>'
            continue
        distance = "reference" if k == 0 else _distance(side.distance, block.threshold)
        cells = "".join(f"<td>{c}</td>" for c in [*_cells(side, column.kind, block), distance])
        body += f"<tr>{name}{cells}</tr>"
    return f'<div class="bf-cmp__table"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


def _badges(column: Column, names: list[str], block: DataCompare) -> str:
    out = ""
    present = column.present
    if not all(present):
        having = [names[k] for k, here in enumerate(present) if here]
        out += f'<span class="bf-cmp__badge bf-cmp__badge--only">only in {_e(", ".join(having))}</span>'
    if column.type_differs:
        types = " · ".join(side.dtype for side in column.sides if side is not None)
        out += f'<span class="bf-cmp__badge bf-cmp__badge--type" title="{_e(types)}">type differs</span>'
    distance = column.largest("distance")
    if block.threshold is not None and distance is not None and distance > block.threshold:
        out += f'<span class="bf-cmp__badge bf-cmp__badge--drift">drifted · {distance:.2f}</span>'
    return out


def _key(value: float | None) -> str:
    return "" if value is None else f"{value:.6g}"


def _payload(column: Column) -> dict[str, t.Any]:
    """What compare.js needs to redraw *column*'s chart."""
    sides: list[dict[str, t.Any] | None] = []
    for side in column.sides:
        if side is None:
            sides.append(None)
            continue
        sides.append({"n": side.values, "counts": side.counts, "deciles": side.deciles,
                      "curve": [list(point) for point in side.curve] if side.curve else None})
    payload: dict[str, t.Any] = {"kind": column.kind, "sides": sides}
    if column.edges:
        payload["range"] = [column.edges[0], column.edges[-1]]
    if column.labels:
        payload["labels"] = column.labels
        payload["other"] = column.other
    return payload


_SORT_NAMES = {"name": "Name", "missing": "Missing values", "zeros": "Zeros", "non_uniformity": "Non-uniformity",
               "distance": "Distance"}
_KIND_PLURALS = {"numeric": "numbers", "categorical": "categories", "datetime": "dates"}


def _controls(block: DataCompare) -> str:
    """The controls compare.js runs; hidden until it does."""
    options = "".join(
        f'<option value="{key}"{" selected" if key == block.sort else ""}>{label}</option>'
        for key, label in _SORT_NAMES.items()
    )
    kinds = [k for k in ("numeric", "categorical", "datetime") if any(c.kind == k for c in block.compared)]
    boxes = "".join(
        f'<label class="bf-cmp__check"><input type="checkbox" class="bf-cmp__kind-filter" value="{k}" checked> '
        f"{_KIND_PLURALS[k]}</label>"
        for k in kinds
    )
    deciles = (
        '<label class="bf-cmp__check"><input type="checkbox" class="bf-cmp__deciles"> deciles</label>'
        if "numeric" in kinds else ""
    )
    return (
        '<div class="bf-cmp__controls" hidden>'
        f'<label class="bf-cmp__ctrl">Sort by <select class="bf-cmp__sort">{options}</select></label>'
        '<input type="search" class="bf-cmp__search" placeholder="Search columns" aria-label="Search columns">'
        f'<span class="bf-cmp__group" role="group" aria-label="Column types">{boxes}</span>'
        '<span class="bf-cmp__group bf-cmp__units" role="group" aria-label="Values as">'
        '<button type="button" class="bf-cmp__unit" data-unit="share" aria-pressed="true">%</button>'
        '<button type="button" class="bf-cmp__unit" data-unit="count" aria-pressed="false">counts</button></span>'
        '<label class="bf-cmp__check"><input type="checkbox" class="bf-cmp__log"> log scale</label>'
        f"{deciles}"
        '<span class="bf-cmp__shown" aria-live="polite"></span>'
        "</div>"
    )


def _row(column: Column, names: list[str], block: DataCompare, index: int, targets: Targets | None) -> str:
    chart, axis, attrs = _chart(column, names, targets)
    keys = " ".join(
        f'data-{attr}="{_key(column.largest(what))}"'
        for attr, what in (("missing", "missing"), ("zeros", "zeros"), ("non-uniformity", "nonuniformity"),
                           ("distance", "distance"))
    )
    chart_html = (
        f'<div class="bf-cmp__chart"{attrs}>{chart}<div class="bf-cmp__ticks">{axis}</div></div>' if chart else ""
    )
    return (
        f'<section class="bf-cmp__row" data-i="{index}" data-name="{_e(column.name)}" data-kind="{column.kind}" {keys}>'
        f'<div class="bf-cmp__head"><span class="bf-cmp__name">{_e(column.name)}</span>'
        f'<span class="bf-cmp__kind">{_KIND_NAMES[column.kind]}</span>{_badges(column, names, block)}</div>'
        f'<div class="bf-cmp__body">{_table(column, names, block)}{chart_html}</div>'
        "</section>"
    )


def _sorted(columns: list[Column], sort: str) -> list[Column]:
    if sort == "name":
        return sorted(columns, key=lambda c: (c.name.casefold(), c.name))
    what = {"non_uniformity": "nonuniformity"}.get(sort, sort)

    def key(column: Column) -> tuple[bool, float, str]:
        value = column.largest(what)
        return value is None, -(value or 0.0), column.name.casefold()

    return sorted(columns, key=key)


# ── public entry ──────────────────────────────────────────────────────────────


def render_compare(block: DataCompare, idgen: IdGen | None = None) -> str:
    """Render a :class:`~briefing.lab.DataCompare` block: a legend, then one row per column."""
    from briefing.lab._select import Targets, check_selects, sender_attrs

    selects = check_selects(block.selects, "DataCompare")
    targets = Targets(block, selects, idgen) if selects and idgen is not None else None
    names = list(block.datasets)
    legend = "".join(
        f'<span class="bf-cmp__dataset"><span class="bf-cmp__swatch" style="background:{_color(k)}"></span>'
        f"{_e(name)} <small>{len(frame):,} rows</small></span>"
        for k, (name, frame) in enumerate(block.datasets.items())
    )
    threshold = f", drifted above {block.threshold:g}" if block.threshold is not None else ""
    note = f'<span class="bf-cmp__measure">Distance from {_e(names[0])}: {_e(block.measure_title)}{threshold}</span>'
    order = {id(column): i for i, column in enumerate(block.compared)}
    rows = "".join(_row(column, names, block, order[id(column)], targets)
                   for column in _sorted(block.compared, block.sort))
    data = script_json({"names": names, "columns": [_payload(c) for c in block.compared]})
    if not rows:
        rows = '<p class="bf-cmp__empty">No columns to compare.</p>'
    return (
        f'<div class="bf-block bf-compare" data-sort="{block.sort}"{sender_attrs(targets, "comparison", block)}>'
        f'<div class="bf-cmp__legend">{legend}{note}</div>'
        f"{_controls(block) if block.compared else ''}"
        f'<div class="bf-cmp__rows">{rows}</div>'
        f'<script type="application/json" class="bf-cmp__data">{data}</script>'
        "</div>"
    )


__all__ = ["render_compare"]
