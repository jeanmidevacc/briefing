"""Rendering is byte-reproducible when the timestamp is pinned."""
from __future__ import annotations

from datetime import UTC, datetime

import briefing as bf
from briefing.renderers.html import render_report


def _doc() -> bf.Briefing:
    return bf.Briefing(
        bf.Text("# Title"),
        bf.Group(bf.BigNumber("A", 1), bf.BigNumber("B", 2), columns=2),
        bf.Alert("note", level="info"),
    )


def test_same_input_same_output_with_pinned_now() -> None:
    now = datetime(2024, 1, 2, 3, 4, tzinfo=UTC)
    a = render_report(_doc(), name="R", now=now)
    b = render_report(_doc(), name="R", now=now)
    assert a == b


def test_pinned_now_appears_in_header() -> None:
    now = datetime(2024, 1, 2, 3, 4, tzinfo=UTC)
    html = render_report(_doc(), name="R", now=now)
    assert "2024-01-02 03:04 UTC" in html
    assert now.isoformat() in html


def test_source_date_epoch_env_var(monkeypatch) -> None:
    # 2021-01-01T00:00:00Z
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1609459200")
    html = render_report(_doc(), name="R")
    assert "2021-01-01 00:00 UTC" in html


def test_unpinned_still_renders() -> None:
    assert "<html" in render_report(_doc(), name="R")


# ── charts (#10) ──────────────────────────────────────────────────────────────


def _charts_doc() -> bf.Briefing:
    import pytest

    go = pytest.importorskip("plotly.graph_objects")
    figure = pytest.importorskip("matplotlib.figure")
    mpl_fig = figure.Figure(figsize=(4, 3))
    ax = mpl_fig.add_subplot()
    ax.plot([1, 2, 3], [3, 1, 2], marker="o")  # clip paths and markers get hashed ids
    ax.set_title("line")
    return bf.Briefing(
        bf.Plot(go.Figure(go.Scatter(x=[1, 2], y=[3, 4]))),
        bf.Plot(mpl_fig),
        bf.Toggle(bf.Plot(go.Figure(go.Bar(x=["a"], y=[1]))), label="More"),
    )


def test_charts_render_byte_identical(monkeypatch) -> None:
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1609459200")
    report = _charts_doc()
    assert render_report(report, name="R") == render_report(report, name="R")


def test_charts_render_byte_identical_across_documents(monkeypatch) -> None:
    # Two separately built, identical documents: nothing may depend on object identity.
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1609459200")
    assert render_report(_charts_doc(), name="R") == render_report(_charts_doc(), name="R")


def test_plotly_div_ids_come_from_the_render(monkeypatch) -> None:
    from tests.html_helpers import parse

    soup = parse(render_report(_charts_doc(), name="R"))
    ids = [div.get("id") for div in soup.select("figure.bf-plot div.plotly-graph-div")]
    assert len(ids) == 2
    assert len(set(ids)) == 2
    assert all(str(i).startswith("plotly-") for i in ids)


def test_matplotlib_svg_has_no_date() -> None:
    html = render_report(_charts_doc(), name="R")
    assert "<dc:date>" not in html
