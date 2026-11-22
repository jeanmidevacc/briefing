"""Cards as a reader uses them (#27): a linked card leads anywhere it's clicked, its own links still work."""
from __future__ import annotations

from playwright.sync_api import expect

import briefing as bf
from tests.test_browser.conftest import Viewer


def _report() -> bf.Briefing:
    cards = bf.Group(
        bf.Card("Pizza, delivery and snacks [(source)](#media/method)", title="Food and delivery", icon="🍕",
                tags=["Pizza", "Uber Eats"], link="detail/food"),
        bf.Card("Films and series", title="Streaming", icon="📺", link="media/streaming"),
        bf.Card("Short", title="Short card"),
        min_width="14rem",
    )
    return bf.Briefing(
        bf.Page(cards, title="Overview", name="overview"),
        bf.Page(bf.Text("## Food {#food}\n\nAll about food."), title="Food", name="detail"),
        bf.Page(bf.Text("## Streaming {#streaming}"), bf.Text("## Method {#method}"), title="Media", name="media"),
    )


def test_clicking_anywhere_on_a_card_follows_its_link(viewer: Viewer) -> None:
    page = viewer.open(_report())
    card = page.locator(".bf-card").first
    box = card.bounding_box()
    assert box is not None
    page.mouse.click(box["x"] + box["width"] - 10, box["y"] + box["height"] / 2)  # on the body, not the title
    expect(page.get_by_role("heading", name="Food")).to_be_visible()


def test_a_link_inside_a_linked_card_goes_to_its_own_target(viewer: Viewer) -> None:
    page = viewer.open(_report())
    page.locator(".bf-card").first.get_by_role("link", name="(source)").click()
    expect(page.get_by_role("heading", name="Method")).to_be_visible()


def test_cards_in_a_row_have_the_same_height(viewer: Viewer) -> None:
    page = viewer.open(_report())
    page.set_viewport_size({"width": 1200, "height": 800})
    heights = {round(h) for h in page.locator(".bf-card").evaluate_all(
        "cs => cs.map(c => c.getBoundingClientRect().height)")}
    assert len(heights) == 1


def test_the_keyboard_reaches_a_linked_card_and_shows_it(viewer: Viewer) -> None:
    page = viewer.open(_report())
    page.locator(".bf-card__link").first.focus()
    outline = page.locator(".bf-card").first.evaluate("c => getComputedStyle(c).outlineStyle")
    assert outline == "solid"
    page.keyboard.press("Enter")
    expect(page.get_by_role("heading", name="Food")).to_be_visible()


def test_tags_sit_at_the_bottom_of_a_card(viewer: Viewer) -> None:
    page = viewer.open(_report())
    page.set_viewport_size({"width": 1200, "height": 800})
    card, tags = (page.locator(s).first.bounding_box() for s in (".bf-card", ".bf-card__tags"))
    assert card is not None and tags is not None
    assert card["y"] + card["height"] - (tags["y"] + tags["height"]) < 25  # the padding, not the slack
