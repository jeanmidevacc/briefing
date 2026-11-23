"""bf.deck.from_report (#199, experimental): a report's first draft as a deck."""
from __future__ import annotations

import typing as t
import warnings
from collections.abc import Iterator

import pandas as pd
import pytest

import briefing as bf
from briefing import _experimental
from tests.banner_images import RED_SVG
from tests.contract import RULES, parse_report
from tests.scenarios import SCENARIOS, Frames


@pytest.fixture(autouse=True)
def _quiet() -> Iterator[None]:
    """Each test sees the experimental warning as if it were the session's first call; most ignore it."""
    _experimental._warned.clear()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", bf.ExperimentalWarning)
        yield


def _shape(deck: bf.deck.Deck) -> list[tuple[str | None, str | None, list[str]]]:
    return [(s.title, s.name, [type(b).__name__ for b in s.blocks]) for s in deck.slides]


def test_it_warns_that_it_is_experimental_once_at_the_callers_line() -> None:
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        bf.deck.from_report(bf.Text("a"))
        bf.deck.from_report(bf.Text("b"))
    found = [w for w in caught if issubclass(w.category, bf.ExperimentalWarning)]
    assert len(found) == 1
    assert "bf.deck.from_report is experimental" in str(found[0].message)
    assert found[0].filename == __file__


def test_each_page_starts_a_slide_with_its_title_and_name() -> None:
    report = bf.Briefing(
        bf.Page(bf.Text("Intro."), bf.BigNumber("A", 1), title="Summary", name="summary"),
        bf.Page(bf.Group(bf.Text("a"), bf.Text("b")), title="Detail", name="detail"),
        footer="Team",
    )
    deck = bf.deck.from_report(report)
    assert _shape(deck) == [("Summary", "summary", ["Text", "BigNumber"]), ("Detail", "detail", ["Group"])]
    assert deck.footer == "Team"


def test_title_opens_the_deck_with_a_section_slide() -> None:
    assert _shape(bf.deck.from_report(bf.Text("a"), title="Q3 review"))[0] == ("Q3 review", None, [])


def test_a_banner_that_opens_the_report_is_the_title_slide() -> None:
    deck = bf.deck.from_report(bf.Briefing(bf.Banner("# Q3", image=RED_SVG), bf.Text("Body.")))
    assert _shape(deck) == [(None, None, ["Banner"]), (None, None, ["Text"])]
    later = bf.deck.from_report(bf.Briefing(bf.Text("Body."), bf.Banner("# Q3", image=RED_SVG)))
    assert _shape(later) == [(None, None, ["Text", "Banner"])]


def test_headings_split_a_text_into_slides() -> None:
    text = "Before.\n\n# Part two\n\nAfter.\n\n## Numbers {#numbers}\n\nSome.\n\n## Method {#auto}\n\nHow."
    deck = bf.deck.from_report(bf.Text(text))
    assert _shape(deck) == [
        (None, None, ["Text"]),
        ("Part two", None, []),
        (None, None, ["Text"]),
        ("Numbers", "numbers", ["Text"]),
        ("Method", "method", ["Text"]),
    ]
    assert [b.content for s in deck.slides for b in s.blocks if isinstance(b, bf.Text)] == [
        "Before.", "After.", "Some.", "How."]


def test_a_break_starts_a_slide_that_keeps_the_title() -> None:
    deck = bf.deck.from_report(bf.Text("## Results\n\nFirst half.\n\n---\n\nSecond half."))
    assert _shape(deck) == [("Results", None, ["Text"]), ("Results", None, ["Text"])]


def test_headings_and_breaks_inside_code_stay_code() -> None:
    code = "```markdown\n## not a slide\n---\n```"
    deck = bf.deck.from_report(bf.Text(f"## Example\n\n{code}"))
    assert _shape(deck) == [("Example", None, ["Text"])]
    assert t.cast(bf.Text, deck.slides[0].blocks[0]).content == code


def test_a_page_that_opens_with_a_heading_lends_that_slide_its_name() -> None:
    report = bf.Briefing(bf.Page(bf.Text("## Overview\n\nIntro."), title="Summary", name="summary"),
                         bf.Page(bf.Text("x"), title="Other"))
    assert _shape(bf.deck.from_report(report))[0] == ("Overview", "summary", ["Text"])


def _page(name: str) -> bf.Page:
    return bf.Page(bf.Text("## One\n\na\n\n## Two\n\nb"), bf.DataTable(pd.DataFrame({"a": [1]}), name="rows"),
                   title=name.title(), name=name)


def test_slides_from_a_named_page_stay_named_so_block_names_dont_clash() -> None:
    page = _page
    deck = bf.deck.from_report(bf.Briefing(page("north"), page("south")))
    names = [s.name for s in deck.slides]
    assert None not in names and len(set(names)) == len(names)
    html = bf.deck.to_html(deck)  # two blocks named "rows" render without a clash
    assert html.count('data-bf-link') >= 2


def test_a_heading_name_used_twice_gets_a_number() -> None:
    report = bf.Briefing(bf.Page(bf.Text("## Notes {#notes}\n\na"), title="A", name="a"),
                         bf.Page(bf.Text("## Notes {#notes}\n\nb"), title="B", name="b"))
    assert [s.name for s in bf.deck.from_report(report).slides] == ["notes", "notes-2"]


def test_a_texts_name_stays_on_its_first_piece() -> None:
    deck = bf.deck.from_report(bf.Text("Intro.\n\n## Next\n\nMore.", name="summary"))
    texts = [b for s in deck.slides for b in s.blocks]
    assert [b.name for b in texts] == ["summary", None]


def test_the_result_is_an_ordinary_deck_to_adjust() -> None:
    deck = bf.deck.from_report(bf.Text("## A\n\na\n\n## B\n\nb\n\n## C\n\nc"))
    del deck.slides[1]
    deck.slides[0].title = "First"
    assert [s.title for s in deck.slides] == ["First", "C"]
    assert "First" in bf.deck.to_html(deck)


@pytest.mark.filterwarnings("ignore")
@pytest.mark.parametrize("scenario", list(SCENARIOS))
def test_every_scenario_converts_to_a_deck_that_keeps_the_contract(scenario: str, frames: Frames) -> None:
    deck = bf.deck.from_report(SCENARIOS[scenario](frames))
    first, second = bf.deck.to_html(deck), bf.deck.to_html(bf.deck.from_report(SCENARIOS[scenario](frames)))
    soup = parse_report(first)
    for rule in RULES.values():
        rule(soup)
    assert first == second  # the same report gives the same deck
