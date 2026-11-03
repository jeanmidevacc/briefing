"""Markdown in Text blocks, as a reader sees it (#4)."""
from __future__ import annotations

import pandas as pd
from playwright.sync_api import Page

import briefing as bf
from tests.test_browser.conftest import Viewer

_PROPS = ["fontSize", "paddingTop", "paddingLeft", "borderTopWidth", "borderTopStyle", "borderTopColor",
          "backgroundColor", "fontWeight"]


def _style(page: Page, selector: str) -> dict[str, str]:
    js = f"e => {{ const s = getComputedStyle(e); return Object.fromEntries({_PROPS!r}.map(p => [p, s[p]])); }}"
    style: dict[str, str] = page.locator(selector).first.evaluate(js)
    return style


def test_markdown_table_is_styled_like_a_table_block(viewer: Viewer) -> None:
    report = bf.Briefing(
        bf.Text("| a | b |\n| --- | --- |\n| 1 | 2 |"),
        bf.Table(pd.DataFrame({"a": [1], "b": [2]})),
    )
    page = viewer.open(report)
    assert page.locator(".bf-text table").count() == 1
    assert _style(page, ".bf-text th") == _style(page, ".bf-table__table th")
    assert _style(page, ".bf-text td") == _style(page, ".bf-table__table td")
