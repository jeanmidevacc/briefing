"""Chips, BigNumber(accent=) and the theme's up/down colours (#27)."""
from __future__ import annotations

import typing as t

import pytest

import briefing as bf
from tests.contract import PAYLOAD
from tests.html_helpers import attr, classes, find_one, parse


def _chips(block: bf.Chips) -> list[t.Any]:
    return list(parse(bf.stringify(bf.Briefing(block))).select("ul.bf-chips > li.bf-chip"))


def test_items_are_text_chips_or_dicts() -> None:
    chips = _chips(bf.Chips(["Pizza", bf.Chip("Steam +41%", tooltip="Usual 31", color="up"),
                             {"text": "Netflix -12%", "color": "down"}]))
    assert [c.get_text() for c in chips] == ["Pizza", "Steam +41%", "Netflix -12%"]
    assert classes(chips[0]) == ["bf-chip"] and chips[0].get("style") is None
    assert attr(chips[1], "title") == "Usual 31" and attr(chips[1], "style") == "--bf-chip: var(--bf-up)"
    assert attr(chips[2], "style") == "--bf-chip: var(--bf-down)" and "bf-chip--color" in classes(chips[2])


@pytest.mark.parametrize(("color", "css"), [("accent", "var(--bf-accent)"), ("#2dd4bf", "#2dd4bf"),
                                            ("teal", "teal"), ("rgb(1, 2, 3)", "rgb(1, 2, 3)")])
def test_colours_are_theme_tokens_or_css_colours(color: str, css: str) -> None:
    (chip,) = _chips(bf.Chips([bf.Chip("x", color=color)]))
    assert attr(chip, "style") == f"--bf-chip: {css}"


def test_text_and_tooltips_are_escaped() -> None:
    (chip,) = _chips(bf.Chips([bf.Chip(PAYLOAD, tooltip=PAYLOAD)]))
    assert chip.get_text() == PAYLOAD and attr(chip, "title") == PAYLOAD and chip.find(True) is None


@pytest.mark.parametrize(("items", "match"), [
    ("Pizza", "items is a list"),
    ([], "at least one pill"),
    ([3], "an item is text, a bf.Chip"),
    ([""], "text is a short line"),
    ([{"text": "x", "colour": "up"}], "Chip has no field 'colour'"),
])
def test_bad_items(items: t.Any, match: str) -> None:
    with pytest.raises(bf.BriefingError, match=match):
        bf.Chips(items)


@pytest.mark.parametrize("color", ["red; } body { display: none", "url(x)", "var(--x)", "#12", 3])
def test_unsafe_or_unknown_colours_are_errors(color: object) -> None:
    with pytest.raises(bf.BriefingError, match="'up', 'down', 'accent' or a CSS colour"):
        bf.Chip("x", color=color)  # type: ignore[arg-type]
    with pytest.raises(bf.BriefingError, match="accent is 'up'"):
        bf.BigNumber("x", 1, accent=color)  # type: ignore[arg-type]


def test_the_json_form() -> None:
    report = bf.Briefing(bf.Chips(["Pizza", bf.Chip("Steam", tooltip="t", color="up")]))
    spec, data = bf.to_spec(report)
    assert spec["blocks"][0]["items"] == ["Pizza", {"text": "Steam", "tooltip": "t", "color": "up"}]
    assert bf.stringify(bf.from_spec(spec, data)) == bf.stringify(report)
    (error,) = bf.validate({"briefing": 1, "blocks": [{"type": "Chips", "items": [{"txt": "x"}]}]})
    assert error.code == "wrong-type"


def test_a_bignumber_accent() -> None:
    card = find_one(parse(bf.stringify(bf.Briefing(bf.BigNumber("Up", 14, accent="up")))), ".bf-bignumber")
    assert "bf-bignumber--accent" in classes(card) and attr(card, "style") == "--bf-number-accent: var(--bf-up)"
    plain = find_one(parse(bf.stringify(bf.Briefing(bf.BigNumber("Up", 14)))), ".bf-bignumber")
    assert plain.get("style") is None


def test_the_theme_sets_up_and_down() -> None:
    css = bf.Formatting(up_color="#e8692a", down_color="#5b7cfa").to_css_vars()
    assert "--bf-up:         #e8692a;" in css and "--bf-down:       #5b7cfa;" in css
    assert "--bf-up:         #16a34a;" in bf.Formatting().to_css_vars()
