"""DataTable's CSV button (#34): a reader downloads the rows they searched for, in their order, as raw values."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
from playwright.sync_api import Page, expect

import briefing as bf
from briefing.export._render import open_report, outside_event_loop
from tests.scenarios import big_frame
from tests.test_browser.conftest import Viewer


def _orders() -> bf.DataTable:
    frame = pd.DataFrame({
        "name": ["Zoë", "=SUM(A1)", "a,b", 'say "hi"', "+33 1 23"],
        "n": [3, -5, 1, 2, 4],
        "share": [0.1234, 0.5, None, 0.25, 1.0],
        "day": pd.to_datetime(pd.Series(["2024-01-05", "2023-11-30", "2024-02-01", None, "2024-03-01"])),
    })
    return bf.DataTable(frame, formats={"share": "{:.1%}", "day": "{:%d %b %Y}"}, caption="Orders, Q1", download=True)


def _download(page: Page) -> tuple[str, str]:
    with page.expect_download() as caught:
        page.locator(".bf-dt__csv").click()
    download = caught.value
    return download.suggested_filename, Path(download.path()).read_bytes().decode("utf-8")


def test_it_downloads_raw_values_in_the_readers_order(viewer: Viewer) -> None:
    page = viewer.open(_orders())
    page.locator('.bf-dt__th[data-col="1"]').click()
    name, text = _download(page)
    assert name == "orders-q1.csv"
    assert text == (
        "﻿name,n,share,day\r\n"
        "'=SUM(A1),-5,0.5,2023-11-30T00:00:00\r\n"  # a formula escaped, a negative number not
        '"a,b",1,,2024-02-01T00:00:00\r\n'
        '"say ""hi""",2,0.25,\r\n'
        "Zoë,3,0.1234,2024-01-05T00:00:00\r\n"  # raw values, not the formatted text
        "'+33 1 23,4,1,2024-03-01T00:00:00\r\n"
    )
    expect(page.locator(".bf-dt__csv-note")).to_have_text("Downloaded 5 rows as orders-q1.csv.")


def test_it_downloads_only_the_rows_matching_the_search(viewer: Viewer) -> None:
    page = viewer.open(_orders())
    page.locator(".bf-dt__search").fill("zo")
    _, text = _download(page)
    assert text.splitlines()[1:] == ["Zoë,3,0.1234,2024-01-05T00:00:00"]


def test_a_big_table_downloads_every_matching_row_not_one_page(viewer: Viewer) -> None:
    page = viewer.open(bf.DataTable(big_frame(1_500), formats={"x": "{:.2f}"}, download=True, name="rows"))
    page.locator(".bf-dt__search").fill("word 3")
    name, text = _download(page)
    lines = text.lstrip("﻿").splitlines()
    frame = big_frame(1_500)
    matching = frame[frame["word"].str.contains("word 3")]  # "word 3" and nothing else: 13 words
    assert name == "rows.csv" and lines[0] == "id,x,word,day" and len(lines) == 1 + len(matching)
    assert lines[1].split(",")[1] == repr(float(matching["x"].iloc[0]))  # full precision, not "{:.2f}"


def test_it_never_prints(viewer: Viewer) -> None:
    page = viewer.open(_orders())
    page.evaluate("window.dispatchEvent(new Event('beforeprint'))")
    expect(page.locator(".bf-dt__csv")).to_be_hidden()


def test_it_is_left_out_of_images_and_pdfs() -> None:
    def check() -> None:
        with open_report(bf.Briefing(_orders()), width=900, scale=1) as session:
            assert session.page.locator(".bf-dt__csv").count() == 1
            assert not session.page.locator(".bf-dt__csv").is_visible()

    outside_event_loop(check)


def test_the_save_as_png_menu_leaves_it_out(viewer: Viewer) -> None:
    page = viewer.open(bf.Briefing(_orders(), export="png"))
    page.evaluate("""() => {  // keep what export.js draws into the PNG
        const serialize = XMLSerializer.prototype.serializeToString;
        window.drawn = [];
        XMLSerializer.prototype.serializeToString = function (node) {
            const markup = serialize.call(this, node);
            window.drawn.push(markup);
            return markup;
        };
    }""")
    with page.expect_download():
        page.get_by_role("button", name="Save as PNG").click()
    drawn: str = page.evaluate("window.drawn.join('')")
    assert "bf-dt__search" in drawn  # the toolbar is drawn…
    assert "bf-dt__csv" not in drawn  # …without the button and its note
