"""The opt-in export menu: bf.Briefing(..., export=("png", "pdf")) (#49)."""
from __future__ import annotations

import pytest

import briefing as bf
from tests.html_helpers import attr, find_one, parse

EXPORT_JS_MARKER = "briefing export menu"


def test_menu_lists_the_requested_actions_in_the_header() -> None:
    html = bf.stringify(bf.Briefing(bf.Text("x"), export=("png", "pdf")), name="Q1")
    menu = find_one(parse(html), ".bf-report__header .bf-export")
    buttons = menu.select("button.bf-export__btn")
    assert [attr(b, "data-export") for b in buttons] == ["png", "pdf"]
    assert [b.get_text() for b in buttons] == ["Save as PNG", "Print"]
    assert EXPORT_JS_MARKER in html


def test_one_action_and_a_single_string() -> None:
    soup = parse(bf.stringify(bf.Briefing(bf.Text("x"), export="pdf"), name="Q1"))
    assert [attr(b, "data-export") for b in soup.select(".bf-export button")] == ["pdf"]


def test_reports_without_export_contain_no_export_code() -> None:
    for report in (bf.Briefing(bf.Text("x")), bf.Briefing(bf.Text("x"), export=())):
        html = bf.stringify(report, name="Q1")
        assert "bf-export" not in html and EXPORT_JS_MARKER not in html


def test_menu_gets_a_header_even_with_the_default_name() -> None:
    soup = parse(bf.stringify(bf.Briefing(bf.Text("x"), export=("png",))))
    assert find_one(soup, ".bf-report__header .bf-export")


@pytest.mark.parametrize("bad", [("png", "gif"), ("svg",), 3])
def test_unknown_actions_raise(bad: object) -> None:
    with pytest.raises(bf.BriefingError, match="png.*pdf"):
        bf.Briefing(bf.Text("x"), export=bad)  # type: ignore[arg-type]


def test_export_is_kept_when_a_briefing_is_rewrapped() -> None:
    inner = bf.Briefing(bf.Text("x"), export=("pdf",))
    assert bf.Briefing(inner).export == ("pdf",)
    assert bf.Briefing.wrap(inner).export == ("pdf",)
