"""BigNumber: a computed change from prev_value, a format, and a sparkline (#35)."""
from __future__ import annotations

import typing as t

import pytest

import briefing as bf
from tests.html_helpers import attr, classes, find_one, parse


def _card(block: bf.BigNumber) -> t.Any:
    return find_one(parse(bf.stringify(bf.Briefing(block))), ".bf-bignumber")


def _change(block: bf.BigNumber) -> tuple[str, list[str], str | None]:
    change = find_one(_card(block), ".bf-bignumber__change")
    title = change.get("title")
    return change.get_text(), [c.split("--")[1] for c in classes(change) if "--" in c], str(title) if title else None


@pytest.mark.parametrize(("kwargs", "text", "marks"), [
    ({"value": 4_210_000, "prev_value": 3_810_000}, "▲ +10.5%", ["up", "good"]),
    ({"value": 90, "prev_value": 100}, "▼ -10.0%", ["down", "bad"]),
    ({"value": 90, "prev_value": 100, "higher_is_better": False}, "▼ -10.0%", ["down", "good"]),
    ({"value": 120, "prev_value": 100, "change_as": "absolute", "format": "{:,.0f} €"}, "▲ +20 €", ["up", "good"]),
    ({"value": 0.031, "prev_value": 0.034, "change_as": "points", "format": "{:.1%}"}, "▼ -0.3 pt", ["down", "bad"]),
    ({"value": 41.5, "prev_value": 40.0, "change_as": "points"}, "▲ +1.5 pt", ["up", "good"]),
    ({"value": 5, "prev_value": 0}, "▲ +5", ["up", "good"]),  # a percent change from zero: the difference
    ({"value": 5, "prev_value": 5}, "0.0%", ["neutral"]),
])
def test_the_change_is_computed(kwargs: dict[str, t.Any], text: str, marks: list[str]) -> None:
    shown, found, _ = _change(bf.BigNumber("Metric", **kwargs))
    assert shown == text and found == marks


def test_the_previous_value_is_in_the_tooltip_and_the_value_is_formatted() -> None:
    block = bf.BigNumber("Revenue", 4_210_000, prev_value=3_810_000, format="${:,.0f}")
    assert find_one(_card(block), ".bf-bignumber__value").get_text() == "$4,210,000"
    assert _change(block)[2] == "Previous: $3,810,000"


def test_a_format_function() -> None:
    block = bf.BigNumber("Users", 142_000, format=lambda v: f"{v / 1000:.0f}K")
    assert find_one(_card(block), ".bf-bignumber__value").get_text() == "142K"


def test_a_change_typed_by_hand_is_unchanged() -> None:
    assert _change(bf.BigNumber("Revenue", "$4.2M", change="+3%", is_upward_change=True))[:2] == (
        "▲ +3%", ["up"])


@pytest.mark.parametrize(("kwargs", "match"), [
    ({"value": 4, "prev_value": 3, "change": "+1"}, "its arrow and its colour are computed"),
    ({"value": 4, "prev_value": 3, "is_upward_change": True}, "drop change, is_upward_change"),
    ({"value": "$4M", "prev_value": 3}, "prev_value needs numbers; value is '\\$4M'"),
    ({"value": 4, "prev_value": "3"}, "prev_value needs numbers; prev_value is '3'"),
    ({"value": 4, "prev_value": 3, "change_as": "ratio"}, "change_as must be one of 'percent', 'absolute', 'points'"),
    ({"value": 4, "change_as": "points"}, "pass prev_value"),
    ({"value": 4, "higher_is_better": False}, "pass prev_value"),
    ({"value": "n/a", "format": "{:.1f}"}, "format '\\{:.1f\\}' can't show the value 'n/a'"),
    ({"value": 4, "format": ".1f"}, "format is a format string"),
    ({"value": 4, "sparkline": [1]}, "at least two numbers"),
    ({"value": 4, "sparkline": [1, None, float("nan")]}, "at least two numbers"),
    ({"value": 4, "sparkline": "123"}, "sparkline is a sequence of numbers"),
    ({"value": 4, "sparkline": [1, "2"]}, "holds numbers"),
])
def test_options_that_dont_fit_say_what_to_pass(kwargs: dict[str, t.Any], match: str) -> None:
    with pytest.raises(bf.BriefingError, match=match):
        bf.BigNumber("Metric", **kwargs)


def test_a_sparkline_from_a_list_series_or_array_with_gaps() -> None:
    np = pytest.importorskip("numpy")
    pd = pytest.importorskip("pandas")
    for series in ([3.1, 3.4, None, 3.9, 4.2], pd.Series([3.1, 3.4, None, 3.9, 4.2]),
                   np.array([3.1, 3.4, np.nan, 3.9, 4.2])):
        block = bf.BigNumber("Revenue", 4.2, sparkline=series)
        assert block.sparkline == [3.1, 3.4, None, 3.9, 4.2]
        svg = find_one(_card(block), "svg.bf-bignumber__spark")
        assert attr(svg, "role") == "img" and attr(svg, "aria-label") == "Trend of 5 values, from 3.1 to 4.2"
        line = attr(svg.find_all("path")[0], "d")
        assert line.count("M") == 2 and line.startswith("M0.00 22.00")  # the gap starts a new stroke
        assert attr(svg.find_all("path")[1], "d") == "M100.00 2.00h0"  # the last point, at the top


def test_a_flat_sparkline_is_drawn_mid_height() -> None:
    svg = find_one(_card(bf.BigNumber("Flat", 1, sparkline=[2, 2, 2])), "svg.bf-bignumber__spark")
    assert attr(find_one(svg, "path"), "d") == "M0.00 12.00L50.00 12.00L100.00 12.00"


def test_the_json_form_round_trips() -> None:
    report = bf.Briefing(bf.BigNumber("Churn", 0.031, prev_value=0.034, format="{:.1%}", change_as="points",
                                      higher_is_better=False, sparkline=[0.04, None, 0.031]))
    spec, data = bf.to_spec(report)
    block = spec["blocks"][0]
    assert block["sparkline"] == [0.04, None, 0.031] and block["change_as"] == "points"
    assert bf.stringify(bf.from_spec(spec, data)) == bf.stringify(report)
