"""The reports the contract and golden tests render: every block type, alone, nested and over data.

``SCENARIOS`` maps a name to a builder that takes the ``request.getfixturevalue``
of a test, so data blocks can use the shared dataframes in ``conftest.py``.
Builders that need a chart library skip the test when it isn't installed.
"""
from __future__ import annotations

import typing as t
from collections.abc import Callable

import pandas as pd
import pytest

import briefing as bf
from briefing.blocks.base import Block
from tests.banner_images import RED_SVG

#: The "calendar" scenario keeps the deprecated hour view (#111) so the tests still cover it;
#: modules that render the scenarios filter its warning with this.
HOUR_VIEW_WARNING = "ignore:CalendarHeatmap. the hour view:DeprecationWarning"

Frames = Callable[[str], pd.DataFrame]
Build = Callable[[Frames], bf.Briefing]

#: Shared dataframes from ``conftest.py`` that the data blocks are rendered over.
FRAME_FIXTURES = ["df_mixed", "df_empty", "df_single_row", "df_all_null", "df_constant"]
REPORT_NAME = "Contract report"


# ── figures (imported lazily, skipped when the library is missing) ────────────


def matplotlib_figure(kind: str = "line") -> t.Any:
    figure = pytest.importorskip("matplotlib.figure")
    fig = figure.Figure(figsize=(4, 3))
    ax = fig.add_subplot()
    if kind == "line":
        ax.plot([1, 2, 3], [3, 1, 2], marker="o")
    else:
        ax.bar(["a", "b"], [2, 5])
    return fig


def plotly_figure() -> t.Any:
    go = pytest.importorskip("plotly.graph_objects")
    return go.Figure(go.Scatter(x=[1, 2, 3], y=[3, 1, 2]))


def altair_chart() -> t.Any:
    alt = pytest.importorskip("altair")
    return alt.Chart(pd.DataFrame({"x": [1, 2, 3], "y": [3, 1, 2]})).mark_point().encode(x="x", y="y")


# ── scenarios ─────────────────────────────────────────────────────────────────


def tabs(*blocks: Block) -> bf.Select:
    return bf.Select(*blocks)


#: Data blocks, each rendered over every fixture in FRAME_FIXTURES.
FRAME_BLOCKS: dict[str, Callable[[pd.DataFrame], Block]] = {
    "table": lambda frame: bf.Table(frame, caption="Table"),
    "datatable": lambda frame: bf.DataTable(frame, caption="DataTable"),
    "dataprofile": lambda frame: bf.lab.DataProfile(frame),
    "datadive": lambda frame: bf.lab.DataDive(frame),
}


def _over_frame(make: Callable[[pd.DataFrame], Block], fixture: str) -> Build:
    return lambda df: bf.Briefing(make(df(fixture)))


def _infinite_frame() -> pd.DataFrame:
    return pd.DataFrame({"x": [1.0, float("inf"), float("-inf"), None, 2.5], "n": [1, 2, 3, 4, 5]})


def _over_infinite(make: Callable[[pd.DataFrame], Block]) -> Build:
    return lambda _: bf.Briefing(make(_infinite_frame()))


SCENARIOS: dict[str, Build] = {
    "text": lambda _: bf.Briefing(bf.Text("# Title\n\nSome *markdown* with a [link](https://example.com).")),
    "text-markdown-table": lambda _: bf.Briefing(bf.Text("| a | b |\n| --- | --- |\n| 1 | 2 |")),
    "html": lambda _: bf.Briefing(bf.HTML("<p>Raw <b>HTML</b></p><ul><li>item</li></ul>")),
    "code": lambda _: bf.Briefing(bf.Code("SELECT 1 FROM t", language="sql", caption="Query")),
    "formula": lambda _: bf.Briefing(bf.Formula(r"\frac{a}{b}", caption="Ratio")),
    "bignumber": lambda _: bf.Briefing(
        bf.Group(
            bf.BigNumber("Revenue", "$4.2M", change="+3%", is_upward_change=True),
            bf.BigNumber("Churn", 0.12, change="-1%", is_upward_change=False),
            bf.BigNumber("Users", 1200),
            columns=3,
        )
    ),
    "alert": lambda _: bf.Briefing(bf.Alert("Drift detected.", level="warning", title="Heads up")),
    "group-widths": lambda _: bf.Briefing(bf.Group(bf.Text("a"), bf.Text("b"), columns=2, widths=[3, 1])),
    "select-tabs": lambda _: bf.Briefing(tabs(bf.Text("a", label="A"), bf.Text("b", label="B"))),
    "select-dropdown": lambda _: bf.Briefing(
        bf.Select(bf.Text("a", label="A"), bf.Text("b", label="B"), type="dropdown")
    ),
    "toggle": lambda _: bf.Briefing(bf.Toggle(bf.Text("hidden"), bf.Text("more"), label="More")),
    "pages": lambda _: bf.Briefing(bf.Page(bf.Text("one"), title="One"), bf.Page(bf.Text("two"), title="Two")),
    "nested-layout": lambda _: bf.Briefing(
        tabs(
            bf.Group(
                bf.Toggle(bf.Text("x"), label="T1"),
                tabs(bf.Text("a", label="A"), bf.Text("b", label="B")),
                label="Outer",
            ),
            bf.Toggle(tabs(bf.Text("c", label="C"), bf.Text("d", label="D")), label="T2"),
        ),
        bf.Toggle(bf.Toggle(bf.Text("deep"), label="Inner"), label="Outer toggle"),
    ),
    "plot-matplotlib": lambda _: bf.Briefing(bf.Plot(matplotlib_figure(), caption="Line")),
    "plot-plotly": lambda _: bf.Briefing(bf.Plot(plotly_figure(), caption="Scatter")),
    "plot-altair": lambda _: bf.Briefing(bf.Plot(altair_chart(), caption="Points")),
    "two-matplotlib-plots": lambda _: bf.Briefing(
        bf.Plot(matplotlib_figure("line")), bf.Plot(matplotlib_figure("bar"))
    ),
    "table-styler": lambda df: bf.Briefing(bf.Table(df("df_constant").style.highlight_max(), caption="Styled")),
    "two-table-stylers": lambda df: bf.Briefing(
        bf.Table(df("df_constant").style.highlight_max()), bf.Table(df("df_constant").style.highlight_max())
    ),
    **{
        f"{kind}-{fixture}": _over_frame(make, fixture)
        for kind, make in FRAME_BLOCKS.items()
        for fixture in FRAME_FIXTURES
    },
    **{f"{kind}-infinite": _over_infinite(make) for kind, make in FRAME_BLOCKS.items()},
    "calendar": lambda df: bf.Briefing(bf.lab.CalendarHeatmap(
        df("df_pipeline_log"), date="run_at", value="rows", group="team", expected=500, events=df("df_events"),
        views=("days", "hours"), tz="America/Montreal", on_click="rows")),
    "calendar-diverging": lambda df: bf.Briefing(
        bf.lab.CalendarHeatmap(df("df_signed"), date="day", value="balance", center=0,
                               colors=["#d73027", "#f7f7f7", "#1a9850"], week_start="sunday")),
    "banner": lambda _: bf.Briefing(
        bf.Banner("# Cover\n\nA **subtitle**.", image=RED_SVG, text_position=55, opacity=80),
        bf.Banner("## Left", image=RED_SVG, side="left", text_position=40, focus=(20, 80), alt="A red field"),
    ),
    "export-menu": lambda _: bf.Briefing(
        bf.Page(bf.Text("# One"), title="One"), bf.Page(bf.Text("# Two"), title="Two"), export="png"
    ),
    "everything": lambda df: bf.Briefing(
        bf.Text("# Everything"),
        bf.Group(bf.BigNumber("A", 1), bf.Alert("note"), columns=2),
        tabs(
            bf.Group(bf.HTML("<i>raw</i>"), bf.Code("x = 1"), bf.Formula("x^2"), label="Text"),
            bf.Group(bf.Plot(matplotlib_figure()), bf.Plot(plotly_figure()), label="Plots"),
            bf.Group(bf.Table(df("df_mixed")), bf.DataTable(df("df_mixed")), label="Tables"),
            bf.Group(bf.lab.DataProfile(df("df_mixed")), bf.lab.DataDive(df("df_mixed")), label="Lab"),
        ),
        bf.Toggle(bf.Select(bf.Text("a", label="A"), bf.Text("b", label="B"), type="dropdown"), label="More"),
    ),
}
