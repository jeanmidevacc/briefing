"""Two notebook previews on one page stay independent (#12)."""
from __future__ import annotations

from playwright.sync_api import expect

import briefing as bf
from tests.test_browser.conftest import Viewer


def _notebook_page(*reports: bf.Block | bf.Preview) -> str:
    """A host page holding each report's notebook preview, the way Jupyter inserts outputs."""
    cells = "".join(f'<div class="cell">{r._repr_html_()}</div>' for r in reports)
    return f'<!DOCTYPE html><html><head><title>notebook</title></head><body><p id="host">cell</p>{cells}</body></html>'


def test_previews_are_isolated(viewer: Viewer) -> None:
    first = bf.Briefing(bf.Toggle(bf.Text("first body"), label="First"))
    second = bf.Briefing(bf.Toggle(bf.Text("second body"), label="Second"))
    page = viewer.open(_notebook_page(first, second))

    # The report CSS must not reach the notebook page itself.
    assert page.locator("#host").evaluate("e => getComputedStyle(e).marginTop") == "16px"

    frames = page.frame_locator("iframe")
    frames.nth(1).get_by_role("button", name="Second").click()
    expect(frames.nth(1).get_by_text("second body")).to_be_visible()
    expect(frames.nth(0).get_by_text("first body")).to_be_hidden()


def test_preview_grows_when_a_toggle_opens(viewer: Viewer) -> None:
    report = bf.Briefing(bf.Toggle(bf.Text("a\n\nb\n\nc\n\nd\n\ne"), label="More"))
    page = viewer.open(_notebook_page(report))
    iframe = page.locator("iframe").first
    before = iframe.bounding_box()
    page.frame_locator("iframe").first.get_by_role("button", name="More").click()
    page.wait_for_timeout(300)
    after = iframe.bounding_box()
    assert before is not None and after is not None
    assert after["height"] > before["height"] + 50


def test_previews_with_different_themes_stay_independent(viewer: Viewer) -> None:
    light = bf.preview(bf.Text("light"))
    dark = bf.preview(bf.Text("dark"), formatting=bf.Formatting.dark())
    page = viewer.open(_notebook_page(light, dark))
    host = page.evaluate("() => getComputedStyle(document.body).backgroundColor")
    frames = [page.frames[1], page.frames[2]]
    assert [f.evaluate("() => getComputedStyle(document.body).backgroundColor") for f in frames] == [
        "rgb(255, 255, 255)",
        "rgb(15, 23, 42)",
    ]
    assert host == "rgba(0, 0, 0, 0)"  # the notebook page keeps its own (default) background
    assert page.locator("#host").evaluate("e => getComputedStyle(e).fontFamily") != frames[0].locator(
        ".bf-text p"
    ).evaluate("e => getComputedStyle(e).fontFamily")


def test_preview_fits_its_content_without_scrolling(viewer: Viewer) -> None:
    page = viewer.open(_notebook_page(bf.Briefing(bf.Text("# Title\n\nsome text"))))
    page.wait_for_timeout(300)
    frame = page.frames[1]
    inner = frame.evaluate("() => document.documentElement.getBoundingClientRect().height")
    outer = page.locator("iframe").first.bounding_box()
    assert outer is not None and abs(outer["height"] - inner) <= 2
