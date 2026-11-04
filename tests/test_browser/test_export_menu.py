"""The in-report export menu works in Chromium (#49)."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
from playwright.sync_api import Page

import briefing as bf
from tests.image_helpers import png_size
from tests.pdf_reader import read_pdf
from tests.test_browser.conftest import Viewer


def _report() -> bf.Briefing:
    return bf.Briefing(
        bf.Page(bf.Text("# Summary\n\nShort."), bf.BigNumber("Revenue", "$4.2M"), title="Summary"),
        bf.Page(bf.Text("# Detail"), bf.DataTable(pd.DataFrame({"n": range(30)})), title="Detail"),
        export=("png", "pdf"),
    )


def _report_size(page: Page) -> tuple[float, float]:
    box = page.locator(".bf-report").bounding_box()
    assert box is not None
    return box["width"], box["height"]


def test_save_as_png_downloads_the_current_page_at_2x(viewer: Viewer, tmp_path: Path) -> None:
    page = viewer.open(_report(), name="Q1 Report")
    page.get_by_role("tab", name="Detail").click()
    width, height = _report_size(page)
    with page.expect_download() as download:
        page.get_by_role("button", name="Save as PNG").click()
    saved = tmp_path / download.value.suggested_filename
    download.value.save_as(saved)
    assert saved.name == "q1_report_detail.png"
    w, h = png_size(saved)
    assert abs(w - 2 * width) <= 2 and abs(h - 2 * height) <= 2


def test_print_opens_the_print_dialog(viewer: Viewer) -> None:
    page = viewer.open(_report(), name="Q1 Report")
    page.evaluate("() => { window.__printed = 0; window.print = () => { window.__printed += 1; }; }")
    page.get_by_role("button", name="Print").click()
    assert page.evaluate("() => window.__printed") == 1


def test_the_menu_does_not_print(viewer: Viewer) -> None:
    page = viewer.open(_report(), name="Q1 Report")
    text = "\n".join(read_pdf(page.pdf(format="A4")).pages)
    assert "Save as PNG" not in text and "Print" not in text
    page.emulate_media(media="print")
    page.evaluate("window.dispatchEvent(new Event('beforeprint'))")
    assert page.locator(".bf-export").evaluate("e => getComputedStyle(e).display") == "none"
