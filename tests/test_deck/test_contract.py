"""Every scenario put on slides follows the HTML contract, as a report does (#197)."""
from __future__ import annotations

import pytest
from bs4 import BeautifulSoup

import briefing as bf
from tests.contract import MARKER, PAYLOAD, RULES, check_deterministic, check_user_text_escaped, parse_report
from tests.scenarios import ESCAPE_SCENARIOS, REPORT_NAME, SCENARIOS, Frames
from tests.test_deck.helpers import as_deck

_parsed: dict[str, BeautifulSoup] = {}


def _render(scenario: str, frames: Frames) -> BeautifulSoup:
    if scenario not in _parsed:
        _parsed[scenario] = parse_report(bf.deck.to_html(as_deck(SCENARIOS[scenario](frames)), name=REPORT_NAME))
    return _parsed[scenario]


@pytest.mark.filterwarnings("ignore")
@pytest.mark.parametrize("scenario", list(SCENARIOS))
@pytest.mark.parametrize("rule", list(RULES))
def test_every_scenario_on_slides_follows_the_rule(rule: str, scenario: str, frames: Frames) -> None:
    RULES[rule](_render(scenario, frames))


@pytest.mark.filterwarnings("ignore")
@pytest.mark.parametrize("scenario", list(SCENARIOS))
def test_every_scenario_on_slides_is_deterministic(scenario: str, frames: Frames) -> None:
    check_deterministic(lambda: bf.deck.to_html(as_deck(SCENARIOS[scenario](frames))))


@pytest.mark.parametrize("scenario", list(ESCAPE_SCENARIOS))
def test_user_text_on_slides_stays_escaped(scenario: str) -> None:
    report, name = ESCAPE_SCENARIOS[scenario]()
    soup = parse_report(bf.deck.to_html(as_deck(report), name=name))
    check_user_text_escaped(soup)
    assert MARKER in soup.get_text()


def test_a_slide_title_and_the_footer_stay_escaped() -> None:
    deck = bf.deck.Deck(bf.deck.Slide("a", title=PAYLOAD), footer=PAYLOAD)
    soup = parse_report(bf.deck.to_html(deck))
    check_user_text_escaped(soup)
    assert soup.get_text().count(MARKER) >= 2
