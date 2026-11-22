"""Big tables from packed JSON (#38): a reader can't tell them from a table kept in the HTML.

The same rows are opened twice, once kept in the HTML (``HTML_ROWS`` raised) and once
packed, and every action a reader takes must show the same cells. ``unpack.js`` must give
back exactly what Python packed, whatever DEFLATE blocks zlib chose.
"""
from __future__ import annotations

import random
import typing as t

import pytest
from playwright.sync_api import Page, expect

import briefing as bf
from briefing.renderers.pack import pack
from tests.golden import static_files
from tests.scenarios import big_frame
from tests.test_browser.conftest import Viewer


def _cells(page: Page) -> list[list[t.Any]]:
    """Each row on show: its cells' text, data-sort key and link (#33)."""
    rows: list[list[t.Any]] = page.locator(".bf-dt__table tbody tr").evaluate_all(
        "rs => rs.map(r => Array.from(r.cells).map(c => [c.textContent, c.getAttribute('data-sort'),"
        " c.querySelector('a') && [c.querySelector('a').getAttribute('href'), c.querySelector('a').target]]))"
    )
    return rows


def _status(page: Page) -> tuple[str, str]:
    return page.locator(".bf-dt__count").inner_text(), page.locator(".bf-dt__page-info").inner_text()


def _walk(page: Page) -> list[t.Any]:
    """What a reader sees through paging, sorting both ways, searching and printing."""
    seen: list[t.Any] = [_cells(page), _status(page)]
    page.locator('.bf-dt__page-btn[data-dir="1"]').click()
    seen += [_cells(page), _status(page)]
    for col in (1, 1, 3, 2):  # x up, x down, day, word
        page.locator(f'.bf-dt__th[data-col="{col}"]').click()
        seen.append(_cells(page))
    page.locator(".bf-dt__search").fill("word 7")
    seen += [_cells(page), _status(page)]
    page.locator(".bf-dt__search").fill("")
    page.evaluate("window.dispatchEvent(new Event('beforeprint'))")
    seen += [len(_cells(page)), page.locator(".bf-dt__print-note").inner_text()]
    page.evaluate("window.dispatchEvent(new Event('afterprint'))")
    seen.append(_cells(page))
    return seen


def test_a_packed_table_behaves_like_one_in_the_html(viewer: Viewer, monkeypatch: pytest.MonkeyPatch) -> None:
    report = bf.Briefing(bf.DataTable(big_frame(1_500), formats={"x": "{:.2f}"},
                                      links={"id": "https://example.org/rows/{}"}))
    packed = viewer.open(report)
    assert packed.locator("script.bf-dt__data").count() == 1
    expected = _walk(packed)
    monkeypatch.setattr(bf.DataTable, "HTML_ROWS", 10_000)
    in_html = viewer.open(report)
    assert in_html.locator("script.bf-dt__data").count() == 0
    assert _walk(in_html) == expected
    assert expected[1] == ("1500 rows", "1–25 of 1500")
    assert expected[0][0][0] == ["0", None, ["https://example.org/rows/0", "_blank"]]  # a link, formatted x next
    assert expected[0][1][1][0] == f"{big_frame(2)['x'][1]:.2f}"
    assert expected[-2] == "Printed 1,000 of 1,500 rows."


def test_without_javascript_it_shows_its_first_page_and_says_so(browser: t.Any, tmp_path: t.Any) -> None:
    path = tmp_path / "big.html"
    path.write_text(bf.stringify(bf.DataTable(big_frame(1_500))), encoding="utf-8")
    context = browser.new_context(java_script_enabled=False)
    page = context.new_page()
    page.goto(path.as_uri())
    expect(page.locator(".bf-dt__table tbody tr")).to_have_count(25)
    expect(page.locator(".bf-dt__more")).to_have_text("The first 25 of 1,500 rows: the others need JavaScript.")
    context.close()


def test_with_javascript_the_note_doesnt_show(viewer: Viewer) -> None:
    page = viewer.open(bf.DataTable(big_frame(1_500)))
    expect(page.locator(".bf-dt__more")).to_have_count(0)  # inside <noscript>, which isn't parsed as markup


def test_a_copied_big_table_works_on_another_page(viewer: Viewer) -> None:
    page = viewer.open(bf.Briefing(bf.DataTable(big_frame(1_500), name="rows"), export="embed"))
    page.context.grant_permissions(["clipboard-read", "clipboard-write"])
    page.get_by_role("button", name="Copy embed code for this table").click()
    expect(page.locator(".bf-copy__toast")).to_contain_text("Embed code copied")
    fragment = page.evaluate("navigator.clipboard.readText()")
    host = viewer.open(f'<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><title>Host</title></head>'
                       f"<body>{fragment}</body></html>")
    expect(host.locator(".bf-dt__count")).to_have_text("1500 rows")


# ── the decompressor ──────────────────────────────────────────────────────────

_RNG = random.Random(38)
_SAMPLES = {
    "empty": "",
    "one character": "x",
    "unicode": "héllo wörld ✓ 日本 🎉" * 50,
    "a byte-order mark": "\ufeffname,n\r\nZoë,3\r\n",  # kept, as a CSV for spreadsheets needs it (#36)
    "repeats (fixed codes)": "abc" * 50_000,
    "noise (stored blocks)": "".join(chr(_RNG.randrange(32, 0x24F)) for _ in range(100_000)),
    "json (dynamic codes)": str([[_RNG.random() for _ in range(8)] for _ in range(3_000)]),
    "report.js": static_files()["static/report.js"],
}


@pytest.mark.parametrize("text", list(_SAMPLES.values()), ids=list(_SAMPLES))
def test_unpack_gives_back_exactly_what_python_packed(page: Page, text: str) -> None:
    page.set_content("<!DOCTYPE html><html><head></head><body></body></html>")
    page.add_script_tag(content=static_files()["static/unpack.js"])
    packed, size = pack(text)
    assert page.evaluate("([data, size]) => window.briefingUnpack(data, size)", [packed, size]) == text


def test_unpack_refuses_damaged_data(page: Page) -> None:
    page.set_content("<!DOCTYPE html><html><head></head><body></body></html>")
    page.add_script_tag(content=static_files()["static/unpack.js"])
    packed, size = pack("abc" * 1000)
    for data, n in ((packed[:20], size), (packed, size + 1)):
        message = page.evaluate(
            "([data, size]) => { try { window.briefingUnpack(data, size); return ''; }"
            " catch (e) { return e.message; } }",
            [data, n],
        )
        assert message.startswith("briefing: the compressed data is damaged")


def test_wrapped_columns_wrap_in_a_big_table_too(viewer: Viewer) -> None:
    page = viewer.open(bf.DataTable(big_frame(1_500), wrap=["word"]))
    page.locator('.bf-dt__page-btn[data-dir="1"]').click()  # rows made from the packed JSON
    classes = page.locator(".bf-dt__table tbody tr:first-child td").evaluate_all("cs => cs.map(c => c.className)")
    assert classes == ["", "", "bf-dt__wrap", ""]
