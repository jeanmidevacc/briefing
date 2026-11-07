"""Table block rendering — static Table and interactive DataTable.

Table
-----
Renders a pandas DataFrame or Styler as a styled static HTML table.
If the user passes a Styler, its inline CSS is preserved verbatim;
otherwise a plain ``<table>`` is emitted with briefing's own table CSS.

DataTable
---------
Renders a DataFrame as a fully self-contained interactive table with:
- Live search / filter (all columns)
- Click-to-sort columns, by value: each cell carries a ``data-sort`` key for
  numbers, dates and durations (see :func:`_sort_key`); text sorts as text
- Client-side pagination (25 rows per page)

All interaction is handled by vanilla JS in ``report.js``; the rendered
HTML contains the full data set, so the table works offline forever.
"""
from __future__ import annotations

import copy
import html as _html
import math
import numbers
import typing as t
from datetime import date, timedelta

from briefing._error import BriefingError
from briefing.renderers.registry import IdGen

if t.TYPE_CHECKING:
    from briefing.blocks.asset import DataTable, Table


# ── helpers ───────────────────────────────────────────────────────────────────


def _fmt(val: t.Any) -> str:
    """Format a single cell value to a display string."""
    try:
        import pandas as pd

        if pd.isna(val):
            return ""
    except (TypeError, ValueError, ImportError):
        pass
    if isinstance(val, float):
        if math.isinf(val):  # int(inf) raises OverflowError
            return "inf" if val > 0 else "-inf"
        if val == int(val) and abs(val) < 1e15:
            return str(int(val))
        return f"{val:g}"
    return str(val)


def _sort_key(val: t.Any) -> str | None:
    """Return the ``data-sort`` key for a cell, or ``None`` to sort it by its text.

    Numbers give their full-precision value, dates their ISO form (which sorts
    chronologically as text), durations their length in seconds. Missing values
    give ``""``, which the browser always sorts last. :func:`_cell` leaves the key
    out when it equals the displayed text, since the browser falls back to that.
    """
    if _fmt(val) == "" and not isinstance(val, str):
        return ""
    if isinstance(val, bool) or type(val).__name__ == "bool_":
        return None
    if isinstance(val, numbers.Integral):
        return str(int(val))
    if isinstance(val, numbers.Real):
        return _number_key(float(val))
    if isinstance(val, date):  # datetime and pandas.Timestamp are dates too
        return val.isoformat()
    if isinstance(val, timedelta):  # includes pandas.Timedelta
        return _number_key(val.total_seconds())
    return None


def _number_key(f: float) -> str:
    """A number as JavaScript's ``Number()`` reads it back exactly, in its shortest form."""
    if math.isinf(f):
        return "Infinity" if f > 0 else "-Infinity"
    return str(int(f)) if f.is_integer() and abs(f) < 2**53 else repr(f)


def _cell(val: t.Any) -> str:
    """One ``<td>``: escaped display text, plus its sort key when that differs from the text."""
    text = _fmt(val)
    key = _sort_key(val)
    sort_attr = "" if key is None or key == text else f' data-sort="{_html.escape(key)}"'
    return f"<td{sort_attr}>{_html.escape(text)}</td>"


def _use_index(df: t.Any) -> bool:
    """Return True if the DataFrame index should be rendered as a column."""
    import pandas as pd

    return not isinstance(df.index, pd.RangeIndex) or df.index.name is not None


# ── static Table ──────────────────────────────────────────────────────────────


def render_table(block: Table, idgen: IdGen | None = None) -> str:
    """Render a :class:`~briefing.Table` block to a static HTML table fragment."""
    try:
        from pandas.io.formats.style import Styler
    except ImportError as exc:
        raise BriefingError(
            "Table requires pandas — install it with:  pip install briefing[pandas]"
        ) from exc

    data = block.data

    if isinstance(data, Styler):
        # A full <style>+<table> fragment, used as it is apart from the id: pandas puts a random
        # uuid in every id and selector. The copy leaves the caller's Styler as it was.
        table_html = copy.copy(data).set_uuid((idgen or IdGen()).next("table")).to_html()
    else:
        table_html = data.to_html(
            classes="bf-table__table",
            border=0,
            index=_use_index(data),
        )

    caption_html = (
        f'<div class="bf-table__caption">{_html.escape(block.caption)}</div>'
        if block.caption
        else ""
    )
    return (
        f'<div class="bf-block bf-table">'
        f'<div class="bf-table__scroll">{table_html}</div>'
        f"{caption_html}"
        f"</div>"
    )


# ── interactive DataTable ─────────────────────────────────────────────────────


def render_datatable(block: DataTable) -> str:
    """Render a :class:`~briefing.DataTable` block to an interactive HTML table."""
    df = block.df
    show_index = _use_index(df)

    # ── header ──
    header_cells = ""
    col_idx = 0
    if show_index:
        idx_name = _html.escape(str(df.index.name or ""))
        header_cells += (
            f'<th class="bf-dt__th" data-col="{col_idx}" scope="col">'
            f"<span>{idx_name}</span>"
            f'<span class="bf-dt__sort-icon" aria-hidden="true"></span>'
            f"</th>"
        )
        col_idx += 1
    for col in df.columns:
        header_cells += (
            f'<th class="bf-dt__th" data-col="{col_idx}" scope="col">'
            f"<span>{_html.escape(str(col))}</span>"
            f'<span class="bf-dt__sort-icon" aria-hidden="true"></span>'
            f"</th>"
        )
        col_idx += 1

    # ── rows ──
    rows_html = ""
    for idx_val, row in zip(df.index, df.itertuples(index=False), strict=True):
        cells = ""
        if show_index:
            cells += _cell(idx_val)
        for val in row:
            cells += _cell(val)
        rows_html += f"<tr>{cells}</tr>"

    caption_html = (
        f'<div class="bf-dt__caption">{_html.escape(block.caption)}</div>'
        if block.caption
        else ""
    )
    return (
        f'<div class="bf-block bf-datatable">'
        f'<div class="bf-dt__toolbar">'
        f'<input class="bf-dt__search" type="search" placeholder="Search…" aria-label="Search table" />'
        f'<span class="bf-dt__count"></span>'
        f"</div>"
        f'<div class="bf-dt__scroll">'
        f'<table class="bf-dt__table">'
        f"<thead><tr>{header_cells}</tr></thead>"
        f"<tbody>{rows_html}</tbody>"
        f"</table>"
        f"</div>"
        f'<div class="bf-dt__footer">'
        f'<button class="bf-dt__page-btn" data-dir="-1">&#8592; Prev</button>'
        f'<span class="bf-dt__page-info"></span>'
        f'<button class="bf-dt__page-btn" data-dir="1">Next &#8594;</button>'
        f"</div>"
        f"{caption_html}"
        f"</div>"
    )


__all__ = ["render_datatable", "render_table"]
