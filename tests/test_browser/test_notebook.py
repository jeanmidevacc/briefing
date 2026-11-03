"""Two notebook previews on one page stay independent (#12)."""
from __future__ import annotations

import pytest
from playwright.sync_api import expect

import briefing as bf
from tests.test_browser.conftest import Viewer


def _notebook_page(*reports: bf.Briefing) -> str:
    """A host page holding each report's notebook preview, the way Jupyter inserts outputs."""
    cells = "".join(f'<div class="cell">{r._repr_html_()}</div>' for r in reports)  # type: ignore[attr-defined]
    return f'<!DOCTYPE html><html><head><title>notebook</title></head><body><p id="host">cell</p>{cells}</body></html>'


@pytest.mark.xfail(reason="#12: blocks have no isolated _repr_html_ preview yet", strict=True)
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


@pytest.mark.xfail(reason="#12: blocks have no isolated _repr_html_ preview yet", strict=True)
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
