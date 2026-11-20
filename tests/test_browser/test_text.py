"""Markdown in Text blocks, as a reader sees it (#4)."""
from __future__ import annotations

import pandas as pd
from playwright.sync_api import Page, expect

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


def test_markup_left_open_in_a_block_ends_with_it(viewer: Viewer) -> None:
    # An unclosed comment, <script> or <style> used to hide every later block, the footer and report.js (#45).
    report = bf.Briefing(
        bf.Select(bf.Text("Intro\n\n<!-- draft note", label="A"), bf.Text("Second tab", label="B")),
        bf.HTML("<style>"),
        bf.HTML("<script>"),
        bf.Text("<textarea>"),
        bf.HTML("<!-->"),  # already a whole comment, as is <!--->: nothing to close
        bf.HTML("<!--->"),
        bf.Text("The end"),
    )
    page = viewer.open(report)
    page.get_by_role("tab", name="B").click()  # report.js still runs
    expect(page.get_by_text("Second tab")).to_be_visible()
    expect(page.get_by_text("The end")).to_be_visible()
    expect(page.locator(".bf-report__footer")).to_be_visible()
