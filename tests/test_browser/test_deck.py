"""A deck in the browser (#197): one slide at a time, scaled to the window, keys, links, overview, fit."""
from __future__ import annotations

import pandas as pd
from playwright.sync_api import Page, expect

import briefing as bf
from tests.scenarios import plotly_figure
from tests.test_browser.conftest import Viewer


def _deck() -> bf.deck.Deck:
    return bf.deck.Deck(
        bf.deck.Slide(title="Part one"),
        bf.deck.Slide(bf.Text("Revenue grew."), bf.Text("## Method {#method}", name="note"), title="Summary",
                      name="summary"),
        bf.deck.Slide(bf.DataTable(pd.DataFrame({"n": range(30)}), name="rows"), title="Rows"),
        bf.deck.Slide(bf.Plot(plotly_figure()), title="Chart"),
        footer="Team",
    )


def _open(viewer: Viewer, deck: bf.deck.Deck | None = None, hash_: str = "") -> Page:
    page = viewer.open(bf.deck.to_html(deck or _deck(), name="Deck"))
    if hash_:
        page.goto(page.url.split("#")[0] + hash_)
        page.wait_for_load_state("load")
    return page


def _current(page: Page) -> str:
    return page.locator(".bf-slide--current").get_attribute("data-bf-slide") or ""


def test_one_slide_shows_at_a_time(viewer: Viewer) -> None:
    page = _open(viewer)
    expect(page.locator(".bf-deck")).to_have_class("bf-deck bf-deck--live")
    expect(page.locator(".bf-slide--current")).to_have_count(1)
    assert _current(page) == "1"
    assert page.locator(".bf-slide").nth(1).evaluate("el => getComputedStyle(el).visibility") == "hidden"
    expect(page.locator(".bf-deck__count")).to_have_text("1 / 4")
    expect(page.locator('[data-bf-go="prev"]')).to_be_disabled()


def test_the_stage_is_scaled_to_fit_the_window(viewer: Viewer) -> None:
    page = _open(viewer)
    box = page.locator(".bf-deck__stage").bounding_box()
    viewport = page.viewport_size
    assert box is not None and viewport is not None
    assert abs(box["width"] / box["height"] - 16 / 9) < 0.01
    assert box["width"] <= viewport["width"] + 1 and box["height"] <= viewport["height"] + 1
    assert max(box["width"] / viewport["width"], box["height"] / viewport["height"]) > 0.99  # it fills one side


def test_keys_move_between_slides_and_the_address_follows(viewer: Viewer) -> None:
    page = _open(viewer)
    page.keyboard.press("ArrowRight")
    assert _current(page) == "2" and page.url.endswith("#2")
    page.keyboard.press("Space")
    page.keyboard.press("PageDown")
    assert _current(page) == "4"
    page.keyboard.press("ArrowRight")  # the last slide stays
    assert _current(page) == "4"
    expect(page.locator('[data-bf-go="next"]')).to_be_disabled()
    page.keyboard.press("Home")
    assert _current(page) == "1"
    page.keyboard.press("End")
    page.keyboard.press("ArrowLeft")
    assert _current(page) == "3"


def test_the_buttons_move_between_slides(viewer: Viewer) -> None:
    page = _open(viewer)
    page.click('[data-bf-go="next"]')
    page.click('[data-bf-go="next"]')
    page.click('[data-bf-go="prev"]')
    assert _current(page) == "2"
    expect(page.locator(".bf-deck__count")).to_have_text("2 / 4")


def test_a_link_opens_its_slide(viewer: Viewer) -> None:
    assert _current(_open(viewer, hash_="#3")) == "3"
    assert _current(_open(viewer, hash_="#summary")) == "2"
    assert _current(_open(viewer, hash_="#rows")) == "3"
    page = _open(viewer, hash_="#summary/method")
    assert _current(page) == "2"
    page.evaluate("location.hash = '#4'")
    page.wait_for_function("document.querySelector('.bf-slide--current').dataset.bfSlide === '4'")


def test_the_overview_shows_every_slide_and_picks_one(viewer: Viewer) -> None:
    page = _open(viewer)
    page.keyboard.press("o")
    expect(page.locator(".bf-deck")).to_have_class("bf-deck bf-deck--live bf-deck--overview")
    expect(page.locator('[data-bf-go="overview"]')).to_have_attribute("aria-pressed", "true")
    for i in range(4):
        assert page.locator(".bf-slide").nth(i).evaluate("el => getComputedStyle(el).visibility") == "visible"
    page.locator(".bf-slide").nth(2).click()
    expect(page.locator(".bf-deck")).to_have_class("bf-deck bf-deck--live")
    assert _current(page) == "3"


def test_escape_leaves_the_overview(viewer: Viewer) -> None:
    page = _open(viewer)
    page.click('[data-bf-go="overview"]')
    page.keyboard.press("ArrowRight")
    page.keyboard.press("Escape")
    expect(page.locator(".bf-deck")).to_have_class("bf-deck bf-deck--live")
    assert _current(page) == "2"


def test_typing_in_a_search_box_does_not_move_the_slides(viewer: Viewer) -> None:
    page = _open(viewer, hash_="#3")
    search = page.locator(".bf-slide--current input").first
    search.click()
    search.press("ArrowRight")
    search.type("1 2")
    assert _current(page) == "3"


def test_a_table_on_a_slide_shows_ten_rows_a_page(viewer: Viewer) -> None:
    page = _open(viewer, hash_="#3")
    expect(page.locator(".bf-slide--current tbody tr")).to_have_count(10)


def test_a_chart_on_a_later_slide_is_as_wide_as_its_slide(viewer: Viewer) -> None:
    page = _open(viewer)
    page.keyboard.press("End")
    width = page.locator(".bf-slide--current .js-plotly-plot").evaluate("el => el.offsetWidth")
    room = page.locator(".bf-slide--current .bf-slide__content").evaluate("el => el.offsetWidth")
    assert abs(width - room) < 4, (width, room)


def test_content_that_is_too_tall_shrinks_to_fit(viewer: Viewer) -> None:
    rows = pd.DataFrame({"n": range(12)})
    deck = bf.deck.Deck(bf.deck.Slide(bf.Table(rows), title="Tall"))
    page = _open(viewer, deck)
    fit = float(page.locator(".bf-slide__content").evaluate("el => el.style.getPropertyValue('--bf-fit')"))
    assert 0.7 <= fit < 1
    body = page.locator(".bf-slide__body").bounding_box()
    content = page.locator(".bf-slide__content").bounding_box()
    assert body is not None and content is not None
    assert content["height"] <= body["height"] + 1
    assert abs(content["width"] - body["width"]) < 2  # as wide as the slide, not just smaller
    expect(page.locator(".bf-slide--overflow")).to_have_count(0)


def test_content_far_too_tall_scrolls_and_says_so(viewer: Viewer) -> None:
    deck = bf.deck.Deck(bf.deck.Slide(bf.Table(pd.DataFrame({"n": range(60)})), title="Far too tall"))
    page = _open(viewer, deck)
    expect(page.locator(".bf-slide--overflow")).to_have_count(1)
    assert page.locator(".bf-slide__content").evaluate("el => el.style.getPropertyValue('--bf-fit')") == "0.7"
    assert page.locator(".bf-slide__body").evaluate("el => getComputedStyle(el).overflowY") == "auto"


def test_a_tab_on_a_slide_still_switches(viewer: Viewer) -> None:
    deck = bf.deck.Deck(bf.deck.Slide(bf.Select(bf.Text("first", label="A"), bf.Text("second", label="B"))))
    page = _open(viewer, deck)
    page.get_by_role("tab", name="B").click()
    expect(page.get_by_text("second")).to_be_visible()
    assert _current(page) == "1"
