"""A DataTable with wrapped columns fits its block instead of scrolling sideways (#151)."""
from __future__ import annotations

import pandas as pd

import briefing as bf
from tests.test_browser.conftest import Viewer

_NOTES = pd.DataFrame({"term": ["Steam", "Xbox"], "note": ["Queried as a topic because the word alone " * 8, "x"]})


def _scrolls(viewer: Viewer, block: bf.DataTable) -> bool:
    page = viewer.open(block)
    result: bool = page.locator(".bf-dt__scroll").evaluate("e => e.scrollWidth > e.clientWidth")
    return result


def test_wrapped_text_fits_the_block(viewer: Viewer) -> None:
    assert _scrolls(viewer, bf.DataTable(_NOTES))  # one line per cell: it scrolls
    assert not _scrolls(viewer, bf.DataTable(_NOTES, wrap=["note"]))
