"""DataProfile block rendering — per-column stats with inline SVG mini-charts.

Architecture
------------
- :func:`render_profile` is the entry point — iterates columns, builds cards.
- :func:`_column_stats` extracts per-column statistics using only pandas.
- :func:`_histogram_svg` renders a numeric distribution as an SVG histogram.
- :func:`_bar_chart_svg` renders a categorical frequency chart as horizontal bars.
- No numpy or extra dependencies — all computations use pandas primitives.
"""
from __future__ import annotations

import html as _html
import math
import typing as t

if t.TYPE_CHECKING:
    from briefing.lab._blocks import DataProfile
    from briefing.lab._select import Targets
    from briefing.renderers.registry import IdGen

#: What draws the invisible bar targets of a linked selection (#21) into a chart, from its bins.
_Extra = t.Callable[[float, float, float, int], str]


# ── column type detection ─────────────────────────────────────────────────────


def _detect_kind(series: t.Any) -> str:
    """Return 'numeric', 'datetime', or 'categorical'."""
    import pandas as pd

    if pd.api.types.is_bool_dtype(series):
        return "categorical"
    if pd.api.types.is_numeric_dtype(series):
        return "numeric"
    if pd.api.types.is_datetime64_any_dtype(series) or pd.api.types.is_timedelta64_dtype(series):
        return "datetime"
    return "categorical"


# ── stat helpers ──────────────────────────────────────────────────────────────


def _fmt_num(v: t.Any, sig: int = 4) -> str:
    """Format a number to at most *sig* significant figures, stripped of trailing zeros."""
    try:
        import pandas as pd

        if pd.isna(v):
            return "—"
    except (TypeError, ValueError):
        pass
    if isinstance(v, float):
        if math.isinf(v):  # int(inf) raises OverflowError
            return "inf" if v > 0 else "-inf"
        if v == int(v) and abs(v) < 1e12:
            return str(int(v))
        # g-format respects significant figures
        return f"{v:.{sig}g}"
    return str(v)


def _pct(num: int, denom: int) -> str:
    if denom == 0:
        return "—"
    return f"{num / denom * 100:.1f}%"


# ── SVG mini-charts ───────────────────────────────────────────────────────────

_SVG_W = 200
_SVG_H = 52
_HIST_BINS = 20
_BAR_FILL = 'fill="var(--bf-accent)" fill-opacity="0.65"'


def _infinite(series: t.Any) -> t.Any:
    """Boolean mask of the ``inf`` / ``-inf`` values in a numeric Series."""
    return series.isin([math.inf, -math.inf])


def _histogram_svg(series: t.Any, extra: _Extra | None = None) -> str:
    """Return an SVG histogram for a numeric pandas Series (its finite values).

    *extra*, given the minimum, maximum, scale and number of bins, draws more on top: the
    targets of a linked selection (#21).
    """
    valid = series.dropna()
    valid = valid[~_infinite(valid)]  # an infinite range would put every value in bin 0
    n = len(valid)
    if n == 0:
        return f'<svg width="{_SVG_W}" height="{_SVG_H}"></svg>'

    mn, mx = float(valid.min()), float(valid.max())
    if mn == mx:
        # Degenerate: single value — draw one full-height bar
        bar = f'<rect x="0" y="0" width="{_SVG_W}" height="{_SVG_H}" fill="var(--bf-accent)" fill-opacity="0.65"/>'
        bar += extra(mn, mx, 1.0, 1) if extra else ""
        return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {_SVG_W} {_SVG_H}">{bar}</svg>'

    # Bucket counts without numpy. A range wider than the largest float (-1e308 … 1e308)
    # would overflow to inf, so such values are halved before subtracting.
    scale = 1.0 if math.isfinite(mx - mn) else 0.5
    low, span = mn * scale, mx * scale - mn * scale
    counts = [0] * _HIST_BINS
    for v in valid:
        idx = min(int((float(v) * scale - low) / span * _HIST_BINS), _HIST_BINS - 1)
        counts[idx] += 1

    max_count = max(counts)
    bar_w = _SVG_W / _HIST_BINS
    gap = max(0.5, bar_w * 0.08)
    bars = ""
    for i, c in enumerate(counts):
        h = (c / max_count) * _SVG_H if max_count else 0
        x = i * bar_w + gap / 2
        y = _SVG_H - h
        w = bar_w - gap
        bars += f'<rect x="{x:.2f}" y="{y:.2f}" width="{w:.2f}" height="{h:.2f}" {_BAR_FILL}/>'

    bars += extra(mn, mx, scale, _HIST_BINS) if extra else ""
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {_SVG_W} {_SVG_H}">{bars}</svg>'


def _bin_hits(column: str, dive: str) -> _Extra:
    """The targets over each bin of a histogram, labelled with its range (#21)."""
    from briefing.lab._select import hits

    def draw(low: float, high: float, scale: float, bins: int) -> str:
        width = _SVG_W / bins
        step = (high * scale - low * scale) / scale / bins
        boxes = [(i * width, 0.0, width, float(_SVG_H), str(i),
                  f"{_fmt_num(low + step * i)}–{_fmt_num(high if i == bins - 1 else low + step * (i + 1))}"
                  if bins > 1 else _fmt_num(low)) for i in range(bins)]
        return hits(column, boxes, dive)

    return draw


def _bar_chart_svg(top_values: list[tuple[str, int]], extra: str = "") -> str:
    """Return an SVG horizontal bar chart for top categorical values."""
    if not top_values:
        return f'<svg width="{_SVG_W}" height="{_SVG_H}"></svg>'

    n = len(top_values)
    max_count = max(c for _, c in top_values)
    row_h = _SVG_H / n
    gap = max(0.5, row_h * 0.15)
    # No text labels in the SVG — the stats list / tooltip carry the names.

    bars = ""
    for i, (_, count) in enumerate(top_values):
        bw = (count / max_count) * (_SVG_W - 2) if max_count else 0
        y = i * row_h + gap / 2
        h = row_h - gap
        bars += f'<rect x="1" y="{y:.2f}" width="{bw:.2f}" height="{h:.2f}" {_BAR_FILL}/>'

    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {_SVG_W} {_SVG_H}">{bars}{extra}</svg>'


def _datetime_range_svg(series: t.Any) -> str:
    """Return a simple timeline showing valid date coverage."""
    valid = series.dropna()
    if len(valid) < 2:
        return f'<svg width="{_SVG_W}" height="{_SVG_H}"></svg>'

    # Normalise timestamps to [0, SVG_W]
    ts = sorted(valid.astype("int64").tolist())
    t_min, t_max = ts[0], ts[-1]
    rng = t_max - t_min or 1
    r = _SVG_H // 2

    # Draw dots sampled to max 100 points
    step = max(1, len(ts) // 100)
    dots = ""
    for t_val in ts[::step]:
        cx = 1 + (t_val - t_min) / rng * (_SVG_W - 2)
        dots += f'<circle cx="{cx:.1f}" cy="{r}" r="1.5" fill="var(--bf-accent)" fill-opacity="0.5"/>'

    # Baseline
    baseline = f'<line x1="1" y1="{r}" x2="{_SVG_W - 1}" y2="{r}" stroke="var(--bf-border)" stroke-width="1"/>'
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {_SVG_W} {_SVG_H}">{baseline}{dots}</svg>'


# ── per-column card ───────────────────────────────────────────────────────────


def _column_card(
    col: str,
    series: t.Any,
    missing_threshold: float,
    max_categories: int,
    targets: Targets | None = None,
) -> str:
    total = len(series)
    missing = int(series.isna().sum())
    missing_pct = missing / total if total > 0 else 0.0
    kind = _detect_kind(series)
    dtype_str = _html.escape(str(series.dtype))

    # ── missing stat row
    miss_cls = " bf-profile__missing--high" if missing_pct > missing_threshold else ""
    miss_val = f"{_pct(missing, total)} ({missing:,})"

    stat_rows = [
        ("count", f"{total:,}"),
        ("missing", f'<span class="bf-profile__stat-val{miss_cls}">{_html.escape(miss_val)}</span>'),
    ]

    chart_svg = ""

    if kind == "numeric":
        unique = int(series.nunique(dropna=True))
        desc = series.describe()
        stat_rows += [
            ("unique", f"{unique:,}"),
            ("mean", _fmt_num(desc["mean"])),
            ("std", _fmt_num(desc["std"])),
            ("min", _fmt_num(desc["min"])),
            ("median", _fmt_num(desc["50%"])),
            ("max", _fmt_num(desc["max"])),
        ]
        infinite = int(_infinite(series).sum())
        if infinite:
            stat_rows.append(("infinite", f"{infinite:,}"))
        chart_attrs, extra = _selectable_bins(targets, col, series)
        chart_svg = _histogram_svg(series, extra)

    elif kind == "categorical":
        unique = int(series.nunique(dropna=True))
        vc = series.value_counts(dropna=True).head(max_categories)
        top = [(str(k), int(v)) for k, v in zip(vc.index, vc.values, strict=True)]
        stat_rows += [("unique", f"{unique:,}")]
        # Top values listed compactly
        top_str = ", ".join(f"{_html.escape(label)} ({cnt:,})" for label, cnt in top[:5])
        if top_str:
            stat_rows.append(("top", top_str))
        chart_attrs, hits_svg = _selectable_values(targets, col, top)
        chart_svg = _bar_chart_svg(top, hits_svg)

    else:  # datetime
        chart_attrs = ""
        valid = series.dropna()
        stat_rows += [
            ("min", _html.escape(str(valid.min()) if len(valid) else "—")),
            ("max", _html.escape(str(valid.max()) if len(valid) else "—")),
        ]
        chart_svg = _datetime_range_svg(series)

    # ── build stat list HTML
    dl_inner = ""
    for key, val_html in stat_rows:
        dl_inner += (
            f'<div class="bf-profile__stat-row">'
            f'<dt>{_html.escape(key)}</dt>'
            f'<dd>{val_html}</dd>'
            f"</div>"
        )

    chart_html = f'<div class="bf-profile__chart"{chart_attrs}>{chart_svg}</div>' if chart_svg else ""

    return (
        f'<div class="bf-profile__card">'
        f'<div class="bf-profile__col-name" title="{_html.escape(col)}">{_html.escape(col)}</div>'
        f'<span class="bf-profile__dtype">{dtype_str}</span>'
        f'<dl class="bf-profile__stats">{dl_inner}</dl>'
        f"{chart_html}"
        f"</div>"
    )


# ── linked selection (#21) ────────────────────────────────────────────────────


def _selectable_bins(targets: Targets | None, col: str, series: t.Any) -> tuple[str, _Extra | None]:
    """A histogram's attributes and its bar targets, when its bars select rows."""
    from briefing.lab._select import bins_test, chart_attrs

    valid = series.dropna()
    valid = valid[~_infinite(valid)]
    if targets is None or not len(valid):
        return "", None
    low, high = float(valid.min()), float(valid.max())
    scale = 1.0 if math.isfinite(high - low) else 0.5
    attrs, on = chart_attrs(targets, str(col), "numeric",
                            bins_test(low, high, scale if low != high else 1.0, _HIST_BINS if low != high else 1))
    return attrs, _bin_hits(str(col), " or ".join(targets.names)) if on else None


def _selectable_values(targets: Targets | None, col: str, top: list[tuple[str, int]]) -> tuple[str, str]:
    """A bar chart's attributes and its bar targets, when its bars select rows."""
    from briefing.lab._render_datadive import _text
    from briefing.lab._select import chart_attrs, hits

    if targets is None or not top:
        return "", ""
    attrs, on = chart_attrs(targets, str(col), "categorical", {"kind": "values"})
    if not on:
        return attrs, ""
    row = _SVG_H / len(top)
    boxes = [(0.0, i * row, float(_SVG_W), row, _text(label), _text(label)) for i, (label, _) in enumerate(top)]
    return attrs, hits(str(col), boxes, " or ".join(targets.names))


# ── public entry ──────────────────────────────────────────────────────────────


def render_profile(block: DataProfile, idgen: IdGen | None = None) -> str:
    """Render a :class:`~briefing.DataProfile` block to an HTML grid of column cards."""
    from briefing.lab._select import Targets, check_selects, sender_attrs

    names = check_selects(block.selects, "DataProfile")
    targets = Targets(block, names, idgen) if names and idgen is not None else None
    df = block.df
    cards = "".join(
        _column_card(col, df[col], block.missing_threshold, block.max_categories, targets)
        for col in df.columns
    )
    return f'<div class="bf-block bf-profile"{sender_attrs(targets, "profile", block)}>{cards}</div>'


__all__ = ["render_profile"]
