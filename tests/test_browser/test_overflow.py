"""A wide block scrolls inside its own box; it never widens its Group, a page or the report."""
from __future__ import annotations

import pandas as pd
import pytest

import briefing as bf
from tests.test_browser.conftest import Viewer

_WIDE = " ".join(["word"] * 150)  # cells don't wrap: this is about 4,000 px of text


@pytest.mark.parametrize(
    "report",
    [
        bf.Briefing(bf.Group(bf.DataTable(pd.DataFrame({"a": [_WIDE]})), bf.Text("beside it"), columns=2)),
        bf.Briefing(bf.Group(bf.DataTable(pd.DataFrame({"a": [_WIDE]})), bf.Text("x"), columns=2, widths=[3, 1])),
        bf.Briefing(bf.Page(bf.DataTable(pd.DataFrame({"a": [_WIDE]})), title="A"), bf.Page(bf.Text("b"), title="B")),
        bf.Briefing(bf.Page(bf.Code("x = '" + "y" * 600 + "'"), title="A"), bf.Page(bf.Text("b"), title="B")),
    ],
    ids=["datatable-in-a-group", "datatable-in-widths", "datatable-in-a-page", "code-in-a-page"],
)
def test_a_wide_block_never_widens_the_report(viewer: Viewer, report: bf.Briefing) -> None:
    page = viewer.open(report)
    width = page.viewport_size["width"] if page.viewport_size else 0
    assert page.evaluate("document.documentElement.scrollWidth") <= width
    scroll = page.locator(".bf-dt__scroll, .bf-code pre").first
    assert scroll.evaluate("e => e.scrollWidth > e.clientWidth")  # it scrolls in its own box
