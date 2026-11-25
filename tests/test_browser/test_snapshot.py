"""The snapshot button, as a reader uses it: copy one block of a report as an image (#215)."""
from __future__ import annotations

import typing as t
from pathlib import Path

import pandas as pd
import pytest
from playwright.sync_api import Page, expect

import briefing as bf
from briefing.export._render import open_report, outside_event_loop
from tests.image_helpers import png_size
from tests.test_browser.conftest import Viewer

#: The background kept around a block in its image, in CSS px (export.js BLOCK_MARGIN).
MARGIN = 16

_ROWS = pd.DataFrame({"n": [3, 1, 2], "word": ["three", "one", "two"]})


def _plotly() -> t.Any:
    go = pytest.importorskip("plotly.graph_objects")
    return go.Figure(go.Scatter(x=[1, 2, 3], y=[3, 1, 2]))


def _report(*export: str) -> bf.Briefing:
    return bf.Briefing(
        bf.Page(
            bf.Text("# Summary"),
            bf.Group(bf.BigNumber("Revenue", "$4.2M"), bf.BigNumber("Orders", "1,204"), columns=2, label="Numbers"),
            title="Summary",
        ),
        bf.Page(bf.DataTable(_ROWS, name="rows"), title="Detail", name="detail"),
        export=export or ("snapshot",),
    )


def _box(page: Page, selector: str) -> tuple[float, float]:
    box = page.locator(selector).first.bounding_box()
    assert box is not None
    return box["width"], box["height"]


# What export.js draws: every SVG it serializes, recorded before it becomes an image.
_RECORD_JS = """() => {
  window.drawn = [];
  const serialize = XMLSerializer.prototype.serializeToString;
  XMLSerializer.prototype.serializeToString = function (node) {
    const text = serialize.call(this, node); window.drawn.push(text); return text;
  };
}"""

# The PNG on the clipboard: its type and size in pixels.
_CLIPBOARD_IMAGE_JS = """async () => {
  const [item] = await navigator.clipboard.read();
  const blob = await item.getType('image/png');
  const bitmap = await createImageBitmap(blob);
  return {types: item.types, width: bitmap.width, height: bitmap.height};
}"""


def test_the_button_copies_the_block_as_a_png_at_2x(viewer: Viewer) -> None:
    page = viewer.open(_report(), name="Q1 Report")
    page.context.grant_permissions(["clipboard-read", "clipboard-write"])
    page.evaluate(_RECORD_JS)
    width, height = _box(page, '[data-bf-snap="Numbers"]')
    page.get_by_role("button", name="Copy Numbers as an image").click()
    expect(page.locator(".bf-copy__toast")).to_have_text("Image copied to the clipboard")
    image = page.evaluate(_CLIPBOARD_IMAGE_JS)
    assert image["types"] == ["image/png"]
    assert abs(image["width"] - 2 * (width + 2 * MARGIN)) <= 2
    assert abs(image["height"] - 2 * (height + 2 * MARGIN)) <= 2
    drawn = page.evaluate("window.drawn")
    assert len(drawn) == 1 and "$4.2M" in drawn[0] and "1,204" in drawn[0]
    assert "bf-copy" not in drawn[0], "the buttons must not be in the image"


def test_the_image_downloads_when_the_clipboard_is_refused(viewer: Viewer, tmp_path: Path) -> None:
    page = viewer.open(_report(), name="Q1 Report")
    # As in a sandboxed notebook frame, or a browser without image copying.
    page.evaluate("() => { window.ClipboardItem = undefined; }")
    page.get_by_role("tab", name="Detail").click()
    width, height = _box(page, '[data-bf-snap="this table"]')
    with page.expect_download() as download:
        page.get_by_role("button", name="Copy this table as an image").click()
    saved = tmp_path / download.value.suggested_filename
    download.value.save_as(saved)
    assert saved.name == "q1_report_table.png"
    w, h = png_size(saved)
    assert abs(w - 2 * (width + 2 * MARGIN)) <= 2 and abs(h - 2 * (height + 2 * MARGIN)) <= 2
    expect(page.locator(".bf-copy__toast")).to_have_text("Image saved as q1_report_table.png")


def test_a_page_downloads_under_its_title(viewer: Viewer, tmp_path: Path) -> None:
    page = viewer.open(_report(), name="Q1 Report")
    page.evaluate("() => { navigator.clipboard.write = () => Promise.reject(new Error('denied')); }")
    with page.expect_download() as download:
        page.get_by_role("button", name="Copy the Summary page as an image").click()
    assert download.value.suggested_filename == "q1_report_summary.png"


def test_a_chart_is_drawn_without_plotlys_toolbar(viewer: Viewer) -> None:
    page = viewer.open(bf.Briefing(bf.Plot(_plotly(), caption="Trend"), export="snapshot"))
    page.context.grant_permissions(["clipboard-read", "clipboard-write"])
    page.evaluate(_RECORD_JS)
    page.locator(".bf-plot").hover()
    page.get_by_role("button", name="Copy Trend as an image").click()
    expect(page.locator(".bf-copy__toast")).to_have_text("Image copied to the clipboard")
    drawn = page.evaluate("window.drawn")
    assert "main-svg" in drawn[0] and "modebar" not in drawn[0]


def test_with_embed_both_buttons_sit_side_by_side(viewer: Viewer) -> None:
    page = viewer.open(_report("embed", "snapshot"), name="Q1 Report")
    block = page.locator('[data-bf-snap="Numbers"]')
    block.hover()
    tools = block.locator(":scope > .bf-copy__tools")
    expect(tools).to_have_count(1)
    image = tools.get_by_role("button", name="Copy Numbers as an image")
    embed = tools.get_by_role("button", name="Copy embed code for Numbers")
    expect(image).to_be_visible()
    expect(embed).to_be_visible()
    a, b = image.bounding_box(), embed.bounding_box()
    assert a is not None and b is not None
    assert a["x"] + a["width"] <= b["x"], "the buttons must not overlap"
    assert abs(a["y"] - b["y"]) <= 2


def test_a_copied_fragment_carries_no_snapshot_marks(viewer: Viewer) -> None:
    page = viewer.open(_report("embed", "snapshot"))
    page.context.grant_permissions(["clipboard-read", "clipboard-write"])
    page.get_by_role("button", name="Copy embed code for the Summary page").click()
    expect(page.locator(".bf-copy__toast")).to_contain_text("Embed code copied")
    fragment: str = page.evaluate("navigator.clipboard.readText()")
    assert "data-bf-snap" not in fragment and "data-bf-embed" not in fragment


def test_the_button_works_by_keyboard(viewer: Viewer) -> None:
    page = viewer.open(_report())
    page.context.grant_permissions(["clipboard-read", "clipboard-write"])
    button = page.get_by_role("button", name="Copy the Summary page as an image")
    expect(button).to_have_css("opacity", "0")
    button.focus()
    expect(button).to_have_css("opacity", "1")
    page.keyboard.press("Enter")
    expect(page.locator(".bf-copy__toast")).to_have_text("Image copied to the clipboard")


def test_the_buttons_never_print(viewer: Viewer) -> None:
    page = viewer.open(_report())
    page.evaluate("window.dispatchEvent(new Event('beforeprint'))")
    buttons = page.locator(".bf-copy__button--image")
    expect(buttons).to_have_count(7)  # 2 pages, the text, the group, 2 numbers, the table
    for i in range(7):
        expect(buttons.nth(i)).to_be_hidden()


def test_the_buttons_are_left_out_of_images_and_pdfs() -> None:
    def check() -> None:
        with open_report(_report(), width=900, scale=1) as session:  # what save_image and save_pdf open
            buttons = session.page.locator(".bf-copy__button--image")
            assert buttons.count() == 7
            assert all(not b.is_visible() for b in buttons.all())

    outside_event_loop(check)
