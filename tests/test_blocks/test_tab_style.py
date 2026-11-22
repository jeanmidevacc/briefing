"""TabStyle: how page tabs and a Select's tabs look (#22)."""
from __future__ import annotations

import typing as t
import warnings

import pytest

import briefing as bf
from tests.html_helpers import classes, find_one, parse


def _pages(**kwargs: t.Any) -> bf.Briefing:
    return bf.Briefing(bf.Page("a", title="A"), bf.Page("b", title="B"), **kwargs)


def _select_classes(html: str) -> list[list[str]]:
    return [classes(s) for s in parse(html).select("div.bf-select")]


def test_the_defaults_add_no_class() -> None:
    assert bf.TabStyle().classes() == ""
    assert bf.TabStyle().to_dict() == {}
    plain, styled = bf.stringify(_pages()), bf.stringify(_pages(tabs=bf.TabStyle()))
    assert plain == styled


@pytest.mark.parametrize(("options", "expected"), [
    ({"layout": "center"}, ["bf-tabs--center"]),
    ({"layout": "stretch"}, ["bf-tabs--stretch"]),
    ({"size": "sm"}, ["bf-tabs--sm"]),
    ({"size": "lg", "variant": "boxed"}, ["bf-tabs--lg", "bf-tabs--boxed"]),
    ({"variant": "pills"}, ["bf-tabs--pills"]),
    ({"full_width": True, "sticky": True}, ["bf-tabs--full", "bf-tabs--sticky"]),
])
def test_each_option_is_a_class_on_the_page_tabs(options: dict[str, t.Any], expected: list[str]) -> None:
    (page_tabs,) = _select_classes(bf.stringify(_pages(tabs=bf.TabStyle(**options))))
    assert [c for c in page_tabs if c.startswith("bf-tabs--")] == expected


def test_a_select_style_stays_on_that_select() -> None:
    inner = bf.Select(bf.Text("x", label="X"), bf.Text("y", label="Y"), style=bf.TabStyle(variant="pills"))
    outer = bf.Select(bf.Group(inner, label="One"), bf.Text("z", label="Two"))
    outer_classes, inner_classes = _select_classes(bf.stringify(bf.Briefing(outer)))
    assert "bf-tabs--pills" in inner_classes and not any(c.startswith("bf-tabs--") for c in outer_classes)


def test_a_dict_is_the_same_style() -> None:
    assert bf.Select(bf.Text("x", label="X"), bf.Text("y", label="Y"), style={"layout": "center"}).style == \
        bf.TabStyle(layout="center")
    assert _pages(tabs={"sticky": True}).tabs == bf.TabStyle(sticky=True)


@pytest.mark.parametrize(("options", "match"), [
    ({"layout": "wide"}, r"layout must be one of 'start', 'center', 'stretch', not 'wide'"),
    ({"size": "xl"}, r"size must be one of 'sm', 'md', 'lg'"),
    ({"variant": "tabs"}, r"variant must be one of 'underline', 'pills', 'boxed'"),
    ({"sticky": "yes"}, r"sticky must be True or False"),
    ({"full_width": 1}, r"full_width must be True or False"),
])
def test_bad_options_say_what_to_pass(options: dict[str, t.Any], match: str) -> None:
    with pytest.raises(bf.BriefingError, match=match):
        bf.TabStyle(**options)


def test_bad_dicts_and_values() -> None:
    with pytest.raises(bf.BriefingError, match=r"TabStyle has no option 'align'; it takes layout, full_width"):
        _pages(tabs={"align": "center"})
    with pytest.raises(bf.BriefingError, match=r"takes a bf.TabStyle\(...\) or a dict of its options, not 'stretch'"):
        _pages(tabs="stretch")


def test_a_dropdown_takes_no_tab_style() -> None:
    with pytest.raises(bf.BriefingError, match="this Select is a dropdown"):
        bf.Select(bf.Text("x", label="X"), bf.Text("y", label="Y"), type="dropdown", style=bf.TabStyle())


def test_page_tabs_need_pages() -> None:
    with pytest.raises(bf.BriefingError, match=r"has no Page.*Select\(style=...\)"):
        bf.Briefing(bf.Text("x"), tabs=bf.TabStyle(layout="center"))


def test_rewrapping_a_report_keeps_its_tab_style() -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        report = bf.Briefing(_pages(tabs=bf.TabStyle(size="lg")))
    assert report.tabs == bf.TabStyle(size="lg")
    assert "bf-tabs--lg" in classes(find_one(parse(bf.stringify(report)), "div.bf-select"))


def test_the_json_form_keeps_only_what_differs() -> None:
    report = _pages(tabs=bf.TabStyle(layout="stretch", sticky=True))
    spec, data = bf.to_spec(report)
    assert spec["tabs"] == {"layout": "stretch", "sticky": True}
    assert bf.stringify(bf.from_spec(spec, data)) == bf.stringify(report)
    assert "tabs" not in bf.to_spec(_pages())[0]
