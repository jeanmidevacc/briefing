"""RecInspector as a reader uses it (#18): pick and search users, switch titles and ids."""
from __future__ import annotations

import pandas as pd
from playwright.sync_api import Locator, Page, expect

import briefing as bf
from briefing.lab._render_recs import user_html
from tests.scenarios import _recs_frames
from tests.test_browser.conftest import Viewer


def _block(page: Page) -> Locator:
    return page.locator(".bf-recs")


def _user(page: Page) -> Locator:
    return page.locator(".bf-recs__user")


def test_the_script_draws_every_user_as_python_does(viewer: Viewer) -> None:
    block = bf.lab.RecInspector(**_recs_frames())
    page = viewer.open(bf.Briefing(block))
    for index in range(len(block.inspection.users)):
        same: bool = _block(page).evaluate(
            """(b, args) => {
                b.briefingRecs.show(args.index);
                const t = b.ownerDocument.createElement('template');
                t.innerHTML = args.html;
                const drawn = b.querySelector('.bf-recs__user');
                return drawn.childNodes.length === t.content.childNodes.length &&
                    Array.from(drawn.childNodes).every((n, i) => n.isEqualNode(t.content.childNodes[i]));
            }""",
            {"index": index, "html": user_html(block.inspection, index)},
        )
        assert same, block.inspection.users[index].id


def test_picking_a_user_shows_them(viewer: Viewer) -> None:
    page = viewer.open(bf.Briefing(bf.lab.RecInspector(**_recs_frames())))
    expect(page.locator(".bf-recs__controls")).to_be_visible()
    page.get_by_label("User", exact=True).select_option(label="ben · 2 interactions")
    expect(_user(page).locator(".bf-recs__user-id")).to_have_text("ben")
    expect(_user(page)).to_have_attribute("data-user", "1")
    page.get_by_label("User", exact=True).select_option(label="eve · 0 interactions")
    expect(_user(page).locator(".bf-recs__none")).to_have_text(["No history.", "No list.", "No list."])


def test_searching_narrows_the_list_and_shows_the_first_match(viewer: Viewer) -> None:
    page = viewer.open(bf.Briefing(bf.lab.RecInspector(**_recs_frames())))
    page.get_by_label("Search users").fill("e")
    expect(page.locator(".bf-recs__shown")).to_have_text("2 of 3 users")  # ben, eve
    expect(_user(page).locator(".bf-recs__user-id")).to_have_text("ben")
    page.get_by_label("Search users").fill("zzz")
    expect(page.locator(".bf-recs__shown")).to_have_text("No user matches")
    expect(_user(page).locator(".bf-recs__user-id")).to_have_text("ben")  # stays on the last one shown
    page.get_by_label("Search users").fill("")
    expect(page.locator(".bf-recs__shown")).to_have_text("")


def test_the_switch_shows_ids_instead_of_titles(viewer: Viewer) -> None:
    page = viewer.open(bf.Briefing(bf.lab.RecInspector(**_recs_frames())))
    item = _user(page).locator('.bf-recs__strip [data-item="i2"]')
    expect(item.locator(".bf-recs__title")).to_be_visible()
    expect(item.locator(".bf-recs__id")).to_be_hidden()
    page.get_by_role("button", name="ids").click()
    expect(item.locator(".bf-recs__title")).to_be_hidden()
    expect(item.locator(".bf-recs__id")).to_be_visible()
    expect(page.get_by_role("button", name="ids")).to_have_attribute("aria-pressed", "true")
    page.get_by_label("User", exact=True).select_option(label="ben · 2 interactions")  # the next user keeps the switch
    expect(_user(page).locator('.bf-recs__list [data-item="i1"] .bf-recs__id').first).to_be_visible()
    page.get_by_role("button", name="titles").click()
    expect(_user(page).locator('.bf-recs__list [data-item="i1"] .bf-recs__title').first).to_be_visible()


def test_an_untitled_item_always_shows_its_id(viewer: Viewer) -> None:
    page = viewer.open(bf.Briefing(bf.lab.RecInspector(**_recs_frames())))
    expect(_user(page).locator('.bf-recs__strip [data-item="i3"] .bf-recs__id')).to_be_visible()


def test_two_inspectors_on_a_page_keep_their_own_user(viewer: Viewer) -> None:
    frames = _recs_frames()
    page = viewer.open(bf.Briefing(bf.lab.RecInspector(**frames), bf.lab.RecInspector(**frames)))
    page.get_by_label("User", exact=True).first.select_option(label="ben · 2 interactions")
    expect(page.locator(".bf-recs__user-id")).to_have_text(["ben", "ana"])


def test_a_long_history_scrolls_inside_the_strip(viewer: Viewer) -> None:
    history = pd.DataFrame({"user": ["a"] * 60, "item": [f"i{i}" for i in range(60)],
                            "timestamp": pd.date_range("2026-01-01", periods=60)})
    recs = pd.DataFrame({"user": ["a"], "item": ["i1"], "rank": [1], "model": ["m"]})
    page = viewer.open(bf.Briefing(bf.lab.RecInspector(history=history, recs=recs)))
    strip = page.locator(".bf-recs__strip")
    wider: bool = strip.evaluate("s => s.scrollWidth > s.clientWidth")
    page_scrolls: bool = page.evaluate("() => document.documentElement.scrollWidth > window.innerWidth")
    assert wider and not page_scrolls
