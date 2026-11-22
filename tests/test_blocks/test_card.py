"""Card: a framed box with a title around stacked blocks, that may lead to a link (#27)."""
from __future__ import annotations

import typing as t

import pytest

import briefing as bf
from tests.contract import PAYLOAD
from tests.html_helpers import attr, classes, find_one, parse


def _card(card: bf.Card) -> t.Any:
    return find_one(parse(bf.stringify(bf.Briefing(card))), ".bf-card")


def test_every_part() -> None:
    card = _card(bf.Card("Pizza and snacks", bf.BigNumber("Searches", 14), title="Food **and** delivery",
                         icon="🍕", tags=["Pizza", bf.Chip("Uber Eats", color="up")]))
    assert find_one(card, ".bf-card__icon").get_text() == "🍕" and attr(find_one(card, ".bf-card__icon"),
                                                                        "aria-hidden") == "true"
    assert find_one(card, ".bf-card__title strong").get_text() == "and"
    body = find_one(card, ".bf-card__body")
    assert [classes(b)[1] for b in body.find_all(recursive=False)] == ["bf-text", "bf-bignumber"]
    assert [c.get_text() for c in card.select(".bf-card__tags .bf-chip")] == ["Pizza", "Uber Eats"]
    assert "bf-card--link" not in classes(card) and card.select("a") == []


def test_a_link_makes_the_title_the_link() -> None:
    card = _card(bf.Card("Body", title="Food **and** delivery", link="detail/food"))
    link = find_one(card, ".bf-card__title a.bf-card__link")
    assert attr(link, "href") == "#detail/food" and link.get_text() == "Food and delivery"
    assert "bf-card--link" in classes(card)
    assert attr(find_one(_card(bf.Card(title="T", link="#summary")), "a"), "href") == "#summary"


def test_text_is_escaped() -> None:
    card = _card(bf.Card(title=PAYLOAD, icon="<b>", tags=[PAYLOAD]))
    assert find_one(card, ".bf-card__title").get_text() == PAYLOAD
    assert find_one(card, ".bf-card__icon").get_text() == "<b>"


def test_only_what_is_given_is_drawn() -> None:
    card = _card(bf.Card("Just a body"))
    assert card.select(".bf-card__head") == [] and card.select(".bf-card__tags") == []
    titled = _card(bf.Card(title="Only a title"))
    assert titled.select(".bf-card__body") == []


@pytest.mark.parametrize(("args", "kwargs", "match"), [
    ((), {}, "give it a title, tags or blocks"),
    (("x",), {"link": "food"}, "a link needs a title"),
    (("x",), {"title": "T", "link": "a/b/c"}, "link is a block or heading link"),
    (("x",), {"title": "T", "link": "https://example.org"}, "link is a block or heading link"),
    (("x",), {"title": "T", "link": "9lives"}, "link is a block or heading link"),
    (("x",), {"icon": "a long label"}, "icon is a short mark"),
    (("x",), {"title": 3}, "title is text"),
    (("x",), {"tags": "Pizza"}, "tags is a list"),
])
def test_bad_options(args: tuple[t.Any, ...], kwargs: dict[str, t.Any], match: str) -> None:
    with pytest.raises(bf.BriefingError, match=match):
        bf.Card(*args, **kwargs)


def test_the_json_form() -> None:
    report = bf.Briefing(bf.Group(
        bf.Card("Body", title="Food", icon="🍕", tags=["Pizza", bf.Chip("Uber", color="up")], link="food"),
        bf.Card(bf.BigNumber("N", 1), title="Other"), min_width="16rem"))
    spec, data = bf.to_spec(report)
    card = spec["blocks"][0]["blocks"][0]
    assert card["type"] == "Card" and card["tags"] == ["Pizza", {"text": "Uber", "color": "up"}]
    assert bf.stringify(bf.from_spec(spec, data)) == bf.stringify(report)
