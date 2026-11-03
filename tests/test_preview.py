"""Notebook previews: each block renders as a full report in its own iframe (#12)."""
from __future__ import annotations

import pandas as pd
import pytest

import briefing as bf
from briefing.blocks.base import Block
from tests.contract import RULES, check_no_external_urls
from tests.html_helpers import attr, find_one, parse


def _blocks() -> list[Block]:
    df = pd.DataFrame({"a": [1, 2], "b": ["x", "y"]})
    return [
        bf.Text("# Hello"), bf.HTML("<b>raw</b>"), bf.Code("x = 1"), bf.BigNumber("A", 1), bf.Alert("note"),
        bf.Group(bf.Text("a"), bf.Text("b"), columns=2), bf.Select(bf.Text("a", label="A"), bf.Text("b", label="B")),
        bf.Toggle(bf.Text("hidden"), label="More"), bf.Table(df), bf.DataTable(df),
        bf.lab.DataProfile(df), bf.Briefing(bf.Text("root")),
    ]


def _inner(iframe_html: str) -> str:
    frame = find_one(parse(iframe_html), "iframe.bf-preview")
    return attr(frame, "srcdoc")


@pytest.mark.parametrize("block", _blocks(), ids=lambda b: type(b).__name__)
def test_every_block_previews_in_its_own_iframe(block: Block) -> None:
    html = block._repr_html_()
    outer = parse(html)
    assert [t.name for t in outer.find_all(recursive=False)] == ["iframe"]
    inner = parse(_inner(html))
    assert inner.select(".bf-report")  # a complete report, like the saved file
    for rule in RULES.values():
        if rule.__name__ != "check_generator_meta":  # #23
            rule(inner)


def test_preview_markup_stays_inside_the_attribute() -> None:
    html = bf.Text("<script>bf_xss()</script> & \"quotes\"")._repr_html_()
    outer = parse(html)
    assert outer.find_all("script") == []
    assert "bf_xss" in _inner(html)


def test_preview_page_is_the_saved_report_plus_the_fit_script() -> None:
    report = bf.Briefing(bf.Text("x"))
    page = _inner(report._repr_html_())
    saved = bf.stringify(report)
    assert "bf-preview-fit" in page and "bf-preview-fit" not in saved
    assert page.replace(page[page.index('<script id="bf-preview-fit">'):page.rindex("</body>")], "") == saved


def test_bf_preview_takes_name_and_theme() -> None:
    preview = bf.preview(bf.Text("x"), name="Q1", formatting=bf.Formatting.dark())
    page = _inner(preview._repr_html_())
    assert "#0f172a" in page  # the dark theme's background
    assert find_one(parse(page), "title").get_text() == "Q1"
    assert attr(find_one(parse(preview._repr_html_()), "iframe"), "title") == "Q1 preview"


def test_preview_of_a_list_wraps_it() -> None:
    page = _inner(bf.preview([bf.Text("one"), bf.Text("two")])._repr_html_())
    assert [p.get_text() for p in parse(page).select(".bf-text p")] == ["one", "two"]


def test_preview_with_charts_is_offline() -> None:
    go = pytest.importorskip("plotly.graph_objects")
    check_no_external_urls(parse(bf.Plot(go.Figure())._repr_html_()))


def test_untrusted_notebooks_show_a_hint() -> None:
    # Sanitisers that strip the iframe keep its text: tell the reader how to see the preview.
    frame = find_one(parse(bf.Text("x")._repr_html_()), "iframe.bf-preview")
    assert "run this cell" in frame.get_text()


def test_preview_is_ascii_so_any_host_encoding_works() -> None:
    html = bf.BigNumber("Δ", "€ 4", change="+1%", is_upward_change=True)._repr_html_()
    assert html.isascii()
    inner = _inner(html)
    assert "▲ +1%" in inner and "€ 4" in inner and "Δ" in inner
