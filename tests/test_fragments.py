"""Fragments from Python: ``bf.stringify(..., full_html=False)`` and ``bf.embed_assets`` (#122).

The fragment contract (``FRAGMENT_RULES`` in ``tests/contract.py``) runs over every
scenario of ``tests/scenarios.py``: no ``<html>``, ``<head>`` or ``<body>``, every
CSS selector and every id starting at the fragment, offline, escaped, unique ids.
Full reports are covered by the golden snapshots, which this work must not change.
"""
from __future__ import annotations

import re
import typing as t
from pathlib import Path

import pandas as pd
import pytest
from bs4 import BeautifulSoup

import briefing as bf
from briefing.renderers.fragment import embed_css
from tests.contract import (
    FRAGMENT_RULES,
    MARKER,
    check_deterministic,
    check_user_text_escaped,
    css_selectors,
    fragment_root,
    parse_report,
)
from tests.golden import static_files
from tests.html_helpers import attr, find_one
from tests.scenarios import ESCAPE_SCENARIOS, HOUR_VIEW_WARNING, SCENARIOS, Frames

pytestmark = pytest.mark.filterwarnings(HOUR_VIEW_WARNING)

_parsed: dict[str, BeautifulSoup] = {}


def _fragment(scenario: str, frames: Frames) -> BeautifulSoup:
    if scenario not in _parsed:
        _parsed[scenario] = parse_report(bf.stringify(SCENARIOS[scenario](frames), full_html=False))
    return _parsed[scenario]


@pytest.mark.parametrize("rule", list(FRAGMENT_RULES))
@pytest.mark.parametrize("scenario", list(SCENARIOS))
def test_fragment_follows_rule(rule: str, scenario: str, frames: Frames) -> None:
    FRAGMENT_RULES[rule](_fragment(scenario, frames))


@pytest.mark.parametrize("scenario", list(SCENARIOS))
def test_fragment_is_deterministic(scenario: str, frames: Frames) -> None:
    check_deterministic(lambda: bf.stringify(SCENARIOS[scenario](frames), full_html=False))


@pytest.mark.parametrize("scenario", list(ESCAPE_SCENARIOS))
def test_user_text_stays_escaped_in_a_fragment(scenario: str) -> None:
    report, name = ESCAPE_SCENARIOS[scenario]()
    soup = parse_report(bf.stringify(report, name=name, full_html=False, header=True))
    check_user_text_escaped(soup)
    assert MARKER in soup.get_text()


# ── the fragment ──────────────────────────────────────────────────────────────


def _soup(blocks: t.Any, **kwargs: t.Any) -> BeautifulSoup:
    return parse_report(bf.stringify(blocks, full_html=False, **kwargs))


def test_a_fragment_is_one_div_that_initialises_itself() -> None:
    html = bf.stringify(bf.Text("# Hello", name="hello"), full_html=False)
    assert html.startswith(f"<!-- briefing {bf.__version__} embed: hello -->\n")
    root = fragment_root(parse_report(html))
    assert attr(root, "id") == "hello"
    scripts = root.find_all("script")
    assert scripts[-1].get_text() == 'briefing.init(document.getElementById("hello"));'
    assert root.select(":scope > .bf-embed__body") and root.select(":scope > .bf-embed__footer")
    assert find_one(root, ".bf-embed__footer").get_text() == f"Made with briefing {bf.__version__}"


def test_the_embed_id_comes_from_a_name_else_a_hash() -> None:
    assert attr(fragment_root(_soup(bf.Text("x", name="intro"))), "id") == "intro"
    assert attr(fragment_root(_soup(bf.Text("x", name="intro"), embed_id="mine")), "id") == "mine"
    hashed = attr(fragment_root(_soup([bf.Text("x"), bf.Text("y")])), "id")
    assert re.fullmatch(r"bf-e[0-9a-f]{8}", hashed)
    assert attr(fragment_root(_soup([bf.Text("x"), bf.Text("y")])), "id") == hashed  # the same input, the same id
    dark = attr(fragment_root(_soup([bf.Text("x"), bf.Text("y")], formatting=bf.Formatting.dark())), "id")
    assert dark != hashed  # so a light and a dark copy can share a page


def test_ids_inside_start_with_the_embed_id() -> None:
    soup = _soup(bf.Briefing(bf.Select(bf.Text("## Notes {#notes}", label="A", name="a"), bf.Text("b", label="B"))),
                 embed_id="rev")
    ids = [attr(tag, "id") for tag in soup.find_all(id=True)]
    assert ids[0] == "rev" and all(i.startswith("rev-") for i in ids[1:])
    assert {"rev-a", "rev-a/notes"} <= set(ids)  # links: page/name under the prefix


def test_the_theme_sits_on_the_fragment() -> None:
    soup = _soup(bf.Text("x", name="dark"), formatting=bf.Formatting.dark())
    sheets = [s.get_text() for s in soup.find_all("style")]
    assert any(s.lstrip().startswith("#dark {") and "#0f172a" in s for s in sheets)


def test_without_assets_only_the_theme_and_the_init_call_remain() -> None:
    soup = _soup(bf.Plot(_plotly(), name="chart"), include_assets=False)
    assert [s.get_text().lstrip()[:7] for s in soup.find_all("style")] == ["#chart "]
    scripts = [s.get_text() for s in soup.find_all("script")]
    assert scripts[-1] == 'briefing.init(document.getElementById("chart"));'
    assert [s for s in scripts if "window.briefing" in s or "window.Plotly)" in s] == []  # Plotly's figure call stays


def test_with_assets_the_fragment_brings_its_css_scripts_and_runtimes() -> None:
    soup = _soup(bf.Plot(_plotly(), name="chart"))
    scripts = " ".join(s.get_text() for s in soup.find_all("script"))
    assert static_files()["static/report.js"] in scripts
    assert "if (!window.Plotly) (function (script, here) {" in scripts  # packed, unpacked once (#38)
    assert embed_css() in " ".join(s.get_text() for s in soup.find_all("style"))


def test_a_header_shows_the_name_only_when_asked() -> None:
    assert _soup(bf.Text("x"), name="Q1").find(class_="bf-report__header") is None
    header = find_one(_soup(bf.Text("x"), name="Q1", header=True), ".bf-report__header")
    assert find_one(header, ".bf-report__title").get_text() == "Q1"


def test_fragments_never_carry_the_export_menu() -> None:
    soup = _soup(bf.Briefing(bf.Text("x"), export="png"), header=True)
    assert soup.find(class_="bf-export") is None
    assert static_files()["static/export.js"] not in str(soup)


def test_a_styled_table_keeps_its_ids_and_selectors_inside() -> None:
    styled = pd.DataFrame({"a": [1, 3]}).style.highlight_max()
    soup = _soup(bf.Table(styled), embed_id="tbl")
    assert any(attr(cell, "id").startswith("tbl-table-") for cell in soup.select("td[id]"))
    selectors = [s for sheet in soup.find_all("style") for s in css_selectors(sheet.get_text())]
    assert any(s.startswith("#tbl-table-") for s in selectors)


def test_save_writes_a_fragment(tmp_path: Path) -> None:
    path = tmp_path / "embed.html"
    bf.save(bf.Text("x", name="saved"), str(path), full_html=False)
    assert attr(fragment_root(parse_report(path.read_text(encoding="utf-8"))), "id") == "saved"


# ── embed_assets and the options' checks ──────────────────────────────────────


def test_embed_assets_holds_what_the_blocks_need_once() -> None:
    dive = bf.lab.DataDive(pd.DataFrame({"x": [1.0, 2.0], "y": [2.0, 1.0]}))
    head = bf.embed_assets([bf.Plot(_plotly()), dive, bf.Text("x")])
    assert head.startswith(f"<!-- briefing {bf.__version__} embed assets -->\n")
    assert head.count("if (!window.Plotly)") == 1
    assert static_files()["lab/static/lab.js"] in head
    assert "lab/static/calendar.js" not in head and static_files()["lab/static/calendar.js"] not in head
    assert bf.embed_assets(bf.Text("x")).count("<script>") == 1  # report.js alone


@pytest.mark.parametrize(
    "options", [{"include_assets": False}, {"embed_id": "x"}, {"header": True}], ids=lambda o: next(iter(o))
)
def test_fragment_options_need_full_html_false(options: dict[str, t.Any]) -> None:
    with pytest.raises(bf.BriefingError, match="only apply to a fragment"):
        bf.stringify(bf.Text("x"), **options)


@pytest.mark.parametrize("embed_id", ["9lives", "has space", "quote\"", ""])
def test_an_embed_id_must_be_a_valid_name(embed_id: str) -> None:
    if not embed_id:  # empty means "not given"
        assert bf.stringify(bf.Text("x"), full_html=False, embed_id=embed_id)
        return
    with pytest.raises(bf.BriefingError, match="Invalid embed_id"):
        bf.stringify(bf.Text("x"), full_html=False, embed_id=embed_id)


def test_the_scoped_stylesheet_reaches_nothing_outside() -> None:
    loose = [s for s in css_selectors(embed_css()) if not re.match(r"\.bf-embed(?![\w-])", s)]
    assert loose == []
    assert "@page" not in embed_css()
    assert not re.search(r"\d+rem\b", embed_css())


def _plotly() -> t.Any:
    go = pytest.importorskip("plotly.graph_objects")
    return go.Figure(go.Scatter(x=[1, 2, 3], y=[3, 1, 2]))


def test_links_written_with_the_reports_names_point_inside_the_fragment() -> None:
    linked = bf.Briefing(
        bf.Page(bf.Text("See [the method](#detail/methodology) or [the host](#elsewhere)."), title="One"),
        bf.Page(bf.Text("## Methodology {#methodology}"), title="Detail", name="detail"),
    )
    hrefs = [attr(a, "href") for a in _soup(linked, embed_id="doc").select(".bf-text p a")]
    assert hrefs == ["#doc-detail/methodology", "#elsewhere"]
