"""The docs' live examples (docs/_static/briefing-example.js) fit their frame without a feedback loop.

A frame is sized to its report's height. A scrollbar inside it would narrow the report, and a
calendar, which fits its width, would then change height and resize the frame, over and over:
the whole docs page shook in some browsers. So a frame never shows a scrollbar.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
from playwright.sync_api import Page, Route

import briefing as bf

ROOT = Path(__file__).resolve().parents[2]
HOST = "http://docs.test"


def _serve(page: Page, files: dict[str, str]) -> None:
    def handle(route: Route) -> None:
        name = route.request.url.removeprefix(HOST + "/")
        if name in files:
            route.fulfill(status=200, body=files[name], content_type="text/html" if name.endswith(".html")
                          else "application/javascript")
        else:
            route.abort()

    page.route(HOST + "/**", handle)


def test_a_preview_has_no_scrollbar_and_fits_its_calendar(page: Page) -> None:
    days = pd.DataFrame({"day": pd.date_range("2026-01-01", periods=200, freq="D"), "n": range(200)})
    report = bf.stringify(bf.lab.CalendarHeatmap(days, date="day", value="n"), name="Calendar")
    host = ('<!doctype html><html><body style="margin:0">'
            '<iframe class="bf-example__frame" src="cal.html" style="width:810px;height:360px;border:0"></iframe>'
            '<script src="briefing-example.js"></script></body></html>')
    _serve(page, {"host.html": host, "cal.html": report,
                  "briefing-example.js": (ROOT / "docs" / "_static" / "briefing-example.js").read_text()})
    page.goto(f"{HOST}/host.html")
    frame = page.locator("iframe")
    page.wait_for_function("() => document.querySelector('iframe').style.height !== '360px'")
    inner = frame.evaluate("""f => { const d = f.contentDocument; return {
        overflow: getComputedStyle(d.documentElement).overflow, width: d.documentElement.clientWidth,
        content: d.body.offsetHeight, frame: f.clientHeight }; }""")
    assert inner["overflow"] == "hidden"  # no scrollbar can appear and narrow the report
    assert inner["width"] == 810
    assert abs(inner["frame"] - inner["content"]) <= 1
