"""Accessible dropdown Selects (#29): a name, panels tied to the choice, keyboard choice."""
from __future__ import annotations

from playwright.sync_api import expect

import briefing as bf
from tests.test_browser.conftest import Viewer


def _dropdown(**kwargs: object) -> bf.Briefing:
    return bf.Briefing(bf.Select(bf.Text("North: 412k", label="North"), bf.Text("South: 287k", label="South"),
                                 bf.Text("West: 190k", label="West"), type="dropdown", **kwargs))  # type: ignore[arg-type]


def test_the_accessibility_tree_names_the_choice_and_its_panel(viewer: Viewer) -> None:
    page = viewer.open(_dropdown(label="Region"))
    assert page.locator(".bf-select").aria_snapshot() == (
        '- combobox "Region":\n'
        '  - option "North" [selected]\n'
        '  - option "South"\n'
        '  - option "West"\n'
        '- region "North":\n'
        '  - paragraph: "North: 412k"'
    )
    expect(page.get_by_role("combobox", name="Region")).to_have_attribute("aria-controls",
                                                                           page.locator(".bf-select__panel").first
                                                                           .get_attribute("id") or "")


def test_without_a_label_the_name_still_says_what_it_does(viewer: Viewer) -> None:
    page = viewer.open(_dropdown())
    expect(page.get_by_role("combobox", name="Choose a view")).to_be_visible()


def test_the_keyboard_chooses_and_the_panel_follows(viewer: Viewer) -> None:
    page = viewer.open(_dropdown(label="Region"))
    box = page.get_by_role("combobox", name="Region")
    box.focus()
    page.keyboard.press("ArrowDown")
    expect(page.get_by_role("region", name="South")).to_be_visible()
    expect(page.get_by_text("North: 412k")).to_be_hidden()
    panel_id = page.get_by_role("region", name="South").get_attribute("id")
    expect(box).to_have_attribute("aria-controls", panel_id or "")
    page.keyboard.press("End")
    expect(page.get_by_role("region", name="West")).to_be_visible()
    page.keyboard.press("Home")
    expect(page.get_by_role("region", name="North")).to_be_visible()


def test_focus_shows_only_for_the_keyboard(viewer: Viewer) -> None:
    page = viewer.open(_dropdown(label="Region"))
    box = page.get_by_role("combobox", name="Region")
    page.keyboard.press("Tab")
    while page.evaluate("document.activeElement.tagName") != "SELECT":
        page.keyboard.press("Tab")
    assert box.evaluate("b => getComputedStyle(b).outlineStyle") == "solid"


def test_nested_dropdowns_keep_their_own_panels(viewer: Viewer) -> None:
    inner = bf.Select(bf.Text("inner one", label="I1"), bf.Text("inner two", label="I2"), type="dropdown",
                      label="Inner")
    outer = bf.Select(bf.Group(inner, label="O1"), bf.Text("outer two", label="O2"), type="dropdown", label="Outer")
    page = viewer.open(bf.Briefing(outer))
    page.get_by_role("combobox", name="Inner").select_option(label="I2")
    expect(page.get_by_text("inner two")).to_be_visible()
    expect(page.get_by_role("region", name="O1")).to_be_visible()  # the outer choice is untouched
    page.get_by_role("combobox", name="Outer").select_option(label="O2")
    expect(page.get_by_text("outer two")).to_be_visible()
