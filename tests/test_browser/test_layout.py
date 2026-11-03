"""Tabs, dropdowns and toggles show the right panel."""
from __future__ import annotations

from playwright.sync_api import expect

import briefing as bf
from tests.test_browser.conftest import Viewer


def _tabs() -> bf.Briefing:
    return bf.Briefing(bf.Select(bf.Text("alpha", label="A"), bf.Text("beta", label="B"), bf.Text("gamma", label="C")))


def test_tabs_show_the_clicked_panel(viewer: Viewer) -> None:
    page = viewer.open(_tabs())
    panels = page.locator(".bf-select__panel")
    expect(panels.nth(0)).to_be_visible()
    expect(panels.nth(1)).to_be_hidden()
    page.get_by_role("tab", name="B").click()
    expect(panels.nth(1)).to_be_visible()
    expect(panels.nth(0)).to_be_hidden()
    expect(page.get_by_role("tab", name="B")).to_have_attribute("aria-selected", "true")


def test_arrow_keys_move_between_tabs(viewer: Viewer) -> None:
    page = viewer.open(_tabs())
    page.get_by_role("tab", name="A").focus()
    page.keyboard.press("ArrowRight")
    expect(page.get_by_role("tab", name="B")).to_be_focused()
    expect(page.get_by_text("beta")).to_be_visible()
    page.keyboard.press("End")
    expect(page.get_by_text("gamma")).to_be_visible()
    page.keyboard.press("Home")
    expect(page.get_by_text("alpha")).to_be_visible()


def test_dropdown_shows_the_chosen_panel(viewer: Viewer) -> None:
    report = bf.Briefing(bf.Select(bf.Text("first", label="One"), bf.Text("second", label="Two"), type="dropdown"))
    page = viewer.open(report)
    expect(page.get_by_text("first")).to_be_visible()
    page.locator(".bf-select__select").select_option(label="Two")
    expect(page.get_by_text("second")).to_be_visible()
    expect(page.get_by_text("first")).to_be_hidden()


def test_toggle_opens_and_closes(viewer: Viewer) -> None:
    page = viewer.open(bf.Briefing(bf.Toggle(bf.Text("hidden detail"), label="Details")))
    header = page.locator(".bf-toggle__header")
    expect(page.get_by_text("hidden detail")).to_be_hidden()
    header.click()
    expect(page.get_by_text("hidden detail")).to_be_visible()
    expect(header).to_have_attribute("aria-expanded", "true")
    header.press("Enter")
    expect(page.get_by_text("hidden detail")).to_be_hidden()


def test_nested_toggle_only_opens_itself(viewer: Viewer) -> None:
    inner = bf.Toggle(bf.Text("inner body"), label="Inner")
    report = bf.Briefing(bf.Toggle(bf.Text("outer body"), inner, label="Outer"))
    page = viewer.open(report)
    page.get_by_role("button", name="Outer").click()
    expect(page.get_by_text("outer body")).to_be_visible()
    expect(page.get_by_text("inner body")).to_be_hidden()
