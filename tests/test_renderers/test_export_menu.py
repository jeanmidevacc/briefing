"""The opt-in export menu: bf.Briefing(..., export="png") (#49, #119)."""
from __future__ import annotations

import pandas as pd
import pytest

import briefing as bf
from tests.html_helpers import attr, find_one, parse

EXPORT_JS_MARKER = "briefing export menu"


def test_menu_lists_the_requested_actions_in_the_header() -> None:
    html = bf.stringify(bf.Briefing(bf.Text("x"), export=("png",)), name="Q1")
    menu = find_one(parse(html), ".bf-report__header .bf-export")
    buttons = menu.select("button.bf-export__btn")
    assert [attr(b, "data-export") for b in buttons] == ["png"]
    assert [b.get_text() for b in buttons] == ["Save as PNG"]
    assert EXPORT_JS_MARKER in html


def test_a_single_string_works() -> None:
    soup = parse(bf.stringify(bf.Briefing(bf.Text("x"), export="png"), name="Q1"))
    assert [attr(b, "data-export") for b in soup.select(".bf-export button")] == ["png"]


def test_reports_without_export_contain_no_export_code() -> None:
    for report in (bf.Briefing(bf.Text("x")), bf.Briefing(bf.Text("x"), export=())):
        html = bf.stringify(report, name="Q1")
        assert "bf-export" not in html and EXPORT_JS_MARKER not in html


def test_menu_gets_a_header_even_with_the_default_name() -> None:
    soup = parse(bf.stringify(bf.Briefing(bf.Text("x"), export=("png",))))
    assert find_one(soup, ".bf-report__header .bf-export")


@pytest.mark.parametrize("bad", [("png", "gif"), ("svg",), "print", 3])
def test_unknown_actions_raise(bad: object) -> None:
    with pytest.raises(bf.BriefingError, match="export accepts 'png'"):
        bf.Briefing(bf.Text("x"), export=bad)  # type: ignore[arg-type]


def test_export_is_kept_when_a_briefing_is_rewrapped() -> None:
    inner = bf.Briefing(bf.Text("x"), export=("png",))
    assert bf.Briefing(inner).export == ("png",)
    assert bf.Briefing.wrap(inner).export == ("png",)


# ── export="pdf": the "Print" button is gone (removed in 0.4.0, tests/test_deprecations.py) ──


def test_there_is_only_a_save_as_png_button() -> None:
    soup = parse(bf.stringify(bf.Briefing(bf.Text("x"), export="png"), name="Q1"))
    assert [b.get_text() for b in soup.select(".bf-export button")] == ["Save as PNG"]


# ── export="snapshot": a camera button on each block (#215) ──


def _snapshot_report(*export: str) -> bf.Briefing:
    return bf.Briefing(
        bf.Page(
            bf.Text("# Summary"),
            bf.Group(bf.BigNumber("Revenue", "$4.2M"), label="Numbers"),
            bf.Group(bf.Text("plain")),
            title="Summary",
        ),
        bf.Page(bf.Table(pd.DataFrame({"n": [1]})), title="Detail"),
        export=export,
    )


def test_snapshot_marks_the_blocks_that_copy_embed_would() -> None:
    snap = parse(bf.stringify(_snapshot_report("snapshot"), name="Q1"))
    embed = parse(bf.stringify(_snapshot_report("embed"), name="Q1"))
    labels = [attr(el, "data-bf-snap") for el in snap.select("[data-bf-snap]")]
    assert labels == [attr(el, "data-bf-embed") for el in embed.select("[data-bf-embed]")]
    assert labels == ["the Summary page", "Summary", "Numbers", "Revenue", "this text", "the Detail page",
                      "this table"]


def test_snapshot_alone_ships_the_script_but_no_menu_or_embed_data() -> None:
    html = bf.stringify(_snapshot_report("snapshot"), name="Q1")
    soup = parse(html)
    assert EXPORT_JS_MARKER in html
    assert soup.select(".bf-export, [data-bf-embed], script.bf-copy-data") == []
    assert any(".bf-copy__tools {" in style.get_text() for style in soup.select("style"))


def test_snapshot_and_embed_mark_the_same_blocks() -> None:
    soup = parse(bf.stringify(_snapshot_report("embed", "snapshot"), name="Q1"))
    snapped = soup.select("[data-bf-snap]")
    assert snapped and snapped == soup.select("[data-bf-embed]")


def test_reports_without_snapshot_have_no_snapshot_marks() -> None:
    for export in ((), ("png",), ("embed",)):
        html = bf.stringify(_snapshot_report(*export), name="Q1")
        assert parse(html).select("[data-bf-snap]") == []
        assert (EXPORT_JS_MARKER in html) == ("png" in export)
