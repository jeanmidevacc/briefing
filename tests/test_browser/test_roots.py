"""briefing's scripts work per root: two outputs share a page without driving each other (#123).

The two-root page holds the bodies of two reports built from the same blocks, so their
ids are the same too: only scripts that query from their own root keep them apart.
"""
from __future__ import annotations

import pandas as pd
from playwright.sync_api import Locator, Page, expect

import briefing as bf
from tests.golden import static_files
from tests.test_browser.conftest import INIT_DOCUMENT, Viewer, split_report


def _report(name: str) -> str:
    days = pd.DataFrame({"day": pd.to_datetime(["2026-01-05", "2026-01-06"]), "amount": [5.0, 3.0]})
    rows = pd.DataFrame({"n": [3, 1, 2], "word": ["three", "one", "two"]})
    report = bf.Briefing(
        bf.Page(
            bf.Toggle(bf.Text("Hidden detail"), label="More"),
            bf.lab.CalendarHeatmap(days, date="day", value="amount"),
            title="Summary",
        ),
        bf.Page(bf.DataTable(rows), title="Detail"),
        export="png",
    )
    return bf.stringify(report, name=name)


def _two_roots(init: str = "a b") -> str:
    head, alpha, scripts = split_report(_report("Alpha"))
    _, beta, _ = split_report(_report("Beta"))
    calls = "".join(f"briefing.init(document.getElementById('root-{r}'));" for r in init.split())
    return (
        f'{head}</head><body><section id="root-a">{alpha}</section><section id="root-b">{beta}</section>'
        f"<script>{scripts}\n{calls}</script></body></html>"
    )


def _roots(page: Page) -> tuple[Locator, Locator]:
    return page.locator("#root-a"), page.locator("#root-b")


def _words(root: Locator) -> list[str]:
    return root.locator(".bf-dt__table tbody tr:not([hidden]) td:last-child").all_inner_texts()


def test_tabs_and_toggles_work_in_their_own_root(viewer: Viewer) -> None:
    a, b = _roots(viewer.open(_two_roots()))
    a.get_by_role("tab", name="Detail").click()
    expect(a.get_by_role("tab", name="Detail")).to_have_attribute("aria-selected", "true")
    expect(b.get_by_role("tab", name="Summary")).to_have_attribute("aria-selected", "true")
    b.get_by_role("button", name="More").click()
    expect(b.get_by_text("Hidden detail")).to_be_visible()
    expect(a.locator(".bf-toggle__header")).to_have_attribute("aria-expanded", "false")  # in a hidden panel


def test_datatable_sort_and_search_stay_in_their_own_root(viewer: Viewer) -> None:
    page = viewer.open(_two_roots())
    a, b = _roots(page)
    for root in (a, b):
        root.get_by_role("tab", name="Detail").click()
    a.locator('.bf-dt__th[data-col="0"]').click()
    assert _words(a) == ["one", "two", "three"]
    assert _words(b) == ["three", "one", "two"]
    b.locator(".bf-dt__search").fill("two")
    expect(b.locator(".bf-dt__count")).to_have_text("1 row")
    expect(a.locator(".bf-dt__count")).to_have_text("3 rows")


def test_calendar_tooltips_show_in_their_own_root(viewer: Viewer) -> None:
    a, b = _roots(viewer.open(_two_roots()))
    a.locator('rect[data-date="2026-01-05"]').hover()
    expect(a.locator(".bf-cal__tip")).to_be_visible()
    expect(b.locator(".bf-cal__tip")).to_be_hidden()
    b.locator('rect[data-date="2026-01-06"]').hover()
    expect(b.locator(".bf-cal__tip")).to_contain_text("2026-01-06")
    expect(a.locator(".bf-cal__tip")).to_be_hidden()  # one tooltip at a time on the page


def test_the_export_menu_saves_its_own_root(viewer: Viewer) -> None:
    page = viewer.open(_two_roots())
    a, b = _roots(page)
    a.get_by_role("tab", name="Detail").click()
    with page.expect_download() as download:
        b.get_by_role("button", name="Save as PNG").click()
    assert download.value.suggested_filename == "beta_summary.png"
    with page.expect_download() as download:
        a.get_by_role("button", name="Save as PNG").click()
    assert download.value.suggested_filename == "alpha_detail.png"


def test_printing_labels_the_panels_of_every_root(viewer: Viewer) -> None:
    page = viewer.open(_two_roots())
    a, b = _roots(page)
    page.evaluate("window.dispatchEvent(new Event('beforeprint'))")
    for root in (a, b):
        expect(root.locator(".bf-print-label")).to_have_text(["Summary", "Detail"])
        expect(root).to_have_class("bf-printing")
    page.evaluate("window.dispatchEvent(new Event('afterprint'))")
    for root in (a, b):
        expect(root.locator(".bf-print-label")).to_have_count(0)
        expect(root).not_to_have_class("bf-printing")


def test_a_root_left_uninitialised_stays_inert(viewer: Viewer) -> None:
    a, b = _roots(viewer.open(_two_roots(init="a")))
    b.get_by_role("tab", name="Detail").click()
    expect(b.get_by_role("tab", name="Detail")).not_to_have_attribute("aria-selected", "true")
    expect(a.locator(".bf-cal__tip")).to_have_count(1)
    expect(b.locator(".bf-cal__tip")).to_have_count(0)


# ── init and register run once ────────────────────────────────────────────────


def _click_once_and_check(root: Locator | Page) -> None:
    # A second handler would undo each of these: the toggle would close and the sort flip.
    root.get_by_role("button", name="More").click()
    expect(root.get_by_text("Hidden detail")).to_be_visible()
    root.get_by_role("tab", name="Detail").click()
    root.locator('.bf-dt__th[data-col="0"]').click()
    expect(root.locator('.bf-dt__th[data-col="0"]')).to_have_attribute("data-sort", "asc")


def test_a_second_init_of_the_document_does_nothing(viewer: Viewer) -> None:
    page = viewer.open(_report("Alpha"))
    expect(page.locator("html")).to_have_attribute("data-bf-ready", "")
    page.evaluate("briefing.init(document)")
    _click_once_and_check(page)


def test_a_second_init_of_an_element_root_does_nothing(viewer: Viewer) -> None:
    page = viewer.open(_two_roots(init="a a b"))
    a, _ = _roots(page)
    expect(a).to_have_attribute("data-bf-ready", "")
    expect(a.locator(".bf-cal__tip")).to_have_count(1)
    _click_once_and_check(a)


def test_a_script_inlined_twice_registers_once(viewer: Viewer) -> None:
    head, body, scripts = split_report(_report("Alpha"))
    report_js = static_files()["static/report.js"]
    twice = f"{report_js}\n{scripts}{INIT_DOCUMENT}"
    page = viewer.open(f"{head}</head><body>{body}<script>{twice}</script></body></html>")
    _click_once_and_check(page)


def test_a_script_registered_after_init_sets_up_the_roots_already_there(viewer: Viewer) -> None:
    dive = bf.stringify(bf.Briefing(bf.lab.DataDive(pd.DataFrame({"x": [1.0, 2.0, 3.0], "y": [3.0, 1.0, 2.0]}))))
    head, body, scripts = split_report(dive)
    lab_js = static_files()["lab/static/lab.js"]
    assert lab_js in scripts
    report_first = scripts.replace(lab_js, "") + INIT_DOCUMENT + "\n" + lab_js
    page = viewer.open(f"{head}</head><body>{body}<script>{report_first}</script></body></html>")
    page.wait_for_function("() => document.querySelector('.bf-datadive').briefingDive")
    assert page.evaluate("document.querySelector('.bf-datadive').briefingDive.shown()") == 3
