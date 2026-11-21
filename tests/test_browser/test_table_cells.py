"""Formatted and linked DataTable cells (#33), as a reader sees and sorts them."""
from __future__ import annotations

import pandas as pd
from playwright.sync_api import expect

import briefing as bf
from tests.test_browser.conftest import Viewer
from tests.test_browser.test_datatable import sort_by, visible_column


def _report() -> bf.Briefing:
    papers = pd.DataFrame({
        "title": ["Graphs", "Ranking", "Bandits"],
        "share": [0.5, 0.1234, None],
        "published": pd.to_datetime(["2024-01-05", "2023-11-30", "2024-02-01"]),
        "url": ["https://example.org/a", "https://example.org/b", None],
    })
    return bf.Briefing(bf.DataTable(papers, formats={"share": "{:.1%}", "published": "{:%d %b %Y}"},
                                    links={"title": "{url}"}))


def test_formatted_cells_sort_by_their_value(viewer: Viewer) -> None:
    page = viewer.open(_report())
    sort_by(page, 2)
    assert visible_column(page, 2) == ["30 Nov 2023", "05 Jan 2024", "01 Feb 2024"]  # by date, not by text
    sort_by(page, 1)
    assert visible_column(page, 1) == ["12.3%", "50.0%", ""]  # empty last


def test_linked_cells_open_their_url_in_a_new_tab(viewer: Viewer) -> None:
    page = viewer.open(_report())
    link = page.get_by_role("link", name="Graphs")
    expect(link).to_have_attribute("href", "https://example.org/a")
    expect(link).to_have_attribute("target", "_blank")
    expect(page.get_by_role("link", name="Bandits")).to_have_count(0)
    page.locator(".bf-dt__search").fill("rank")
    expect(page.get_by_role("link", name="Ranking")).to_be_visible()  # search reads the link's text
