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
from tests.contract import PAYLOAD

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


def big_frame(rows: int = 1_500) -> pd.DataFrame:
    """More rows than ``DataTable.HTML_ROWS``: a table whose rows are packed as JSON (#38)."""
    return pd.DataFrame({
        "id": range(rows),
        "x": [((i * 37) % 101) / 7 for i in range(rows)],
        "word": [f"word {i % 13}" for i in range(rows)],
        "day": pd.date_range("2025-01-01", periods=rows, freq="h"),
    })


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
    "alert": lambda _: bf.Briefing(bf.Alert("Drift **detected** in `orders`; see [the runbook](#runbook).",
                                            level="warning", title="Heads *up*")),
    "group-widths": lambda _: bf.Briefing(bf.Group(bf.Text("a"), bf.Text("b"), columns=2, widths=[3, 1])),
    "select-tabs": lambda _: bf.Briefing(tabs(bf.Text("a", label="A"), bf.Text("b", label="B"))),
    "select-dropdown": lambda _: bf.Briefing(
        bf.Select(bf.Text("a", label="A"), bf.Text("b", label="B"), type="dropdown")
    ),
    "toggle": lambda _: bf.Briefing(bf.Toggle(bf.Text("hidden"), bf.Text("more"), label="More")),
    "pages": lambda _: bf.Briefing(bf.Page(bf.Text("one"), title="One"), bf.Page(bf.Text("two"), title="Two")),
    "header": lambda _: bf.Briefing(
        bf.Text("Body"),
        header=bf.Header(subtitle="Weekly **search** interest", author="Analytics team", logo=RED_SVG,
                         as_of="2026-11-20", tz="America/Montreal")),
    "tab-style": lambda _: bf.Briefing(
        bf.Page(bf.Select(bf.Text("a", label="A"), bf.Text("b", label="B"),
                          style=bf.TabStyle(layout="center", size="sm", variant="pills")), title="One"),
        bf.Page(bf.Text("two"), title="Two"),
        tabs=bf.TabStyle(layout="stretch", full_width=True, sticky=True, size="lg", variant="boxed")),
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
    "datatable-big": lambda _: bf.Briefing(bf.DataTable(
        big_frame(), caption="Packed rows", name="rows", formats={"x": "{:.2f}"},
        links={"id": "https://example.org/rows/{}"})),
    "datatable-formats": lambda _: bf.Briefing(bf.DataTable(
        pd.DataFrame({
            "title": ["Graphs", "Ranking", "Bandits"],
            "url": ["https://example.org/a", "https://example.org/b", None],
            "doi": ["10.1000/a", None, "10.1000/c"],
            "citations": [12345, 678, 9],
            "share": [0.1234, 0.5, None],
            "published": pd.to_datetime(pd.Series(["2024-01-05", "2023-11-30", None])),
        }),
        formats={"citations": "{:,}", "share": "{:.1%}", "published": "{:%d %b %Y}"},
        links={"doi": "https://doi.org/{}", "title": "{url}"},
        wrap=["title"],
        download=True,
    )),
    "calendar": lambda df: bf.Briefing(bf.lab.CalendarHeatmap(
        df("df_pipeline_log"), date="run_at", value="rows", group="team", expected=500,
        events=df("df_events").assign(color=pd.Series(["#2dd4bf", None, "rgb(96, 165, 250)"])),
        tz="America/Montreal", on_click="rows")),
    "calendar-diverging": lambda df: bf.Briefing(
        bf.lab.CalendarHeatmap(df("df_signed"), date="day", value="balance", center=0,
                               colors=["#d73027", "#f7f7f7", "#1a9850"], week_start="sunday",
                               start="2026-02-15", end="2026-05-31")),
    "time-heatmap": lambda df: bf.Briefing(bf.lab.TimeHeatmap(
        df("df_pipeline_log"), date="run_at", rows="weekday", columns="hour", value="rows", group="team",
        group_order=["ingest"], on_click="rows")),
    "time-heatmap-months": lambda df: bf.Briefing(bf.lab.TimeHeatmap(
        df("df_signed"), date="day", rows="day", columns="month", value="balance", agg="mean", center=0,
        colors=["#d73027", "#f7f7f7", "#1a9850"], week_start="sunday")),
    "banner": lambda _: bf.Briefing(
        bf.Banner("# Cover\n\nA **subtitle**.", image=RED_SVG, text_position=55, opacity=80,
                  kicker="Data through <Nov 20>"),
        bf.Banner("## Left", image=RED_SVG, side="left", text_position=40, focus=(20, 80), alt="A red field"),
    ),
    "image": lambda _: bf.Briefing(
        bf.Image(RED_SVG, caption="A red field", width="60%"),
        bf.Image(RED_SVG, alt="Red", width=120),
    ),
    "attachment": lambda df: bf.Briefing(
        bf.Attachment(b"# Notes\n\nPacked, as text.\n", filename="notes.md", label="Notes"),
        bf.Attachment(bytes(range(256)), filename="blob.bin"),
        bf.Attachment(df("df_constant"), name="constant"),
    ),
    "links": lambda _: bf.Briefing(
        bf.Page(bf.Text("# Summary {#top}\n\nSee [the method](#detail/methodology)."), title="Summary", name="summary"),
        bf.Page(
            bf.Select(bf.Text("North", label="North", name="north"), bf.Text("South", label="South"), name="by-region"),
            bf.Select(bf.Text("One", label="One"), bf.Text("Two", label="Two", name="two"), type="dropdown"),
            bf.Toggle(bf.Text("## Methodology {#methodology}\n\nHow it was measured.", name="method"), label="More",
                      name="more"),
            title="Detail",
            name="detail",
        ),
        bf.Page(bf.Text("## Methodology {#methodology}\n\nThe same name in a page without one."), title="Notes"),
    ),
    "copy-embed": lambda df: bf.Briefing(
        bf.Page(
            bf.Text("# Summary {#top}\n\nSee [the detail](#detail/rows)."),
            bf.Group(bf.BigNumber("Revenue", "$4.2M"), bf.Alert("Margin dropped.", title="Heads up"), columns=2,
                     label="Numbers"),
            bf.Banner("## Q1", image=RED_SVG),
            title="Summary",
            name="summary",
        ),
        bf.Page(
            bf.Plot(matplotlib_figure(), caption="Line"),
            bf.Plot(plotly_figure(), name="scatter"),
            bf.Table(df("df_constant")),
            bf.DataTable(df("df_mixed"), name="rows"),
            bf.lab.DataProfile(pd.DataFrame({"n": [1, 2, 3]})),  # dtypes named alike by pandas 2 and 3
            bf.Code("x = 1"),
            title="Detail",
            name="detail",
        ),
        export=("png", "embed"),
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


# ── user text, to check it stays escaped ──────────────────────────────────────


def _payload_frame() -> pd.DataFrame:
    return pd.DataFrame({PAYLOAD: [PAYLOAD, "plain"], "n": [1, 2]})


#: Every user-supplied string set to PAYLOAD. ``Text`` and ``HTML`` content is
#: raw markup by design (see CLAUDE.md), so only their labels are tested.
ESCAPE_SCENARIOS: dict[str, Callable[[], tuple[bf.Briefing, str]]] = {
    "report-name": lambda: (bf.Briefing(bf.Text("x")), PAYLOAD),
    "report-footer": lambda: (bf.Briefing(bf.Text("x"), footer=PAYLOAD), "R"),
    "select-tab-labels": lambda: (bf.Briefing(tabs(bf.Text("a", label=PAYLOAD), bf.Text("b", label=PAYLOAD))), "R"),
    "select-dropdown-labels": lambda: (
        bf.Briefing(bf.Select(bf.Text("a", label=PAYLOAD), bf.HTML("<b>b</b>", label=PAYLOAD), type="dropdown")),
        "R",
    ),
    "toggle-label": lambda: (bf.Briefing(bf.Toggle(bf.Text("a"), label=PAYLOAD)), "R"),
    "page-titles": lambda: (bf.Briefing(bf.Page(bf.Text("a"), title=PAYLOAD), bf.Page(bf.Text("b"), title="2")), "R"),
    "code": lambda: (bf.Briefing(bf.Code(PAYLOAD, language=PAYLOAD, caption=PAYLOAD)), "R"),
    "formula": lambda: (bf.Briefing(bf.Formula(PAYLOAD, caption=PAYLOAD)), "R"),
    "bignumber": lambda: (bf.Briefing(bf.BigNumber(PAYLOAD, PAYLOAD, change=PAYLOAD, is_upward_change=True)), "R"),
    "alert": lambda: (bf.Briefing(bf.Alert(PAYLOAD, title=PAYLOAD)), "R"),
    "plot-caption": lambda: (bf.Briefing(bf.Plot(matplotlib_figure(), caption=PAYLOAD)), "R"),
    "table": lambda: (bf.Briefing(bf.Table(_payload_frame(), caption=PAYLOAD)), "R"),
    "datatable": lambda: (bf.Briefing(bf.DataTable(_payload_frame(), caption=PAYLOAD)), "R"),
    "dataprofile": lambda: (bf.Briefing(bf.lab.DataProfile(_payload_frame())), "R"),
    "datadive": lambda: (bf.Briefing(bf.lab.DataDive(_payload_frame(), color=PAYLOAD)), "R"),
    "image-caption-alt": lambda: (bf.Briefing(bf.Image(RED_SVG, caption=PAYLOAD, alt=PAYLOAD)), "R"),
    "attachment-label": lambda: (bf.Briefing(bf.Attachment(b"x", filename="x.txt", label=PAYLOAD)), "R"),
    "banner-alt": lambda: (bf.Briefing(tabs(bf.Banner("x", image=RED_SVG, alt=PAYLOAD, label=PAYLOAD),
                                             bf.Text("b", label="B"))), "R"),
    "calendar": lambda: (bf.Briefing(bf.lab.CalendarHeatmap(
        pd.DataFrame({"day": pd.to_datetime(["2026-01-05", "2026-01-06"]), "who": [PAYLOAD, "b"]}),
        date="day", group="who", events=pd.DataFrame({"start": ["2026-01-05"], "label": [PAYLOAD]}),
        on_click="rows")), "R"),
}
