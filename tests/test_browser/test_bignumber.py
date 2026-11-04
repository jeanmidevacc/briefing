"""BigNumber colours follow is_positive_intent, independent of the arrow (#14)."""
from __future__ import annotations

import briefing as bf
from tests.test_browser.conftest import Viewer

GREEN, RED = "rgb(22, 163, 74)", "rgb(220, 38, 38)"


def test_four_combinations(viewer: Viewer) -> None:
    report = bf.Briefing(bf.Group(
        bf.BigNumber("Revenue", "$4.2M", change="+12%", is_upward_change=True, is_positive_intent=True),
        bf.BigNumber("Return Rate", "8.0 %", change="+0.2%", is_upward_change=True, is_positive_intent=False),
        bf.BigNumber("Churn", "2.1 %", change="-0.4%", is_upward_change=False, is_positive_intent=True),
        bf.BigNumber("Margin", "31 %", change="-0.8%", is_upward_change=False, is_positive_intent=False),
        columns=4,
    ))
    page = viewer.open(report)
    changes = page.locator(".bf-bignumber__change")
    seen = [(changes.nth(i).inner_text()[0], changes.nth(i).evaluate("e => getComputedStyle(e).color"))
            for i in range(4)]
    assert seen == [("▲", GREEN), ("▲", RED), ("▼", GREEN), ("▼", RED)]


def test_without_the_flag_colour_follows_the_arrow(viewer: Viewer) -> None:
    report = bf.Briefing(
        bf.BigNumber("Up", 1, change="+1%", is_upward_change=True),
        bf.BigNumber("Down", 1, change="-1%", is_upward_change=False),
    )
    changes = viewer.open(report).locator(".bf-bignumber__change")
    assert [changes.nth(i).evaluate("e => getComputedStyle(e).color") for i in range(2)] == [GREEN, RED]


def test_change_without_direction_is_neutral(viewer: Viewer) -> None:
    report = bf.Briefing(
        bf.BigNumber("Users", "142K", change="+3%"),
        bf.BigNumber("NPS", 41, change="+2", is_positive_intent=True),
    )
    page = viewer.open(report)
    changes = page.locator(".bf-bignumber__change")
    muted = page.evaluate("() => getComputedStyle(document.documentElement).getPropertyValue('--bf-muted').trim()")
    assert muted == "#6b7280"
    first = (changes.nth(0).inner_text(), changes.nth(0).evaluate("e => getComputedStyle(e).color"))
    second = (changes.nth(1).inner_text(), changes.nth(1).evaluate("e => getComputedStyle(e).color"))
    assert first == ("+3%", "rgb(107, 114, 128)")  # muted, no arrow
    assert second == ("+2", GREEN)  # colour only, no arrow
