"""The copy-embed button, from Python's side: what a report with ``export=("embed",)`` carries (#124).

The browser side (copying, pasting, the dialog) is in ``tests/test_browser/test_copy_embed.py``.
"""
from __future__ import annotations

import base64
import gzip
import json
import re
import typing as t

import pandas as pd
import pytest
from bs4 import BeautifulSoup

import briefing as bf
from tests.golden import static_files
from tests.html_helpers import attr, find_one, parse

_DF = pd.DataFrame({"n": [3, 1, 2]})


def _report(**kwargs: t.Any) -> bf.Briefing:
    return bf.Briefing(
        bf.Page(
            bf.Text("# Summary {#top}\n\nSee [the rows](#detail/rows)."),
            bf.Group(bf.BigNumber("Revenue", "$4.2M"), bf.Alert("Low margin.", title="Heads up"), label="Numbers"),
            bf.Group(bf.Text("unlabelled group")),
            title="Summary",
            name="summary",
        ),
        bf.Page(
            bf.DataTable(_DF, name="rows"),
            bf.Table(_DF, caption="Raw"),
            bf.Code("x = 1"),
            bf.HTML("<b>raw</b>"),
            bf.Formula("x^2"),
            bf.Toggle(bf.Text("hidden"), label="More"),
            bf.Select(bf.Text("a", label="A"), bf.Text("b", label="B")),
            title="Detail",
            name="detail",
        ),
        **kwargs,
    )


def _payload(html: str) -> dict[str, t.Any]:
    script = find_one(parse(html), "script.bf-copy-data")
    data: dict[str, t.Any] = json.loads(gzip.decompress(base64.b64decode(json.loads(script.get_text()))))
    return data


def _marked(soup: BeautifulSoup) -> dict[str, str]:
    return {attr(el, "data-bf-embed-id"): attr(el, "data-bf-embed") for el in soup.select("[data-bf-embed]")}


def test_a_report_without_it_carries_nothing_of_it() -> None:
    html = bf.stringify(_report(export="png"))
    soup = parse(html)
    assert soup.select("[data-bf-embed], script.bf-copy-data, script[data-bf-runtime]") == []
    assert not any(attr(tag, "id").startswith("bf-r") for tag in soup.find_all(id=True))
    assert static_files()["static/copy-embed.js"] not in html
    assert static_files()["static/copy-embed.css"] not in html


def test_embed_alone_adds_no_menu_and_no_header() -> None:
    soup = parse(bf.stringify(_report(export="embed")))
    assert soup.select(".bf-export, .bf-report__header") == []


def test_buttons_go_on_pages_labelled_groups_and_content_blocks() -> None:
    labels = sorted(_marked(parse(bf.stringify(_report(export="embed")))).values())
    assert labels == sorted([
        "the Summary page", "Summary", "Numbers", "Revenue", "Heads up", "this text",  # its first heading, or none
        "the Detail page", "this table", "Raw", "this text", "A", "B",  # tabs by their labels
    ])  # not the Code, HTML or Formula, the Toggle, the Select or the unlabelled Group


def test_made_up_ids_start_with_the_reports_hash_and_links_keep_their_addresses() -> None:
    soup = parse(bf.stringify(_report(export="embed")))
    ids = [attr(tag, "id") for tag in soup.find_all(id=True)]
    links = {attr(tag, "id") for tag in soup.select("[data-bf-link]")}
    assert links == {"summary", "summary/top", "detail", "detail/rows"}
    prefixes = {re.match(r"bf-r[0-9a-f]{8}-", i).group() for i in ids if i not in links}  # type: ignore[union-attr]
    assert len(prefixes) == 1  # every made-up id, one prefix


def test_the_untouched_copy_is_the_reports_blocks_as_rendered() -> None:
    html = bf.stringify(_report(export="embed"), name="Q1")
    data = _payload(html)
    start = html.index('<div class="bf-blocks">')
    assert html[start:start + len(data["body"])] == data["body"]
    assert data["version"] == bf.__version__
    assert re.fullmatch(r"bf-r[0-9a-f]{8}-", data["prefix"]) and data["prefix"] in data["body"]
    assert len(data["blocks"]) == len(_marked(parse(html)))
    scripts = [s.get_text() for s in parse(html).select("script[data-bf-script]")]
    assert scripts[0] == static_files()["static/report.js"]
    assert data["theme"].lstrip().startswith(f"#{data['token']} {{")
    assert data["footer"] == f"Made with briefing {bf.__version__}"


def test_each_block_names_the_runtimes_and_scripts_it_needs() -> None:
    go = pytest.importorskip("plotly.graph_objects")
    dive = bf.lab.DataDive(pd.DataFrame({"x": [1.0, 2.0], "y": [2.0, 1.0]}))
    html = bf.stringify(bf.Briefing(bf.Plot(go.Figure(go.Scatter(x=[1], y=[1]))), dive, export="embed"))
    blocks = _payload(html)["blocks"]
    scripts = [s.get_text() for s in parse(html).select("script[data-bf-script]")]
    assert [b["runtimes"] for b in blocks] == [["Plotly"], []]
    assert [[scripts[i] for i in b["scripts"]] for b in blocks] == [
        [static_files()["static/report.js"]],
        [static_files()["static/report.js"], static_files()["lab/static/lab.js"]],
    ]
    assert find_one(parse(html), 'script[data-bf-runtime="Plotly"]')


def test_fragments_never_carry_it() -> None:
    soup = parse(bf.stringify(_report(export="embed"), full_html=False))
    assert soup.select("[data-bf-embed], script.bf-copy-data") == []


def test_the_copy_is_the_same_bytes_every_time() -> None:
    assert bf.stringify(_report(export="embed")) == bf.stringify(_report(export="embed"))
