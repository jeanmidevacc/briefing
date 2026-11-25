"""The copy-embed button, as a reader uses it: copy a part of a report, paste it elsewhere (#124)."""
from __future__ import annotations

import typing as t

import pandas as pd
import pytest
from playwright.sync_api import Page, expect

import briefing as bf
from briefing.export._render import open_report, outside_event_loop
from tests.contract import FRAGMENT_RULES, parse_report
from tests.test_browser.conftest import Viewer, click_tool

_ROWS = pd.DataFrame({"n": [3, 1, 2], "word": ["three", "one", "two"]})


def _plotly() -> t.Any:
    go = pytest.importorskip("plotly.graph_objects")
    return go.Figure(go.Scatter(x=[1, 2, 3], y=[3, 1, 2]))


def _report() -> bf.Briefing:
    return bf.Briefing(
        bf.Page(bf.Text("# Summary\n\nSee [the rows](#detail/rows)."), bf.Plot(_plotly()), title="Summary",
                name="summary"),
        bf.Page(bf.DataTable(_ROWS, name="rows"), bf.Toggle(bf.Text("Hidden detail"), label="More"),
                title="Detail", name="detail"),
        export="embed",
    )


def _open(viewer: Viewer) -> Page:
    page = viewer.open(_report())
    page.context.grant_permissions(["clipboard-read", "clipboard-write"])
    return page


def _copy(page: Page, label: str) -> str:
    click_tool(page.get_by_role("button", name=f"Copy embed code for {label}"))
    expect(page.locator(".bf-copy__toast")).to_contain_text("Embed code copied, ")
    copied: str = page.evaluate("navigator.clipboard.readText()")
    return copied


def _paste(viewer: Viewer, *fragments: str) -> Page:
    """A blank host page of someone else's, with *fragments* pasted into its body."""
    return viewer.open(
        '<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><title>Host</title></head>'
        f'<body><h1>Elsewhere</h1>{"".join(fragments)}</body></html>'
    )


def _words(page: Page) -> list[str]:
    return page.locator(".bf-dt__table tbody tr:not([hidden]) td:last-child").all_inner_texts()


def test_a_copied_table_is_the_untouched_one_and_works_on_another_page(viewer: Viewer) -> None:
    page = _open(viewer)
    page.get_by_role("tab", name="Detail").click()
    page.locator('.bf-dt__th[data-col="0"]').click()  # sorted on the page: the copy must not be
    page.locator('.bf-dt__search').fill("t")
    fragment = _copy(page, "this table")
    soup = parse_report(fragment)
    for rule in FRAGMENT_RULES.values():
        rule(soup)
    assert fragment.startswith(f"<!-- briefing {bf.__version__} embed: rows -->")
    host = _paste(viewer, fragment)
    assert _words(host) == ["three", "one", "two"]  # as rendered, not as sorted and searched
    expect(host.locator(".bf-dt__count")).to_have_text("3 rows")
    host.locator('.bf-dt__th[data-col="0"]').click()
    assert _words(host) == ["one", "two", "three"]
    expect(host.locator(".bf-copy__button")).to_have_count(0)  # a fragment never carries the buttons


def test_a_copied_page_brings_its_chart_runtime_and_links(viewer: Viewer) -> None:
    page = _open(viewer)
    fragment = _copy(page, "the Summary page")
    assert "if (!window.Plotly) (function (script, here) {" in fragment  # the packed runtime (#38)
    for rule in FRAGMENT_RULES.values():
        rule(parse_report(fragment))
    host = _paste(viewer, fragment)
    expect(host.locator("#summary .js-plotly-plot .main-svg").first).to_be_visible()
    assert host.locator("#summary .bf-text h1").inner_text() == "Summary"


def test_the_code_shows_in_a_dialog_when_copying_is_refused(viewer: Viewer) -> None:
    page = viewer.open(_report())
    # As in a sandboxed notebook frame: no clipboard, and the copy command refused.
    page.evaluate("""() => {
        Object.defineProperty(navigator, 'clipboard', {value: {writeText: () => Promise.reject(new Error('denied'))}});
        document.execCommand = () => false;
    }""")
    page.get_by_role("tab", name="Detail").click()
    click_tool(page.get_by_role("button", name="Copy embed code for this table"))
    dialog = page.get_by_role("dialog", name="Embed code for this table")
    expect(dialog).to_be_visible()
    code = dialog.locator("textarea")
    expect(code).to_be_focused()
    value = code.input_value()
    assert value.startswith("<!-- briefing") and value.rstrip().endswith("</div>")
    assert code.evaluate("e => [e.selectionStart, e.selectionEnd]") == [0, len(value)]
    dialog.get_by_role("button", name="Close").click()
    expect(page.locator(".bf-copy__dialog")).to_have_count(0)


def test_the_button_works_by_keyboard(viewer: Viewer) -> None:
    page = _open(viewer)
    button = page.get_by_role("button", name="Copy embed code for the Summary page")
    expect(button).to_have_css("opacity", "0")
    button.focus()
    expect(button).to_have_css("opacity", "1")
    page.keyboard.press("Enter")
    expect(page.locator(".bf-copy__toast")).to_contain_text("Embed code copied")
    assert page.evaluate("navigator.clipboard.readText()").startswith("<!-- briefing")


def test_the_buttons_never_print(viewer: Viewer) -> None:
    page = viewer.open(_report())
    button = page.get_by_role("button", name="Copy embed code for the Summary page")
    button.focus()
    page.evaluate("window.dispatchEvent(new Event('beforeprint'))")
    expect(page.locator(".bf-copy__button")).to_have_count(6)  # 2 pages, 2 texts, the chart, the table
    for i in range(6):
        expect(page.locator(".bf-copy__button").nth(i)).to_be_hidden()


def test_the_buttons_are_left_out_of_images_and_pdfs() -> None:
    def check() -> None:
        with open_report(_report(), width=900, scale=1) as session:  # what save_image and save_pdf open
            assert session.page.locator(".bf-copy__button").count() == 6
            assert all(not b.is_visible() for b in session.page.locator(".bf-copy__button").all())

    outside_event_loop(check)
