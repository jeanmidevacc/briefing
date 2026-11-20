"""Links to pages, tabs and headings, as a reader follows and shares them (#24)."""
from __future__ import annotations

from playwright.sync_api import Page, expect

import briefing as bf
from tests.test_browser.conftest import Viewer, split_report

_FILLER = "\n\n".join(["A paragraph that pushes the rest of the page below the fold."] * 40)


def _report() -> bf.Briefing:
    return bf.Briefing(
        bf.Page(bf.Text("# Summary\n\nSee [the method](#detail/methodology)."), title="Summary"),
        bf.Page(
            bf.Select(bf.Text("North rows", label="North"), bf.Text("South rows", label="South", name="south"),
                      name="by-region"),
            bf.Select(bf.Text("One shown", label="One"), bf.Text("Two shown", label="Two", name="two"),
                      type="dropdown"),
            bf.Text(_FILLER),
            bf.Toggle(bf.Text("## Methodology {#methodology}\n\nHow it was measured."), label="More"),
            title="Detail",
            name="detail",
        ),
    )


def _open_at(viewer: Viewer, link: str) -> Page:
    """Load the report afresh at report.html#link, as when a shared link is opened."""
    page = viewer.open(_report())
    url = page.url
    page.goto("about:blank")
    page.goto(f"{url}#{link}")
    return page


def _hash(page: Page) -> str:
    return page.url.partition("#")[2]


def test_a_link_opens_its_page_and_toggle_and_scrolls_to_the_heading(viewer: Viewer) -> None:
    page = _open_at(viewer, "detail/methodology")
    assert page.url.startswith("file://")
    expect(page.get_by_role("tab", name="Detail")).to_have_attribute("aria-selected", "true")
    expect(page.get_by_role("button", name="More")).to_have_attribute("aria-expanded", "true")
    expect(page.get_by_role("heading", name="Methodology")).to_be_in_viewport()
    assert _hash(page) == "detail/methodology"


def test_a_link_opens_a_tab_inside_a_page(viewer: Viewer) -> None:
    page = _open_at(viewer, "detail/south")
    expect(page.get_by_role("tab", name="Detail")).to_have_attribute("aria-selected", "true")
    expect(page.get_by_role("tab", name="South")).to_have_attribute("aria-selected", "true")
    expect(page.get_by_text("South rows")).to_be_visible()


def test_a_link_opens_a_dropdown_option(viewer: Viewer) -> None:
    page = _open_at(viewer, "detail/two")
    expect(page.locator(".bf-select__select")).to_have_value("1")
    expect(page.get_by_text("Two shown")).to_be_visible()


def test_an_unknown_link_leaves_the_report_as_it_opens(viewer: Viewer) -> None:
    page = _open_at(viewer, "nowhere")
    expect(page.get_by_role("tab", name="Summary")).to_have_attribute("aria-selected", "true")


def test_choosing_a_tab_writes_its_link_without_adding_history(viewer: Viewer) -> None:
    page = viewer.open(_report())
    entries = page.evaluate("history.length")
    page.get_by_role("tab", name="Detail").click()
    assert _hash(page) == "detail"
    page.get_by_role("tab", name="South").click()
    assert _hash(page) == "detail/south"
    page.get_by_role("tab", name="North").click()  # unnamed: the closest named block around it
    assert _hash(page) == "detail/by-region"
    page.locator(".bf-select__select").select_option("1")
    assert _hash(page) == "detail/two"
    page.get_by_role("tab", name="Summary").click()  # an unnamed page has no link
    assert "#" not in page.url
    assert page.evaluate("history.length") == entries


def test_a_reload_keeps_the_open_tab(viewer: Viewer) -> None:
    page = viewer.open(_report())
    page.get_by_role("tab", name="Detail").click()
    page.get_by_role("tab", name="South").click()
    page.reload()
    expect(page.get_by_role("tab", name="South")).to_have_attribute("aria-selected", "true")
    expect(page.get_by_text("South rows")).to_be_visible()


def test_a_link_in_the_text_opens_its_target(viewer: Viewer) -> None:
    page = viewer.open(_report())
    page.get_by_role("link", name="the method").click()
    expect(page.get_by_role("button", name="More")).to_have_attribute("aria-expanded", "true")
    expect(page.get_by_role("heading", name="Methodology")).to_be_in_viewport()


def test_a_named_heading_shows_a_copy_link_icon_on_hover(viewer: Viewer) -> None:
    page = _open_at(viewer, "detail/methodology")
    page.context.grant_permissions(["clipboard-read", "clipboard-write"])
    heading = page.get_by_role("heading", name="Methodology")
    icon = heading.get_by_role("link", name="Copy link to this section")
    actions = heading.locator(".bf-heading-actions")  # where the icon and, later, other buttons sit
    page.mouse.move(0, 0)
    expect(actions).to_have_css("opacity", "0")
    heading.hover()
    expect(actions).to_have_css("opacity", "1")
    page.get_by_role("tab", name="Detail").click()
    assert _hash(page) == "detail"
    heading.hover()
    icon.click()
    assert _hash(page) == "detail/methodology"
    expect(icon).to_have_attribute("data-copied", "")
    assert page.evaluate("navigator.clipboard.readText()") == page.url
    page.evaluate("window.dispatchEvent(new Event('beforeprint'))")
    expect(icon).to_be_hidden()


def test_links_inside_an_embedded_root_leave_the_address_alone(viewer: Viewer) -> None:
    head, body, scripts = split_report(bf.stringify(_report()))
    init = "briefing.init(document.getElementById('root'));"
    page = viewer.open(f'{head}</head><body><section id="root">{body}</section>'
                       f"<script>{scripts}\n{init}</script></body></html>")
    url = page.url
    page.goto("about:blank")
    page.goto(f"{url}#detail/south")
    expect(page.get_by_role("tab", name="Summary")).to_have_attribute("aria-selected", "true")  # address ignored
    page.get_by_role("link", name="the method").click()
    expect(page.get_by_role("button", name="More")).to_have_attribute("aria-expanded", "true")
    expect(page.get_by_role("heading", name="Methodology")).to_be_in_viewport()
    page.get_by_role("tab", name="South").click()
    assert _hash(page) == "detail/south"  # unchanged since the page opened
