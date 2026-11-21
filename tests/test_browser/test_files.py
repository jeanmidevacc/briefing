"""Image and Attachment in the reader's browser (#36): the picture shows, the file downloads exactly."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
from playwright.sync_api import Page, expect

import briefing as bf
from tests.banner_images import RED_SVG
from tests.test_browser.conftest import Viewer


def _download(page: Page, label: str) -> tuple[str, bytes]:
    with page.expect_download() as caught:
        page.get_by_role("button", name=label).click()
    return caught.value.suggested_filename, Path(caught.value.path()).read_bytes()


def test_an_image_shows_at_its_width(viewer: Viewer) -> None:
    page = viewer.open(bf.Image(RED_SVG, caption="A red field", width=300))
    img = page.get_by_role("img", name="A red field")
    expect(img).to_be_visible()
    assert img.evaluate("i => [i.complete && i.naturalWidth > 0, i.getBoundingClientRect().width]") == [True, 300]


def test_an_image_never_wider_than_its_column(viewer: Viewer) -> None:
    page = viewer.open(bf.Group(bf.Image(RED_SVG, alt="Red"), bf.Text("beside"), columns=2))
    widths = page.get_by_role("img", name="Red").evaluate(
        "i => [i.getBoundingClientRect().width,"
        " i.closest('.bf-group__cell, .bf-group > *').getBoundingClientRect().width]"
    )
    assert widths[0] <= widths[1] + 0.5


def test_attachments_download_exactly(viewer: Viewer) -> None:
    frame = pd.DataFrame({"name": ["Zoë", "=SUM(A1)"], "n": [3, -5]})
    page = viewer.open(bf.Briefing(
        bf.Attachment(bytes(range(256)) * 40, filename="blob.bin", label="Blob"),
        bf.Attachment("café ✓\n".encode() * 500, filename="notes.txt", label="Notes"),
        bf.Attachment(frame, filename="orders.csv", label="Orders"),
    ))
    assert _download(page, "Blob") == ("blob.bin", bytes(range(256)) * 40)
    assert _download(page, "Notes") == ("notes.txt", "café ✓\n".encode() * 500)
    name, data = _download(page, "Orders")
    assert name == "orders.csv" and data.decode() == "﻿name,n\r\nZoë,3\r\n'=SUM(A1),-5\r\n"
    expect(page.locator(".bf-attachment__note").last).to_have_text("Downloaded orders.csv.")


def test_a_dataframe_attachment_is_the_same_file_as_the_tables_csv_button(viewer: Viewer) -> None:
    frame = pd.DataFrame({
        "x": [0.1234, 2.0, None],
        "day": pd.to_datetime(pd.Series(["2024-01-05", None, "2024-02-01"])),
        "w": ['say "hi"', "+33", "a,b"],
    })
    page = viewer.open(bf.Briefing(bf.Attachment(frame, filename="t.csv", label="File"),
                                   bf.DataTable(frame, name="t", download=True, formats={"x": "{:.1%}"})))
    _, attached = _download(page, "File")
    with page.expect_download() as caught:
        page.locator(".bf-dt__csv").click()
    assert Path(caught.value.path()).read_bytes() == attached


def test_an_attachment_prints_as_one_line(viewer: Viewer) -> None:
    page = viewer.open(bf.Attachment(b"x", filename="notes.txt", label="Notes"))
    page.evaluate("window.dispatchEvent(new Event('beforeprint'))")
    expect(page.locator(".bf-attachment__button")).to_be_visible()
    expect(page.locator(".bf-attachment__note")).to_be_hidden()
