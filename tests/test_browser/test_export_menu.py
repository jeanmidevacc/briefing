"""The in-report export menu works in Chromium (#49)."""
from __future__ import annotations

import base64
from pathlib import Path

import pandas as pd
from playwright.sync_api import Page

import briefing as bf
from tests.image_helpers import png_size
from tests.pdf_reader import read_pdf
from tests.test_browser.conftest import Viewer

#: The page background kept around the report in a "Save as PNG" image, in CSS px (export.js MARGIN).
MARGIN = 32


def _report() -> bf.Briefing:
    return bf.Briefing(
        bf.Page(bf.Text("# Summary\n\nShort."), bf.BigNumber("Revenue", "$4.2M"), title="Summary"),
        bf.Page(bf.Text("# Detail"), bf.DataTable(pd.DataFrame({"n": range(30)})), title="Detail"),
        export="png",
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
    assert abs(w - 2 * (width + 2 * MARGIN)) <= 2 and abs(h - 2 * (height + 2 * MARGIN)) <= 2


# Decode a PNG in the page: the colours found in its outer band of `band` pixels, and how
# many pixels just inside that band differ from the page background.
_EDGES_JS = """async ([src, band]) => {
  const img = new Image(); img.src = src; await img.decode();
  const canvas = document.createElement('canvas');
  canvas.width = img.naturalWidth; canvas.height = img.naturalHeight;
  const ctx = canvas.getContext('2d'); ctx.drawImage(img, 0, 0);
  const px = ctx.getImageData(0, 0, canvas.width, canvas.height).data;
  const at = (x, y) => Array.from(px.slice((y * canvas.width + x) * 4, (y * canvas.width + x) * 4 + 3)).join(',');
  const probe = document.createElement('canvas').getContext('2d');
  probe.fillStyle = getComputedStyle(document.body).backgroundColor; probe.fillRect(0, 0, 1, 1);
  const background = Array.from(probe.getImageData(0, 0, 1, 1).data.slice(0, 3)).join(',');
  const edge = new Set(); let inside = 0;
  for (let y = 0; y < canvas.height; y++) for (let x = 0; x < canvas.width; x++) {
    const inBand = x < band || y < band || x >= canvas.width - band || y >= canvas.height - band;
    if (inBand) edge.add(at(x, y));
    else if (at(x, y) !== background) inside++;
  }
  return {edge: Array.from(edge), background, inside};
}"""


def test_save_as_png_keeps_a_margin_of_page_background(viewer: Viewer, tmp_path: Path) -> None:
    """Content never touches the image's edge: a MARGIN-wide band of page background frames it."""
    page = viewer.open(_report(), name="Q1 Report")
    with page.expect_download() as download:
        page.get_by_role("button", name="Save as PNG").click()
    saved = tmp_path / "q1.png"
    download.value.save_as(saved)
    src = "data:image/png;base64," + base64.b64encode(saved.read_bytes()).decode("ascii")
    found = page.evaluate(_EDGES_JS, [src, 2 * MARGIN])  # the image is drawn at 2x
    assert found["edge"] == [found["background"]]
    assert found["inside"] > 0, "the report itself should be drawn inside the margin"


def test_there_is_no_print_button(viewer: Viewer) -> None:
    """The browser's own print (Ctrl+P) does what the old "Print" button did."""
    page = viewer.open(_report(), name="Q1 Report")
    assert page.locator(".bf-export__btn").all_inner_texts() == ["Save as PNG"]


def test_the_menu_does_not_print(viewer: Viewer) -> None:
    page = viewer.open(_report(), name="Q1 Report")
    text = "\n".join(read_pdf(page.pdf(format="A4")).pages)
    assert "Save as PNG" not in text and "Print" not in text
    page.emulate_media(media="print")
    page.evaluate("window.dispatchEvent(new Event('beforeprint'))")
    assert page.locator(".bf-export").evaluate("e => getComputedStyle(e).display") == "none"
