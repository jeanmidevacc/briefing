"""TabStyle as a reader sees it (#22): layouts, a sticky bar, a full-width line, variants, phone width."""
from __future__ import annotations

import typing as t

import pytest
from playwright.sync_api import Page

import briefing as bf
from tests.test_browser.conftest import Viewer

_FILLER = [bf.Text(f"Paragraph {i}. " * 40) for i in range(20)]


def _open(viewer: Viewer, width: int = 1200, **style: t.Any) -> Page:
    pages = [bf.Page(*_FILLER, title=title) for title in ("Overview", "Regional detail", "Method")]
    page = viewer.open(bf.Briefing(*pages, tabs=bf.TabStyle(**style)))
    page.set_viewport_size({"width": width, "height": 600})
    return page


def _boxes(page: Page) -> list[dict[str, float]]:
    return t.cast("list[dict[str, float]]", page.locator(".bf-select__tablist").first.evaluate(
        "l => Array.from(l.children).map(b => { const r = b.getBoundingClientRect();"
        " return {left: r.left, right: r.right, width: r.width}; })"))


def _list_box(page: Page) -> dict[str, float]:
    return t.cast("dict[str, float]", page.locator(".bf-select__tablist").first.evaluate(
        "l => { const r = l.getBoundingClientRect(); return {left: r.left, right: r.right, top: r.top}; }"))


def test_stretch_shares_the_line_equally(viewer: Viewer) -> None:
    page = _open(viewer, layout="stretch")
    tabs, line = _boxes(page), _list_box(page)
    widths = {round(b["width"]) for b in tabs}
    assert len(widths) == 1 and abs(tabs[0]["left"] - line["left"]) < 1 and abs(tabs[-1]["right"] - line["right"]) < 1


def test_center_centres_the_tabs(viewer: Viewer) -> None:
    page = _open(viewer, layout="center")
    tabs, line = _boxes(page), _list_box(page)
    assert abs((tabs[0]["left"] - line["left"]) - (line["right"] - tabs[-1]["right"])) < 1.5


def test_sticky_keeps_the_bar_at_the_top(viewer: Viewer) -> None:
    for sticky in (True, False):
        page = _open(viewer, sticky=sticky)
        page.evaluate("window.scrollTo(0, 1500)")
        assert page.evaluate("scrollY") > 500
        top = _list_box(page)["top"]
        assert abs(top) < 1 if sticky else top < -300  # without sticky, the bar scrolls away


def test_full_width_reaches_the_edges_without_a_sideways_scroll(viewer: Viewer) -> None:
    page = _open(viewer, width=1600, full_width=True, sticky=True)
    line = _list_box(page)
    assert line["left"] > 100  # the tabs stay aligned with the content
    shadow = page.locator(".bf-select__tablist").first.evaluate("l => getComputedStyle(l, '::after').boxShadow")
    assert shadow != "none"
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")


@pytest.mark.parametrize("variant", ["pills", "boxed"])
def test_variants_mark_the_active_tab(viewer: Viewer, variant: str) -> None:
    page = _open(viewer, variant=variant)
    active, other = (page.locator(".bf-select__tab").nth(i).evaluate(
        "b => { const s = getComputedStyle(b); return [s.backgroundColor, s.borderTopColor]; }") for i in (0, 1))
    assert active != other


@pytest.mark.parametrize("style", [{"layout": "stretch", "size": "lg"}, {"full_width": True, "sticky": True},
                                   {"variant": "boxed", "layout": "center"}])
def test_phone_width_stays_usable(viewer: Viewer, style: dict[str, t.Any]) -> None:
    page = _open(viewer, width=360, **style)
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    page.get_by_role("tab", name="Method").click()
    assert page.get_by_role("tab", name="Method").get_attribute("aria-selected") == "true"
