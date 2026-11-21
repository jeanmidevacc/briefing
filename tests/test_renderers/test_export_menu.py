"""The opt-in export menu: bf.Briefing(..., export="png") (#49, #119)."""
from __future__ import annotations

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
