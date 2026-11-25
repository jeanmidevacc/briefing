"""DataDive block rendering: an interactive dot explorer, drawn on a canvas (#16).

Architecture
------------
- The data travels by column, not by row: numbers as numbers, dates as epoch
  milliseconds, everything else as categories (a list of levels and one code per
  row). It is JSON, packed by ``renderers/pack.py`` in a ``script.bf-dd__data``
  that ``unpack.js`` opens as the page loads (#38).
- ``lab.js`` draws the dots on a ``<canvas>`` and the axes, ticks and labels in
  an SVG on top of it, and redraws when a dropdown or the block's width changes.
- The legend under the controls colours the dots and filters them: a click
  hides or shows a category.
- A ``bf.Scale`` passed as ``colors=`` travels as a ramp of colours (or the
  colour of each category) with its domain and centre, so the page places a
  value on it as ``Scale.position`` does.

No Vega, no D3, no CDN: it works forever in a standalone HTML file.
"""
from __future__ import annotations

import html as _html
import json
import math
import typing as t

from briefing import color as _color
from briefing.renderers.pack import pack
from briefing.renderers.script_json import script_json
from briefing.scale import Scale

if t.TYPE_CHECKING:
    from briefing.lab._blocks import DataDive

#: Colours sampled along a numeric Scale for the page: enough that neighbours look the same.
RAMP = 64

#: Text values longer than this are cut, with an ellipsis, to keep the file light.
MAX_TEXT = 200


# ── column classification ─────────────────────────────────────────────────────


def _col_kind(series: t.Any) -> str:
    import pandas as pd

    if pd.api.types.is_bool_dtype(series):
        return "categorical"
    if pd.api.types.is_numeric_dtype(series):
        return "numeric"
    if pd.api.types.is_datetime64_any_dtype(series):
        return "datetime"
    return "categorical"


# ── default axis selection ────────────────────────────────────────────────────


def _pick_defaults(
    df: t.Any, x_hint: str | None, y_hint: str | None, color_hint: str | None
) -> tuple[str, str, str]:
    import pandas as pd

    def _is_number(col: t.Any) -> bool:
        s = df[col]
        return pd.api.types.is_numeric_dtype(s) and not pd.api.types.is_bool_dtype(s)

    numeric_cols = [c for c in df.columns if _is_number(c)]
    other_cols = [c for c in df.columns if c not in numeric_cols]
    all_cols = list(df.columns)

    x = x_hint or (numeric_cols[0] if len(numeric_cols) >= 1 else (all_cols[0] if all_cols else ""))
    y = y_hint or (numeric_cols[1] if len(numeric_cols) >= 2 else (all_cols[1] if len(all_cols) >= 2 else x))
    color = color_hint or (other_cols[0] if other_cols else (numeric_cols[2] if len(numeric_cols) >= 3 else ""))
    return x, y, color


# ── data serialisation ────────────────────────────────────────────────────────


def _text(value: t.Any) -> str:
    text = str(value)
    return text if len(text) <= MAX_TEXT else text[: MAX_TEXT - 1] + "…"


def _encode(name: str, series: t.Any) -> dict[str, t.Any]:
    """One column for the page: ``{"name", "kind", "values"}``, or levels and codes for categories."""
    import pandas as pd

    kind = _col_kind(series)
    if kind == "numeric":  # JSON has no NaN or infinity: both are missing, as before (#16)
        values = [None if pd.isna(v) or math.isinf(v) else (int(v) if float(v).is_integer() and abs(v) < 2**53
                  else float(v)) for v in series.tolist()]
        return {"name": name, "kind": kind, "values": values}
    if kind == "datetime":
        stamps = series.dt.tz_convert("UTC").dt.tz_localize(None) if series.dt.tz is not None else series
        ms = stamps.astype("datetime64[ms]").astype("int64").tolist()
        return {"name": name, "kind": kind, "values": [None if missing else v for v, missing in
                                                        zip(ms, series.isna().tolist(), strict=True)]}
    codes, levels = pd.factorize(series, use_na_sentinel=True)
    return {"name": name, "kind": "categorical", "levels": [_text(v) for v in levels.tolist()],
            "codes": codes.tolist()}


def _serialise(df: t.Any) -> str:
    """The columns of *df* as compact JSON: NaN becomes null, a date its epoch milliseconds."""
    return json.dumps({"rows": len(df), "columns": [_encode(str(name), df[name]) for name in df.columns]},
                      ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def _scale(colors: Scale | None) -> dict[str, t.Any] | None:
    """What the page needs to colour with *colors*: a category's colour, or a ramp and its domain."""
    if colors is None:
        return None
    if colors.categorical:
        return {"categories": colors.mapping}
    if colors.steps is not None:
        ramp = [_color.along(colors.colors, k / (colors.steps - 1)) for k in range(colors.steps)]
    else:
        ramp = [_color.along(colors.colors, k / (RAMP - 1)) for k in range(RAMP)]
    return {"ramp": ramp, "domain": list(colors.domain) if colors.domain is not None else None,
            "center": colors.center}


# ── public entry ──────────────────────────────────────────────────────────────


def render_datadive(block: DataDive) -> str:
    """Render a :class:`~briefing.lab.DataDive` block to a self-contained interactive explorer."""
    df = block.df
    cols = [str(c) for c in df.columns]
    if not cols:
        return '<div class="bf-block bf-placeholder">⚠ DataDive: no columns to display.</div>'

    x_def, y_def, color_def = _pick_defaults(df, block.x, block.y, block.color)

    def _options(selected: str, none: bool) -> str:
        out = '<option value="">— none —</option>' if none else ""
        for col in cols:
            sel = " selected" if col == selected else ""
            out += f'<option value="{_html.escape(col)}"{sel}>{_html.escape(col)}</option>'
        return out

    def _control(axis: str, label: str, option_html: str) -> str:
        return (
            f'<label class="bf-dd__ctrl">{label}'
            f'<select class="bf-dd__sel" data-axis="{axis}">{option_html}</select>'
            f"</label>"
        )

    layout = block.layout  # "scatter" or "tile"
    if layout == "scatter":
        x_label, y_label, y_options = "X", "Y", _options(y_def, False)
    else:  # in tile mode, Y is optional: group by X only
        x_label, y_label, y_options = "Column", "Row", _options(y_def, True)
    controls = (
        '<div class="bf-dd__controls">'
        + _control("x", x_label, _options(x_def, False))
        + _control("y", y_label, y_options)
        + _control("color", "Color", _options(color_def, True))
        + "</div>"
    )

    packed, size = pack(_serialise(df), level=6)  # megabytes at 100,000 rows: 9 would take seconds
    scale = _scale(block.colors)
    scale_html = (
        "" if scale is None else
        f'<script type="application/json" class="bf-dd__scale">{script_json(scale)}</script>'
    )
    rows = len(df)
    return (
        f'<div class="bf-block bf-datadive" data-layout="{layout}">'
        f"{controls}"
        '<div class="bf-dd__legend" aria-label="Legend: click a category to hide or show its dots"></div>'
        '<div class="bf-dd__plot-area">'
        f'<canvas class="bf-dd__canvas" role="img" aria-label="DataDive {layout} plot of {rows:,} rows"></canvas>'
        '<svg class="bf-dd__axes" aria-hidden="true"></svg>'
        '<div class="bf-dd__tooltip" hidden></div>'
        "</div>"
        f'<div class="bf-dd__footer">{rows:,} rows</div>'
        f'<script type="application/json" class="bf-dd__data" data-size="{size}">"{packed}"</script>'
        f"{scale_html}"
        "</div>"
    )


__all__ = ["render_datadive"]
