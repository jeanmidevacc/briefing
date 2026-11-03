"""Tests for the plot rendering module (Phase 3)."""
from __future__ import annotations

import pytest
from bs4 import BeautifulSoup

from briefing._error import BriefingError
from briefing.blocks.asset import Plot
from briefing.blocks.layout import Briefing
from briefing.renderers.plot import detect_library, render_figure, scan_for_plots
from tests.html_helpers import attr, classes, find_one

# ── detect_library ────────────────────────────────────────────────────────────


class TestDetectLibrary:
    def test_plotly_figure(self):
        plotly = pytest.importorskip("plotly.graph_objects")
        fig = plotly.Figure()
        assert detect_library(fig) == "plotly"

    def test_matplotlib_figure(self):
        mpl = pytest.importorskip("matplotlib.pyplot")
        fig, _ = mpl.subplots()
        assert detect_library(fig) == "matplotlib"
        mpl.close("all")

    def test_matplotlib_axes(self):
        mpl = pytest.importorskip("matplotlib.pyplot")
        _, ax = mpl.subplots()
        assert detect_library(ax) == "matplotlib"
        mpl.close("all")

    def test_bokeh_figure(self):
        bokeh_plotting = pytest.importorskip("bokeh.plotting")
        fig = bokeh_plotting.figure()
        assert detect_library(fig) == "bokeh"

    def test_altair_chart(self):
        alt = pytest.importorskip("altair")
        chart = alt.Chart()
        assert detect_library(chart) == "altair"

    def test_unknown_object_raises(self):
        with pytest.raises(BriefingError, match="Unsupported figure type"):
            detect_library(object())

    def test_unknown_object_raises_for_dict(self):
        with pytest.raises(BriefingError):
            detect_library({"not": "a figure"})


# ── scan_for_plots ────────────────────────────────────────────────────────────


class TestScanForPlots:
    def test_empty_blocks_returns_empty_set(self):
        from briefing.blocks.text import Text

        root = Briefing(Text("hi"))
        assert scan_for_plots(root) == set()

    def test_finds_matplotlib_plot(self):
        mpl = pytest.importorskip("matplotlib.pyplot")
        fig, _ = mpl.subplots()
        root = Briefing(Plot(fig))
        libs = scan_for_plots(root)
        mpl.close("all")
        assert "matplotlib" in libs

    def test_finds_plotly_plot(self):
        go = pytest.importorskip("plotly.graph_objects")
        fig = go.Figure()
        root = Briefing(Plot(fig))
        libs = scan_for_plots(root)
        assert "plotly" in libs

    def test_finds_nested_plot(self):
        mpl = pytest.importorskip("matplotlib.pyplot")
        from briefing.blocks.layout import Group

        fig, _ = mpl.subplots()
        root = Briefing(Group(Plot(fig)))
        libs = scan_for_plots(root)
        mpl.close("all")
        assert "matplotlib" in libs

    def test_multiple_libraries_detected(self):
        mpl = pytest.importorskip("matplotlib.pyplot")
        go = pytest.importorskip("plotly.graph_objects")
        fig_mpl, _ = mpl.subplots()
        fig_plotly = go.Figure()
        root = Briefing(Plot(fig_mpl), Plot(fig_plotly))
        libs = scan_for_plots(root)
        mpl.close("all")
        assert libs == {"matplotlib", "plotly"}

    def test_unsupported_figure_skipped_in_scan(self):
        """scan_for_plots should not raise for unsupported figures — errors surface at render."""
        root = Briefing(Plot(object()))
        # Should not raise
        libs = scan_for_plots(root)
        assert libs == set()


# ── render_figure (matplotlib) ────────────────────────────────────────────────


class TestRenderMatplotlib:
    def setup_method(self):
        self.mpl = pytest.importorskip("matplotlib.pyplot")

    def teardown_method(self):
        self.mpl.close("all")

    def test_renders_svg_fragment(self):
        fig, ax = self.mpl.subplots()
        ax.plot([1, 2, 3], [1, 4, 9])
        html = render_figure(Plot(fig))
        assert "<svg" in html
        assert "<figure" in html

    def test_wraps_in_figure_tag(self):
        fig, _ = self.mpl.subplots()
        html = render_figure(Plot(fig))
        soup = BeautifulSoup(html, "html.parser")
        assert "bf-plot" in classes(find_one(soup, "figure"))

    def test_responsive_removes_fixed_width(self):
        fig, _ = self.mpl.subplots()
        html = render_figure(Plot(fig, responsive=True))
        soup = BeautifulSoup(html, "html.parser")
        svg = soup.find("svg")
        assert svg is not None
        assert svg.get("width") == "100%"

    def test_non_responsive_keeps_fixed_width(self):
        fig, _ = self.mpl.subplots()
        html = render_figure(Plot(fig, responsive=False))
        soup = BeautifulSoup(html, "html.parser")
        svg = soup.find("svg")
        assert svg is not None
        # should have a numeric width attribute, not "100%"
        w = svg.get("width", "")
        assert w != "100%"

    def test_caption_rendered(self):
        fig, _ = self.mpl.subplots()
        html = render_figure(Plot(fig, caption="My chart"))
        soup = BeautifulSoup(html, "html.parser")
        cap = soup.find("figcaption")
        assert cap is not None
        assert "My chart" in cap.text

    def test_no_caption_when_empty(self):
        fig, _ = self.mpl.subplots()
        html = render_figure(Plot(fig))
        soup = BeautifulSoup(html, "html.parser")
        assert soup.find("figcaption") is None

    def test_axes_object_accepted(self):
        _, ax = self.mpl.subplots()
        html = render_figure(Plot(ax))
        assert "<svg" in html

    def test_self_contained_no_external_src(self):
        fig, ax = self.mpl.subplots()
        ax.bar(["A", "B"], [3, 7])
        html = render_figure(Plot(fig))
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup.find_all(src=True):
            assert not attr(tag, "src").startswith("http"), f"External src found: {attr(tag, 'src')}"


# ── render_figure (plotly) ────────────────────────────────────────────────────


class TestRenderPlotly:
    def test_renders_div(self):
        go = pytest.importorskip("plotly.graph_objects")
        fig = go.Figure(go.Scatter(x=[1, 2], y=[3, 4]))
        html = render_figure(Plot(fig))
        soup = BeautifulSoup(html, "html.parser")
        assert soup.find("figure") is not None
        # plotly produces a <div> with data
        assert soup.find("div") is not None

    def test_no_inline_plotlyjs(self):
        """include_plotlyjs=False — the script tag with Plotly.js should NOT be in the figure HTML."""
        go = pytest.importorskip("plotly.graph_objects")
        fig = go.Figure()
        html = render_figure(Plot(fig))
        # plotlyjs bundle contains this identifier
        assert "var Plotly" not in html or len(html) < 500_000


# ── render_figure (unsupported) ───────────────────────────────────────────────


class TestRenderUnsupported:
    def test_unsupported_figure_returns_placeholder(self):
        html = render_figure(Plot(object()))
        soup = BeautifulSoup(html, "html.parser")
        placeholder = soup.find(class_="bf-placeholder")
        assert placeholder is not None
        assert "Unsupported" in placeholder.text


# ── full render_report with plots (integration) ───────────────────────────────


class TestRenderReportWithPlot:
    def test_matplotlib_in_full_report(self):
        mpl = pytest.importorskip("matplotlib.pyplot")
        from briefing.renderers.html import render_report

        fig, ax = mpl.subplots()
        ax.plot([1, 2, 3])
        html = render_report(Briefing(Plot(fig)))
        mpl.close("all")
        soup = BeautifulSoup(html, "html.parser")
        assert soup.find("svg") is not None
        # no external CDN references
        for tag in soup.find_all(src=True):
            assert not str(tag.get("src", "")).startswith("http")

    def test_plotly_runtime_embedded_once(self):
        go = pytest.importorskip("plotly.graph_objects")
        from briefing.renderers.html import render_report

        fig = go.Figure()
        html = render_report(Briefing(Plot(fig), Plot(go.Figure())))
        # plotlyjs bundle should appear exactly once in <head>
        assert html.count("var Plotly") <= 1
