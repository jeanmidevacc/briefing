"""DataDive block rendering — interactive dot explorer, fully self-contained.

Architecture
------------
- All data is serialised as a JSON array embedded in the HTML via a
  ``<script type="application/json">`` tag so that the JS can parse it.
- A second JSON tag carries column-type metadata (numeric vs categorical vs
  datetime) so that the JS can choose the correct scale for each axis.
- Dropdown controls let the user reassign X, Y, and Color channels.
- The SVG is re-drawn in vanilla JS on every dropdown change.
- Tooltip is an absolutely-positioned ``<div>`` shown on dot hover.

No Vega, no D3, no CDN — works forever in a standalone HTML file.
"""
from __future__ import annotations

import html as _html
import json
import typing as t

if t.TYPE_CHECKING:
    from briefing.lab._blocks import DataDive


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


def _serialise(df: t.Any) -> str:
    """Serialise DataFrame to a compact JSON array, NaN→null, datetimes→ISO."""
    import pandas as pd

    # Convert to object dtype for JSON friendliness, convert datetimes to iso strings
    out = df.copy()
    for col in out.columns:
        if pd.api.types.is_datetime64_any_dtype(out[col]):
            out[col] = out[col].dt.strftime("%Y-%m-%d %H:%M")
        # Truncate long strings to avoid huge payloads
        if out[col].dtype == object or pd.api.types.is_string_dtype(out[col]):
            out[col] = out[col].apply(lambda v: str(v)[:64] if isinstance(v, str) else v)

    return str(out.to_json(orient="records", date_format="iso", default_handler=str))


# ── public entry ──────────────────────────────────────────────────────────────


def render_datadive(block: DataDive) -> str:
    """Render a :class:`~briefing.DataDive` block to a self-contained interactive SVG explorer."""
    df = block.df
    cols = list(df.columns)
    if not cols:
        return '<div class="bf-block bf-placeholder">⚠ DataDive: no columns to display.</div>'

    # Column metadata for the JS scale engine
    meta = {col: _col_kind(df[col]) for col in cols}

    # Default selections
    x_def, y_def, color_def = _pick_defaults(df, block.x, block.y, block.color)

    # Build dropdown <option> lists
    def _options(selected: str) -> str:
        out = '<option value="">— none —</option>' if selected == "" else ""
        for col in cols:
            sel = ' selected' if col == selected else ''
            out += f'<option value="{_html.escape(col)}"{sel}>{_html.escape(col)}</option>'
        return out

    def _options_required(selected: str) -> str:
        return "".join(
            f'<option value="{_html.escape(col)}"'
            f'{" selected" if col == selected else ""}>{_html.escape(col)}</option>'
            for col in cols
        )

    def _control(axis: str, label: str, option_html: str) -> str:
        return (
            f'<label class="bf-dd__ctrl">{label}'
            f'<select class="bf-dd__sel" data-axis="{axis}">{option_html}</select>'
            f"</label>"
        )

    layout = block.layout  # "scatter" or "tile"
    none_option = '<option value="">— none —</option>'

    # In tile mode, Y is optional (group by X only) and gets a "— none —" entry.
    if layout == "scatter":
        y_label, x_label = "Y", "X"
        y_option_html = _options_required(y_def)
    else:
        y_label, x_label = "Row", "Column"
        y_option_html = none_option + _options(y_def)

    controls = (
        '<div class="bf-dd__controls">'
        + _control("x", x_label, _options_required(x_def))
        + _control("y", y_label, y_option_html)
        + _control("color", "Color", none_option + _options(color_def))
        + "</div>"
    )

    data_json = _serialise(df)
    meta_json = json.dumps(meta)
    n_rows = len(df)
    vb = "0 0 620 400" if layout == "scatter" else "0 0 820 500"
    aria = f"DataDive {layout} plot"

    return (
        f'<div class="bf-block bf-datadive" data-layout="{layout}">'
        f"{controls}"
        f'<div class="bf-dd__plot-area">'
        f'<svg class="bf-dd__plot" viewBox="{vb}" aria-label="{aria}"></svg>'
        f'<div class="bf-dd__tooltip" hidden></div>'
        f"</div>"
        f'<div class="bf-dd__footer">{n_rows:,} rows</div>'
        f'<script type="application/json" class="bf-dd__data">{data_json}</script>'
        f'<script type="application/json" class="bf-dd__meta">{meta_json}</script>'
        f"</div>"
    )


__all__ = ["render_datadive"]
