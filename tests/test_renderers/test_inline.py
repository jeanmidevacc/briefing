"""Inline Markdown in captions, alert titles and messages, and BigNumber headings (#26)."""
from __future__ import annotations

import typing as t

import pandas as pd
import pytest

import briefing as bf
from briefing.renderers.inline import inline_markdown, inline_plain
from tests.banner_images import RED_SVG
from tests.html_helpers import attr, find_one, parse


def _figure() -> t.Any:
    go = pytest.importorskip("plotly.graph_objects")
    return go.Figure()


TEXT = "Revenue **in $k**, *net*, `code` and [source](https://example.org)"


@pytest.mark.parametrize(("source", "html"), [
    ("**bold** and __bold__", "<strong>bold</strong> and <strong>bold</strong>"),
    ("*it* and _it_", "<em>it</em> and <em>it</em>"),
    ("`a < b`", "<code>a &lt; b</code>"),
    ("[docs](https://example.org)", '<a href="https://example.org">docs</a>'),
    ("<https://example.org>", '<a href="https://example.org">https://example.org</a>'),
    ("p_value_adj", "p_value_adj"),  # underscores inside a word are no emphasis
    ("\\*kept\\*", "*kept*"),
    ("a\nb", "a b"),
    ("a  \nb", "a b"),  # a hard break too: these fields are one line
    ("**  \n", "**"),
])
def test_inline_markdown(source: str, html: str) -> None:
    assert inline_markdown(source) == html


@pytest.mark.parametrize("source", ["# Title", "- item", "1. item", "> quote", "| a | b |"])
def test_block_syntax_stays_text(source: str) -> None:
    assert inline_markdown(source) == source.replace(">", "&gt;")


def test_raw_html_stays_escaped() -> None:
    assert inline_markdown('<b onclick="x()">hi</b>') == "&lt;b onclick=&quot;x()&quot;&gt;hi&lt;/b&gt;"


@pytest.mark.parametrize("url", ["javascript:alert(1)", "vbscript:x", "data:text/html,x", "file:///etc/passwd"])
def test_unsafe_links_are_no_links(url: str) -> None:
    assert "<a" not in inline_markdown(f"[click]({url})")


def test_images_stay_text() -> None:
    assert inline_markdown("![logo](https://example.org/logo.png)") == "![logo](https://example.org/logo.png)"


def test_plain_text_drops_the_markup() -> None:
    assert inline_plain(TEXT) == "Revenue in $k, net, code and source"
    assert inline_plain("<b>&amp;</b>") == "<b>&</b>"


def _first(html: str, selector: str) -> t.Any:
    return find_one(parse(html), selector)


@pytest.mark.parametrize(("block", "selector"), [
    (lambda: bf.Plot(_figure(), caption=TEXT), ".bf-plot__caption"),
    (lambda: bf.Table(pd.DataFrame({"a": [1]}), caption=TEXT), ".bf-table__caption"),
    (lambda: bf.DataTable(pd.DataFrame({"a": [1]}), caption=TEXT), ".bf-dt__caption"),
    (lambda: bf.Image(RED_SVG, caption=TEXT), ".bf-image__caption"),
    (lambda: bf.Code("x = 1", caption=TEXT), ".bf-code__caption"),
    (lambda: bf.Alert(TEXT), ".bf-alert__message"),
    (lambda: bf.Alert("m", title=TEXT), ".bf-alert__title"),
    (lambda: bf.BigNumber(TEXT, 42), ".bf-bignumber__heading"),
])
def test_each_field_renders_inline_markdown(block: t.Callable[[], bf.Block], selector: str) -> None:
    field = _first(bf.stringify(bf.Briefing(block())), selector)
    assert field.find("strong").get_text() == "in $k" and field.find("em").get_text() == "net"
    assert field.find("code").get_text() == "code"
    assert attr(field.find("a"), "href") == "https://example.org"


def test_formula_caption() -> None:
    field = _first(bf.stringify(bf.Briefing(bf.Formula("x^2", caption="**Area**"))), ".bf-formula__caption")
    assert field.find("strong").get_text() == "Area"


def test_an_image_alt_from_its_caption_is_plain_text() -> None:
    img = _first(bf.stringify(bf.Briefing(bf.Image(RED_SVG, caption=TEXT))), "img.bf-image__img")
    assert attr(img, "alt") == "Revenue in $k, net, code and source"


def test_the_copy_embed_label_and_csv_name_are_plain_text() -> None:
    table = bf.DataTable(pd.DataFrame({"a": [1]}), caption="**Sales** by `region`", download=True)
    soup = parse(bf.stringify(bf.Briefing(table, export="embed")))
    assert attr(find_one(soup, "[data-bf-embed]"), "data-bf-embed") == "Sales by region"
    assert attr(find_one(soup, ".bf-dt__csv"), "data-bf-filename") == "sales-by-region.csv"
