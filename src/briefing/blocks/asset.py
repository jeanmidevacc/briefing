"""Asset-based blocks: Plot, Table, DataTable.

These blocks hold external data (figures, DataFrames) and are serialised
into the HTML as inline assets during the render pass.

``Table`` / ``DataTable`` accept any dataframe library ``briefing`` can
normalise (see :mod:`briefing._frames`); the data is stored internally as a
pandas DataFrame.
"""
from __future__ import annotations

import typing as t
import warnings

from briefing._frames import is_pandas_dataframe, to_pandas
from briefing.blocks.base import _MAX_CAPTION_LEN, Block, BlockId, _truncate

if t.TYPE_CHECKING:
    import pandas as pd
    from pandas.io.formats.style import Styler


class Plot(Block):
    """Chart / figure block — library agnostic.

    Auto-detects the figure type at render time:

    - **Plotly** → embedded as interactive HTML (inline JS)
    - **Altair / Vega-Lite** → embedded as Vega spec (inline runtime)
    - **Matplotlib / Seaborn / Plotnine** → embedded as inline SVG
    - **Bokeh** → embedded with inline resources

    Args:
        figure: A Plotly, Altair, Matplotlib (or Seaborn / Plotnine) or Bokeh figure.
        caption: Optional caption shown below the chart.
        responsive: Let the chart fill the width of its container. Size the figure in
            its plotting library, e.g. Matplotlib's ``figsize=(w, h)``.
        name: Stable block id (letters, digits, ``_`` and ``-``), its link in the report (``#page/name``).
        label: Tab or dropdown label when the block is inside a ``Select``.

    Example::

        bf.Plot(plotly_fig, caption="Revenue over time")
        bf.Plot(altair_chart, label="Chart", responsive=True)
    """

    embed_noun: t.ClassVar[str | None] = "chart"

    def __init__(
        self,
        figure: t.Any,
        caption: str | None = None,
        responsive: bool = True,
        name: BlockId | None = None,
        label: str | None = None,
    ) -> None:
        super().__init__(name=name, label=label)
        self.figure = figure
        self.caption = _truncate(caption, _MAX_CAPTION_LEN) if caption else caption
        self.responsive = responsive


class Table(Block):
    """Static HTML table rendered from a dataframe or a pandas Styler.

    Best for multidimensional DataFrames where you want pandas' Styler
    formatting to be preserved. A Styler is used verbatim; any other frame
    (pandas, polars, pyarrow, …) is normalised to pandas.

    Args:
        data: A dataframe (as for :class:`DataTable`) or a pandas ``Styler``, kept as-is.
        caption: Optional caption below the table.
        name: Stable block id (letters, digits, ``_`` and ``-``), its link in the report (``#page/name``).
        label: Tab or dropdown label when the block is inside a ``Select``.

    Example::

        bf.Table(df)
        bf.Table(df.style.highlight_max(color="lightgreen"))
    """

    embed_noun: t.ClassVar[str | None] = "table"

    def __init__(
        self,
        data: pd.DataFrame | Styler | t.Any,
        caption: str | None = None,
        name: BlockId | None = None,
        label: str | None = None,
    ) -> None:
        super().__init__(name=name, label=label)
        # A Styler carries its own formatting rules — keep it as-is. Everything
        # else goes through the dataframe intake layer.
        if type(data).__name__ == "Styler" or is_pandas_dataframe(data):
            self.data = data
        else:
            self.data = to_pandas(data, block="Table")
        self.caption = _truncate(caption, _MAX_CAPTION_LEN) if caption else caption


class DataTable(Block):
    """Interactive, sortable and searchable table rendered from a pandas DataFrame.

    Handles large datasets via client-side pagination. Viewers can also sort
    columns and filter rows by typing in the search box.

    Args:
        df: The data: pandas, polars, pyarrow, anything with the dataframe
            interchange protocol, or a dict of columns.
        caption: Optional caption below the table.
        max_rows: Rows beyond this are dropped with a warning.
        name: Stable block id (letters, digits, ``_`` and ``-``), its link in the report (``#page/name``).
        label: Tab or dropdown label when the block is inside a ``Select``.

    Example::

        bf.DataTable(df, caption="Top 1 000 orders")
    """

    embed_noun: t.ClassVar[str | None] = "table"

    #: Maximum rows rendered by default; larger DataFrames are truncated with a warning.
    MAX_ROWS: t.ClassVar[int] = 10_000
    #: Tables up to this many rows keep every row in the HTML. Bigger ones keep the first
    #: page there (what a reader without JavaScript sees) and the rows as compressed JSON,
    #: which the page's script shows, sorts and searches (#38).
    HTML_ROWS: t.ClassVar[int] = 1_000

    def __init__(
        self,
        df: pd.DataFrame | t.Any,
        caption: str | None = None,
        max_rows: int = MAX_ROWS,
        name: BlockId | None = None,
        label: str | None = None,
    ) -> None:
        super().__init__(name=name, label=label)
        df = to_pandas(df, block="DataTable")

        if len(df) > max_rows:
            warnings.warn(
                f"DataTable: DataFrame has {len(df):,} rows — truncating to {max_rows:,}. "
                "Increase 'max_rows' to render more.",
                stacklevel=2,
            )
            df = df.head(max_rows)

        self.df = df
        self.caption = _truncate(caption, _MAX_CAPTION_LEN) if caption else caption
        self.max_rows = max_rows


# ── public re-exports ─────────────────────────────────────────────────────────

__all__: list[str] = ["DataTable", "Plot", "Table"]
