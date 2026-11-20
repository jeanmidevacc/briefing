"""Fragments on a host page, as a reader of a docs site or a wiki sees them (#122)."""
from __future__ import annotations

import typing as t

import pandas as pd
import pytest
from playwright.sync_api import Locator, Page, expect

import briefing as bf
from tests.test_browser.conftest import Viewer

_DAYS = pd.DataFrame({"day": pd.to_datetime(["2026-01-05", "2026-01-06"]), "amount": [5.0, 3.0]})
_ROWS = pd.DataFrame({"n": [3, 1, 2], "word": ["three", "one", "two"]})

#: Styles that matter on a host page; read from an element with getComputedStyle.
_STYLE = ["fontFamily", "fontSize", "fontWeight", "fontStyle", "lineHeight", "letterSpacing", "color",
          "backgroundColor", "marginTop", "marginBottom", "paddingTop", "paddingLeft", "textAlign"]
_STYLE_JS = f"e => {{ const s = getComputedStyle(e); return {_STYLE!r}.map(p => s[p]); }}"


def _host(*parts: str, head: str = "", css: str = "") -> str:
    """A plain page of the host's own, holding *parts* between its heading and its last paragraph."""
    return (
        '<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><title>Host</title>'
        f"<style>{css}</style>{head}</head><body>"
        '<h1 id="host-title">Host page</h1><p id="host-p">The host\'s paragraph.</p>'
        f'{"".join(parts)}<p id="host-end">The host\'s last word.</p></body></html>'
    )


def _plotly() -> t.Any:
    go = pytest.importorskip("plotly.graph_objects")
    return go.Figure(go.Scatter(x=[1, 2, 3], y=[3, 1, 2]))


def _report() -> bf.Briefing:
    return bf.Briefing(
        bf.Select(
            bf.Group(
                bf.Toggle(bf.Text("Hidden detail"), label="More"),
                bf.lab.CalendarHeatmap(_DAYS, date="day", value="amount"),
                bf.Plot(_plotly()),
                label="Summary",
            ),
            bf.DataTable(_ROWS, label="Detail"),
        )
    )


def _page_with_three(viewer: Viewer) -> Page:
    light = bf.stringify(_report(), full_html=False, embed_id="light")
    dark = bf.stringify(_report(), full_html=False, embed_id="dark", formatting=bf.Formatting.dark())
    bare_blocks = bf.Select(bf.Text("First", label="One"), bf.Text("Second", label="Two"))
    bare = bf.stringify(bare_blocks, full_html=False, embed_id="bare", include_assets=False)
    return viewer.open(_host(light, dark, bare, head=bf.embed_assets(bare_blocks)))


def _words(root: Locator) -> list[str]:
    return root.locator(".bf-dt__table tbody tr:not([hidden]) td:last-child").all_inner_texts()


def test_tabs_and_toggles_work_in_each_fragment(viewer: Viewer) -> None:
    page = _page_with_three(viewer)
    light, dark, bare = page.locator("#light"), page.locator("#dark"), page.locator("#bare")
    light.get_by_role("tab", name="Detail").click()
    expect(light.get_by_role("tab", name="Detail")).to_have_attribute("aria-selected", "true")
    expect(dark.get_by_role("tab", name="Summary")).to_have_attribute("aria-selected", "true")
    dark.get_by_role("button", name="More").click()
    expect(dark.get_by_text("Hidden detail")).to_be_visible()
    expect(light.locator(".bf-toggle__header")).to_have_attribute("aria-expanded", "false")
    bare.get_by_role("tab", name="Two").click()  # its scripts came from embed_assets in the <head>
    expect(bare.get_by_text("Second")).to_be_visible()


def test_datatable_sort_and_search_work_in_each_fragment(viewer: Viewer) -> None:
    page = _page_with_three(viewer)
    light, dark = page.locator("#light"), page.locator("#dark")
    for root in (light, dark):
        root.get_by_role("tab", name="Detail").click()
    dark.locator('.bf-dt__th[data-col="0"]').click()
    assert _words(dark) == ["one", "two", "three"]
    assert _words(light) == ["three", "one", "two"]
    light.locator(".bf-dt__search").fill("two")
    expect(light.locator(".bf-dt__count")).to_have_text("1 row")
    expect(dark.locator(".bf-dt__count")).to_have_text("3 rows")


def test_plotly_hover_and_calendar_tooltips_work_in_each_fragment(viewer: Viewer) -> None:
    page = _page_with_three(viewer)
    for embed_id in ("light", "dark"):
        root = page.locator(f"#{embed_id}")
        root.locator(".scatterlayer .point").first.hover(force=True)
        expect(root.locator(".hoverlayer .hovertext")).to_have_count(1)
        root.locator('rect[data-date="2026-01-05"]').hover()
        expect(root.locator(".bf-cal__tip")).to_be_visible()
    expect(page.locator("#light .bf-cal__tip")).to_be_hidden()  # one tooltip at a time


def test_fragments_leave_the_host_page_as_it_was(viewer: Viewer) -> None:
    plain = viewer.open(_host())
    before = {i: plain.locator(f"#{i}").evaluate(_STYLE_JS) for i in ("host-title", "host-p", "host-end")}
    background = plain.evaluate("getComputedStyle(document.body).backgroundColor")
    page = _page_with_three(viewer)
    after = {i: page.locator(f"#{i}").evaluate(_STYLE_JS) for i in ("host-title", "host-p", "host-end")}
    assert after == before
    assert page.evaluate("getComputedStyle(document.body).backgroundColor") == background
    # Each fragment paints its own theme.
    assert page.locator("#dark").evaluate("e => getComputedStyle(e).backgroundColor") == "rgb(15, 23, 42)"


# ── a hostile host ────────────────────────────────────────────────────────────

_HOSTILE = "html { font-size: 10px; } * { font-family: serif; } p { margin: 3em 0; } table { margin: 3em; }"

#: Elements whose look must not change between a report and a fragment on the hostile host.
_LOOKS = [".bf-text h2", ".bf-text p", ".bf-text li", ".bf-text code", ".bf-table__table th",
          ".bf-table__table td", ".bf-dt__th", ".bf-dt__search", ".bf-bignumber__value", ".bf-alert__title",
          ".bf-alert__message", ".bf-block.bf-alert"]


def _styled() -> bf.Briefing:
    return bf.Briefing(
        bf.Text("## Results\n\nA paragraph with `code` in it.\n\n- one item\n- another"),
        bf.Group(bf.BigNumber("Revenue", "$4.2M"), bf.Alert("Margin dropped.", title="Heads up"), columns=2),
        bf.Table(_ROWS),
        bf.DataTable(_ROWS),
    )


def _looks(page: Page, scope: str) -> dict[str, list[str]]:
    return {sel: page.locator(f"{scope} {sel}").first.evaluate(_STYLE_JS) for sel in _LOOKS}


def test_a_hostile_host_changes_nothing_in_the_fragment(viewer: Viewer) -> None:
    report = viewer.open(_styled())
    expected = _looks(report, ".bf-report")
    page = viewer.open(_host(bf.stringify(_styled(), full_html=False, embed_id="frag"), css=_HOSTILE))
    assert page.locator("#host-p").evaluate("e => getComputedStyle(e).fontFamily") == "serif"  # the host's rules apply
    assert _looks(page, "#frag") == expected


# ── links and print ───────────────────────────────────────────────────────────


def test_a_link_in_a_fragment_scrolls_within_it_and_leaves_the_address(viewer: Viewer) -> None:
    filler = "\n\n".join(["A paragraph that pushes the rest below the fold."] * 40)
    linked = bf.Briefing(
        bf.Page(bf.Text("See [the method](#detail/methodology)."), title="Summary"),
        bf.Page(bf.Text(filler), bf.Toggle(bf.Text("## Methodology {#methodology}"), label="More"),
                title="Detail", name="detail"),
    )
    page = viewer.open(_host(bf.stringify(linked, full_html=False, embed_id="doc")))
    url = page.url
    root = page.locator("#doc")
    root.get_by_role("link", name="the method").click()
    expect(root.get_by_role("tab", name="Detail")).to_have_attribute("aria-selected", "true")
    expect(root.get_by_role("button", name="More")).to_have_attribute("aria-expanded", "true")
    expect(root.get_by_role("heading", name="Methodology")).to_be_in_viewport()
    root.get_by_role("tab", name="Summary").click()
    assert page.url == url


def test_a_fragment_prints_open_like_a_report(viewer: Viewer) -> None:
    page = viewer.open(_host(bf.stringify(_report(), full_html=False, embed_id="light")))
    root = page.locator("#light")
    page.evaluate("window.dispatchEvent(new Event('beforeprint'))")
    expect(root.get_by_text("Hidden detail")).to_be_visible()
    expect(root.locator(".bf-print-label")).to_have_text(["Summary", "Detail"])
    page.evaluate("window.dispatchEvent(new Event('afterprint'))")
    expect(root.get_by_text("Hidden detail")).to_be_hidden()
