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
import json
import math
import numbers
import re
import string
import typing as t
from dataclasses import dataclass
from datetime import date, timedelta

from briefing._error import BriefingError
from briefing.renderers.pack import pack
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


def _td(text: str, key: str | None, href: str | None) -> str:
    """A cell: its text (a link to *href*, #33), and its sort key when that differs from the text."""
    sort_attr = "" if key is None or key == text else f' data-sort="{_html.escape(key)}"'
    shown = _html.escape(text)
    if href is not None:
        shown = f'<a href="{_html.escape(href)}" target="_blank" rel="noopener noreferrer">{shown}</a>'
    return f"<td{sort_attr}>{shown}</td>"


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
        idgen = idgen or IdGen()
        uuid = idgen.next("table")
        table_html = copy.copy(data).set_uuid(uuid).to_html()
        if idgen.prefix:  # in a fragment (#122), every id and selector starts with its embed id
            table_html = table_html.replace(f"T_{uuid}", uuid)
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

    # ── rows: all of them, or above HTML_ROWS the first page, the rest as packed JSON (#38) ──
    big = from_json(block)
    columns = _columns(block, show_index)
    rows_html = "".join(
        "<tr>" + "".join(_td(c.texts[i], c.keys[i], c.hrefs[i] if c.hrefs else None) for c in columns) + "</tr>"
        for i in range(min(len(df), PAGE_ROWS) if big else len(df))
    )
    more_html = data_html = ""
    if big:
        more_html = (
            f'<noscript><p class="bf-dt__more">The first {PAGE_ROWS} of {len(df):,} rows: '
            "the others need JavaScript.</p></noscript>"
        )
        packed, size = pack(json.dumps(_payload(len(df), columns), ensure_ascii=False, separators=(",", ":")))
        data_html = f'<script type="application/json" class="bf-dt__data" data-size="{size}">"{packed}"</script>'

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
        f"{_csv_button(block)}"
        f"</div>"
        f'<div class="bf-dt__scroll">'
        f'<table class="bf-dt__table">'
        f"<thead><tr>{header_cells}</tr></thead>"
        f"<tbody>{rows_html}</tbody>"
        f"</table>"
        f"</div>"
        f"{more_html}"
        f'<div class="bf-dt__footer">'
        f'<button class="bf-dt__page-btn" data-dir="-1">&#8592; Prev</button>'
        f'<span class="bf-dt__page-info"></span>'
        f'<button class="bf-dt__page-btn" data-dir="1">Next &#8594;</button>'
        f"</div>"
        f"{caption_html}"
        f"{data_html}"
        f"</div>"
    )


def _csv_button(block: DataTable) -> str:
    """The "CSV" button of a table with ``download=True`` (#34), and where it says what it did."""
    if not block.download:
        return ""
    base = block.name or block.caption or "table"
    name = re.sub(r"[^A-Za-z0-9]+", "-", base).strip("-").lower()[:60] or "table"
    return (
        f'<button class="bf-dt__csv" type="button" data-bf-filename="{_html.escape(name)}.csv" '
        'title="Download the rows matching the search, in their order, as CSV">CSV</button>'
        '<span class="bf-dt__csv-note" aria-live="polite"></span>'
    )


_JS_NUMBER = re.compile(r"^[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?$|^[+-]?Infinity$")


def _csv_field(text: str) -> str:
    """One CSV field, as report.js's ``csvField`` writes it (#34)."""
    if re.match(r"[=+\-@\t\r]", text) and not _JS_NUMBER.match(text.strip()):
        text = "'" + text  # a spreadsheet would run it as a formula; a number such as -5 stays
    return '"' + text.replace('"', '""') + '"' if re.search(r'[",\r\n]', text) else text


def csv_text(df: t.Any) -> str:
    """*df* as the CSV a DataTable's button downloads (#34): raw values, UTF-8 with a BOM, CRLF."""
    show_index = _use_index(df)
    names = ([str(df.index.name or "")] if show_index else []) + [str(c) for c in df.columns]
    columns = ([df.index.tolist()] if show_index else []) + [df.iloc[:, j].tolist() for j in range(df.shape[1])]
    lines = [",".join(_csv_field(n.strip()) for n in names)]
    for i in range(len(df)):
        raw = [(_sort_key(c[i]) if _sort_key(c[i]) is not None else _fmt(c[i]).strip()) for c in columns]
        lines.append(",".join(_csv_field(str(v)) for v in raw))
    return "\ufeff" + "\r\n".join(lines) + "\r\n"


#: Rows a page of a DataTable shows (``PAGE_SIZE`` in report.js): what a big table keeps in its HTML.
PAGE_ROWS = 25


def from_json(block: DataTable) -> bool:
    """Whether *block* stores its rows as packed JSON (#38): above ``DataTable.HTML_ROWS`` rows."""
    return len(block.df) > block.HTML_ROWS


@dataclass
class _Column:
    """A column as the table shows it: each cell's text, sort key and link (``None``: none)."""

    texts: list[str]
    keys: list[str | None]
    hrefs: list[str | None] | None


def _missing(value: t.Any) -> bool:
    import pandas as pd

    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def _columns(block: DataTable, show_index: bool) -> list[_Column]:
    """Every column the table shows (its index first, when it shows one), with formats and links applied (#33)."""
    df = block.df
    formats, links = block.formats or {}, block.links or {}
    names = ([None] if show_index else []) + list(df.columns)
    values = ([df.index.tolist()] if show_index else []) + [df.iloc[:, j].tolist() for j in range(df.shape[1])]
    by_name = {str(name): column for name, column in zip(names, values, strict=True) if name is not None}
    columns = []
    for name, column in zip(names, values, strict=True):
        how = formats.get(name) if name is not None else None
        template = links.get(name) if name is not None else None
        texts = _formatted(how, name, column) if how is not None else [_fmt(v) for v in column]
        hrefs = _hrefs(template, name, column, by_name) if template is not None else None
        columns.append(_Column(texts, [_sort_key(v) for v in column], hrefs))
    return columns


def _formatted(how: t.Any, name: t.Any, column: list[t.Any]) -> list[str]:
    """Each value of *column* as its format shows it (#33); missing values stay empty, and values
    the format doesn't fit show as they are, with a warning naming the first of them."""
    texts: list[str] = []
    misfits: list[t.Any] = []
    for value in column:
        if _missing(value):
            texts.append("")
            continue
        try:
            texts.append(str(how(value)) if callable(how) else str(how.format(value)))
        except (ValueError, TypeError, KeyError, IndexError, AttributeError):
            misfits.append(value)
            texts.append(_fmt(value))
    if misfits:
        _warn(f"DataTable: the format {how!r} of column {name!r} doesn't fit {len(misfits)} of its values "
              f"(such as {misfits[0]!r}); they show as they are.")
    return texts


def _warn(message: str) -> None:
    import warnings

    warnings.warn(message, UserWarning, stacklevel=3)


_LINK_SCHEMES = re.compile(r"^(?:https?://|mailto:)", re.I)


def _hrefs(template: str, name: t.Any, column: list[t.Any], by_name: dict[str, list[t.Any]]) -> list[str | None]:
    """Each cell's link from *template*: ``{}`` is the cell, ``{other}`` that column in the row (#33)."""
    fields = [f for _, f, _, _ in string.Formatter().parse(template) if f not in (None, "", "0")]
    hrefs: list[str | None] = []
    refused = None
    for i, value in enumerate(column):
        row = {f: by_name[f][i] for f in fields}
        if _missing(value) or any(_missing(v) for v in row.values()):
            hrefs.append(None)
            continue
        url = template.format(value, **row).strip()
        if _LINK_SCHEMES.match(url):
            hrefs.append(url)
        else:
            hrefs.append(None)
            refused = refused or url
    if refused is not None:
        _warn(f"DataTable: column {name!r} links only to http(s):// and mailto: URLs; "
                   f"{refused[:60]!r} and any like it show as text.")
    return hrefs


def _payload(rows: int, columns: list[_Column]) -> dict[str, t.Any]:
    """A big table's rows for report.js (#38), column by column: how many there are, each cell's
    text, its sort key where a column has any that differs from its text (``null``: sort by
    the text), and its link where a column has links (``null``: none)."""
    keys = {
        str(j): c.keys for j, c in enumerate(columns)
        if any(k is not None and k != shown for k, shown in zip(c.keys, c.texts, strict=True))
    }
    links = {str(j): c.hrefs for j, c in enumerate(columns) if c.hrefs is not None}
    payload: dict[str, t.Any] = {"rows": rows, "text": [c.texts for c in columns], "keys": keys}
    if links:
        payload["links"] = links
    return payload


__all__ = ["PAGE_ROWS", "csv_text", "from_json", "render_datatable", "render_table"]
