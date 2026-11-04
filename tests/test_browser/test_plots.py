"""Charts fill their container and draw without the network (#8, #9)."""
from __future__ import annotations

import typing as t

import pandas as pd
import pytest
from playwright.sync_api import Page

import briefing as bf
from tests.test_browser.conftest import Viewer


def _plotly_figure() -> t.Any:
    go = pytest.importorskip("plotly.graph_objects")
    return go.Figure(go.Scatter(x=[1, 2, 3], y=[3, 1, 2]))


def chart_fill(page: Page, nth: int = 0) -> float:
    """Width of the nth drawn Plotly chart as a fraction of its figure's width."""
    page.wait_for_timeout(300)  # let Plotly's resize handlers run
    figure = page.locator("figure.bf-plot").nth(nth)
    chart = figure.locator(".main-svg").first
    chart_box, figure_box = chart.bounding_box(), figure.bounding_box()
    assert chart_box is not None and figure_box is not None, "chart not drawn"
    return chart_box["width"] / figure_box["width"]


def test_visible_plotly_chart_fills_its_width(viewer: Viewer) -> None:
    page = viewer.open(bf.Briefing(bf.Plot(_plotly_figure())))
    assert chart_fill(page) > 0.97


def test_plotly_chart_fills_its_width_when_toggle_opens(viewer: Viewer) -> None:
    page = viewer.open(bf.Briefing(bf.Toggle(bf.Plot(_plotly_figure()), label="Chart")))
    page.get_by_role("button", name="Chart").click()
    assert chart_fill(page) > 0.97


def test_plotly_chart_fills_its_width_in_dropdown(viewer: Viewer) -> None:
    report = bf.Briefing(
        bf.Select(bf.Text("first", label="Text"), bf.Plot(_plotly_figure(), label="Chart"), type="dropdown")
    )
    # Passes in 0.1.0 (the dropdown hides panels after Plotly has drawn); kept so #9 can't regress it.
    page = viewer.open(report)
    page.locator(".bf-select__select").select_option(label="Chart")
    assert chart_fill(page) > 0.97


def test_plotly_chart_fills_its_width_in_nested_toggle(viewer: Viewer) -> None:
    inner = bf.Toggle(bf.Plot(_plotly_figure()), label="Inner")
    page = viewer.open(bf.Briefing(bf.Toggle(bf.Text("outer"), inner, label="Outer")))
    page.get_by_role("button", name="Outer").click()
    page.get_by_role("button", name="Inner").click()
    assert chart_fill(page) > 0.97


def test_plotly_chart_fills_its_width_in_second_tab(viewer: Viewer) -> None:
    report = bf.Briefing(bf.Select(bf.Text("first", label="Text"), bf.Plot(_plotly_figure(), label="Chart")))
    page = viewer.open(report)
    page.get_by_role("tab", name="Chart").click()
    assert chart_fill(page) > 0.97


def test_altair_chart_draws_offline(viewer: Viewer) -> None:
    alt = pytest.importorskip("altair")
    chart = alt.Chart(pd.DataFrame({"x": [1, 2, 3], "y": [3, 1, 2]})).mark_point().encode(x="x", y="y")
    page = viewer.open(bf.Briefing(bf.Plot(chart)))
    page.wait_for_timeout(500)
    assert viewer.external_requests == []
    # Vega draws into an SVG or a canvas, in the page or in a nested frame.
    drawn = [f for f in page.frames if f.locator("svg.marks, canvas.marks").count() > 0]
    assert drawn, "the Altair chart was not drawn"


def test_altair_chart_fills_its_width_when_toggle_opens(viewer: Viewer) -> None:
    alt = pytest.importorskip("altair")
    chart = alt.Chart(pd.DataFrame({"x": [1, 2, 3], "y": [3, 1, 2]})).mark_line().encode(x="x", y="y")
    page = viewer.open(bf.Briefing(bf.Toggle(bf.Plot(chart), label="Chart")))
    page.get_by_role("button", name="Chart").click()
    page.wait_for_timeout(500)
    drawn = page.locator(".bf-altair svg").first.bounding_box()
    figure = page.locator("figure.bf-plot").first.bounding_box()
    assert drawn is not None and figure is not None
    assert drawn["width"] > 0.9 * figure["width"]


def _mpl(kind: str) -> t.Any:
    figure = pytest.importorskip("matplotlib.figure")
    fig = figure.Figure(figsize=(4, 2.5))
    ax = fig.add_subplot()
    if kind == "line":
        ax.plot([1, 2, 3, 4], [3, 1, 4, 2], marker="o")
        ax.set_ylim(1.5, 3.5)  # clips the line: needs its clip path
    else:
        ax.scatter([1, 2, 3], [2, 3, 1], marker="s")
    ax.set_title(kind)
    return fig


def test_matplotlib_references_resolve_inside_their_own_figure(viewer: Viewer) -> None:
    # The browser resolves a clip-path or <use> by document-wide id: with shared ids,
    # the second figure's references would land in the first figure's SVG.
    page = viewer.open(bf.Briefing(bf.Plot(_mpl("line")), bf.Plot(_mpl("scatter"))))
    stray: list[str] = page.evaluate("""() => {
      const out = [];
      document.querySelectorAll('figure.bf-plot svg').forEach((svg, n) => {
        svg.querySelectorAll('[clip-path], use').forEach(el => {
          const ref = el.getAttribute('clip-path') || el.getAttribute('xlink:href') || el.getAttribute('href') || '';
          const id = (ref.match(/#([^)"']+)/) || [])[1];
          const target = id && document.getElementById(id);
          if (!target || target.closest('svg') !== svg) out.push(`figure ${n}: ${ref}`);
        });
      });
      return out;
    }""")
    assert stray == []
