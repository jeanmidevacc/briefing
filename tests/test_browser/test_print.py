"""Printing shows every page, tab and toggle, without controls (#37)."""
from __future__ import annotations

import typing as t

import pandas as pd
import pytest
from playwright.sync_api import Page

import briefing as bf
from tests.pdf_reader import Pdf, read_pdf
from tests.test_browser.conftest import Viewer

ROWS = 5_000


def _report() -> bf.Briefing:
    go = pytest.importorskip("plotly.graph_objects")
    df = pd.DataFrame({"label": [f"row {i}" for i in range(ROWS)], "n": range(ROWS)})
    small = pd.DataFrame({"x": [1.0, 2.0, 3.0], "y": [3.0, 1.0, 2.0], "cat": ["a", "b", "a"]})
    return bf.Briefing(
        bf.Page(
            bf.Text("Quarter summary text."),
            bf.Group(bf.BigNumber("Revenue", "$4.2M"), bf.BigNumber("Users", "142K"), columns=2),
            bf.Toggle(bf.Text("Toggle body text."), label="Methodology"),
            title="Summary",
        ),
        bf.Page(bf.DataTable(df, caption="All rows"), title="Data"),
        bf.Page(
            bf.Plot(go.Figure(go.Scatter(x=[1, 2, 3], y=[3, 1, 2]))),
            bf.Select(bf.Text("first option", label="First"), bf.Text("second option", label="Second"),
                      type="dropdown"),
            bf.lab.DataDive(small),
            title="Charts",
        ),
    )


def _print(page: Page) -> Pdf:
    return read_pdf(page.pdf(format="A4", print_background=True))


def _in_print_layout(page: Page) -> None:
    page.emulate_media(media="print")
    page.evaluate("window.dispatchEvent(new Event('beforeprint'))")


def _display(page: Page, selector: str) -> list[str]:
    displays: list[str] = page.locator(selector).evaluate_all("els => els.map(e => getComputedStyle(e).display)")
    return displays


def test_every_page_prints_on_its_own_sheet(viewer: Viewer) -> None:
    pdf = _print(viewer.open(_report(), name="Q1 Report"))
    starts = [text.split("\n", 1)[0].strip() for text in pdf.pages]
    assert "Data" in starts and "Charts" in starts  # pages 2 and 3 open a sheet with their title
    assert "Summary" in pdf.pages[0]
    order = [next(i for i, text in enumerate(pdf.pages) if title in text) for title in ("Summary", "Data", "Charts")]
    assert order == sorted(order)


def test_tab_labels_become_headings_and_the_tab_bar_is_hidden(viewer: Viewer) -> None:
    page = viewer.open(_report())
    _in_print_layout(page)
    assert _display(page, ".bf-select__tablist") == ["none"]
    labels = page.locator(".bf-print-label").all_inner_texts()
    assert labels == ["Summary", "Data", "Charts", "First", "Second"]


def test_toggles_print_open_and_controls_are_hidden(viewer: Viewer) -> None:
    page = viewer.open(_report())
    pdf = _print(page)
    text = "\n".join(pdf.pages)
    assert "Toggle body text." in text and "second option" in text
    assert "Search" not in text and "Prev" not in text and "Next" not in text
    _in_print_layout(page)
    assert _display(page, ".bf-toggle__body") == ["block"]
    for control in (".bf-dt__toolbar", ".bf-dt__footer", ".bf-select__select", ".bf-dd__controls", ".bf-toggle__icon"):
        assert set(_display(page, control)) == {"none"}, control


def test_datatable_prints_1000_rows_with_a_note(viewer: Viewer) -> None:
    pdf = _print(viewer.open(_report()))
    text = "\n".join(pdf.pages)
    assert "Printed 1,000 of 5,000 rows" in text
    assert "row 999\n" in text + "\n" and "row 1000\n" not in text + "\n"


def test_datatable_prints_the_rows_matching_the_search(viewer: Viewer) -> None:
    page = viewer.open(_report())
    page.get_by_role("tab", name="Data").click()
    page.locator(".bf-dt__search").fill("row 4")  # row 4, 40-49, 400-499, 4000-4999: 1,111 rows
    text = "\n".join(_print(page).pages)
    assert "Printed 1,000 of 1,111 rows" in text
    assert "row 3\n" not in text + "\n"


def test_plotly_fills_the_printable_width(viewer: Viewer) -> None:
    page = viewer.open(_report())
    _in_print_layout(page)
    page.wait_for_timeout(300)
    widths: dict[str, float] = page.evaluate("""() => {
      const probe = document.createElement('div'); probe.style.width = '180mm'; document.body.append(probe);
      const paper = probe.getBoundingClientRect().width; probe.remove();
      const fig = document.querySelector('figure.bf-plot');
      return {paper, figure: fig.getBoundingClientRect().width,
              chart: fig.querySelector('.main-svg').getBoundingClientRect().width};
    }""")
    assert widths["figure"] == pytest.approx(widths["paper"], abs=2)
    assert widths["chart"] / widths["figure"] > 0.97


def _screen_state(page: Page) -> dict[str, t.Any]:
    state: dict[str, t.Any] = page.evaluate("""() => ({
      hiddenPanels: [...document.querySelectorAll('.bf-select__panel')].map(p => p.hidden),
      toggleHidden: document.querySelector('.bf-toggle__body').hidden,
      visibleRows: document.querySelectorAll('.bf-dt__table tbody tr:not([hidden])').length,
      labels: document.querySelectorAll('.bf-print-label').length,
      printing: document.documentElement.classList.contains('bf-printing'),
      chart: Math.round(document.querySelector('.main-svg').getBoundingClientRect().width),
    })""")
    return state


def test_screen_layout_is_unchanged_after_printing(viewer: Viewer) -> None:
    page = viewer.open(_report())
    page.wait_for_timeout(300)
    before = _screen_state(page)
    page.pdf(format="A4")  # fires beforeprint and afterprint, like the print dialog
    page.wait_for_timeout(300)
    assert _screen_state(page) == before


def test_colours_print_and_blocks_avoid_splitting(viewer: Viewer) -> None:
    page = viewer.open(_report())
    page.emulate_media(media="print")
    styles: dict[str, str] = page.evaluate("""() => ({
      adjust: getComputedStyle(document.body).printColorAdjust,
      plot: getComputedStyle(document.querySelector('.bf-plot')).breakInside,
      kpis: getComputedStyle(document.querySelector('.bf-bignumber').parentElement).breakInside,
    })""")
    assert styles == {"adjust": "exact", "plot": "avoid", "kpis": "avoid"}


def test_pdf_reader_walks_the_whole_page_tree(viewer: Viewer) -> None:
    # Skia groups pages eight to a /Pages node; the reader must find all of them, in order.
    blocks = [bf.Page(bf.Text(f"Sheet number {i}"), title=f"P{i}") for i in range(20)]
    pdf = _print(viewer.open(bf.Briefing(*blocks)))
    assert len(pdf.pages) == 20
    assert [f"Sheet number {i}" in text for i, text in enumerate(pdf.pages)] == [True] * 20
