"""The report header with a bf.Header (#25), as a reader sees it: desktop and phone width."""
from __future__ import annotations

import typing as t

import briefing as bf
from tests.banner_images import RED_SVG
from tests.test_browser.conftest import Viewer


def _open(viewer: Viewer, width: int) -> t.Any:
    header = bf.Header(subtitle="Weekly search interest, **worldwide** and US", author="Analytics team",
                       logo=RED_SVG, as_of="2026-11-20", tz="America/Montreal")
    page = viewer.open(bf.Briefing(bf.Text("Body"), header=header, export="png"), name="Search report")
    page.set_viewport_size({"width": width, "height": 700})
    return page


def _box(page: t.Any, selector: str) -> dict[str, float]:
    return t.cast("dict[str, float]", page.locator(selector).evaluate(
        "e => { const r = e.getBoundingClientRect(); return {left: r.left, right: r.right, top: r.top,"
        " bottom: r.bottom, width: r.width, height: r.height}; }"))


def test_desktop_puts_the_logo_and_heading_left_and_the_dates_right(viewer: Viewer) -> None:
    page = _open(viewer, 1200)
    logo, heading, asof, date = (_box(page, s) for s in (".bf-report__logo", ".bf-report__heading",
                                                           ".bf-report__asof", ".bf-report__date"))
    assert logo["height"] <= 36.5 and logo["width"] <= 128.5
    assert logo["right"] <= heading["left"] < asof["left"] < date["left"]
    subtitle, title = _box(page, ".bf-report__subtitle"), _box(page, ".bf-report__title")
    assert subtitle["top"] >= title["bottom"] - 1  # the subtitle sits under the title


def test_phone_width_stacks_without_scrolling_sideways(viewer: Viewer) -> None:
    page = _open(viewer, 360)
    heading, date = _box(page, ".bf-report__heading"), _box(page, ".bf-report__date")
    assert date["top"] >= heading["bottom"] - 1
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
