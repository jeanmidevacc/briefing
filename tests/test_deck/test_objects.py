"""bf.deck.Deck and bf.deck.Slide (#197): what they hold, and the mistakes they turn away."""
from __future__ import annotations

import typing as t

import pandas as pd
import pytest

import briefing as bf


def test_a_deck_holds_its_slides_in_order() -> None:
    first = bf.deck.Slide(bf.Text("a"), title="One")
    second = bf.deck.Slide(title="Two")
    deck = bf.deck.Deck(first, second, footer="Team")
    assert deck.slides == [first, second]
    assert list(deck) == [first, second]
    assert len(deck) == 2
    assert deck.footer == "Team"
    assert repr(deck) == "Deck(2 slide(s), footer='Team')"


def test_slides_can_be_passed_as_a_list() -> None:
    slides = [bf.deck.Slide(title="One"), bf.deck.Slide(title="Two")]
    assert bf.deck.Deck(slides=slides).slides == slides


def test_a_slide_wraps_strings_and_dataframes_as_a_report_does() -> None:
    slide = bf.deck.Slide("Revenue grew.", pd.DataFrame({"a": [1]}), title="Summary", name="summary")
    assert [type(b).__name__ for b in slide.blocks] == ["Text", "DataTable"]
    assert slide.title == "Summary"
    assert slide.name == "summary"
    assert repr(slide) == "Slide(2 block(s), title='Summary', name='summary')"


def test_a_slide_with_only_a_title_is_a_section_slide() -> None:
    slide = bf.deck.Slide(title="  Part two  ")
    assert slide.blocks == []
    assert slide.title == "Part two"


@pytest.mark.parametrize("title", [None, "", "   "])
def test_an_empty_slide_is_refused(title: str | None) -> None:
    with pytest.raises(bf.BriefingError, match="This Slide is empty"):
        bf.deck.Slide(title=title)


def test_a_title_must_be_text() -> None:
    with pytest.raises(bf.BriefingError, match="Slide 'title' must be text"):
        bf.deck.Slide("a", title=t.cast(t.Any, 3))


def test_a_slide_name_follows_the_block_name_rules() -> None:
    with pytest.raises(bf.BriefingError, match="Invalid block name"):
        bf.deck.Slide("a", name="2nd slide")


def test_a_slide_cant_hold_a_slide_or_a_page() -> None:
    with pytest.raises(bf.BriefingError, match="can't hold another Slide"):
        bf.deck.Slide(bf.deck.Slide("a"))
    with pytest.raises(bf.BriefingError, match="can't hold a Page"):
        bf.deck.Slide(bf.Page("a", title="P"))


def test_a_deck_needs_slides() -> None:
    with pytest.raises(bf.BriefingError, match="has no slides"):
        bf.deck.Deck()


def test_a_deck_holds_only_slides_and_says_how_to_wrap_a_block() -> None:
    with pytest.raises(bf.BriefingError, match=r"slide 2 is a Text\. Wrap it: bf\.deck\.Slide"):
        bf.deck.Deck(bf.deck.Slide(title="One"), t.cast(t.Any, bf.Text("loose")))


def test_a_deck_footer_must_be_text() -> None:
    with pytest.raises(bf.BriefingError, match="Deck 'footer' must be text"):
        bf.deck.Deck(bf.deck.Slide(title="One"), footer=t.cast(t.Any, 1))


def test_a_slide_in_a_report_says_where_it_belongs() -> None:
    with pytest.raises(bf.BriefingError, match="goes in a bf.deck.Deck"):
        bf.stringify(bf.Briefing(bf.Group(bf.deck.Slide("a"))))


def test_a_deck_passed_where_a_report_goes_says_how_to_save_it() -> None:
    deck = bf.deck.Deck(bf.deck.Slide(title="One"))
    with pytest.raises(bf.BriefingError, match=r"save it with bf\.deck\.save"):
        bf.stringify(t.cast(t.Any, deck))
