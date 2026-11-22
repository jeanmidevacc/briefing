"""bf.Legend (#177): one legend for the blocks that share a Scale."""
from __future__ import annotations

import typing as t

import pandas as pd
import pytest

import briefing as bf
from tests.contract import PAYLOAD
from tests.html_helpers import attr, find_one, parse

SCALE = bf.Scale(["#1b2c80", "#f5479a", "#ffc46b"], domain=(0, 100))


def _days() -> pd.DataFrame:
    return pd.DataFrame({"d": pd.date_range("2026-06-01", periods=10), "v": range(10)})


def test_a_legend_shows_the_scale_no_data_and_events() -> None:
    events = pd.DataFrame({"start": ["2026-06-05"], "end": ["2026-06-07"], "label": ["Trailer"],
                           "color": ["#a3e635"]})
    legend = find_one(parse(bf.stringify(bf.Briefing(bf.Legend(SCALE, title="Interest, **0 to 100**",
                                                                 events=events)))), ".bf-legend")
    assert find_one(legend, ".bf-legend__title strong").get_text() == "0 to 100"
    assert attr(find_one(legend, ".bf-cal__ramp"), "style").startswith("background:linear-gradient(to right, #1b2c80")
    text = find_one(legend, ".bf-cal__legend").get_text(" ")
    assert text.split()[:2] == ["0", "100"] and "no data" in text and "Trailer (2026-06-05 to 2026-06-07)" in text
    assert attr(find_one(legend, ".bf-cal__swatch--event-span"), "style") == "--bf-event: #a3e635"


def test_blocks_can_hide_their_own_legend() -> None:
    page = bf.Briefing(bf.Legend(SCALE),
                       bf.lab.CalendarHeatmap(_days(), date="d", value="v", colors=SCALE, legend=False),
                       bf.lab.TimeHeatmap(_days(), date="d", rows="weekday", columns="month", value="v",
                                          colors=SCALE, legend=False))
    assert len(parse(bf.stringify(page)).select(".bf-cal__legend")) == 1
    shown = bf.stringify(bf.Briefing(bf.lab.CalendarHeatmap(_days(), date="d", value="v", colors=SCALE)))
    assert len(parse(shown).select(".bf-cal__legend")) == 1


@pytest.mark.parametrize(("args", "kwargs", "match"), [
    ((bf.Scale(["#000", "#fff"]),), {}, "needs a domain"),
    ((["#000", "#fff"],), {}, "scale is a bf.Scale"),
    ((SCALE,), {"title": 3}, "title is text"),
    ((SCALE,), {"events": pd.DataFrame({"when": ["2026-01-01"]})}, "'start' column"),
])
def test_bad_legends(args: tuple[t.Any, ...], kwargs: dict[str, t.Any], match: str) -> None:
    with pytest.raises(bf.BriefingError, match=match):
        bf.Legend(*args, **kwargs)


def test_legend_flag_is_a_bool() -> None:
    with pytest.raises(bf.BriefingError, match="legend is True or False"):
        bf.lab.CalendarHeatmap(_days(), date="d", legend="no")  # type: ignore[arg-type]


def test_the_title_is_escaped() -> None:
    legend = find_one(parse(bf.stringify(bf.Briefing(bf.Legend(SCALE, title=PAYLOAD)))), ".bf-legend__title")
    assert legend.get_text() == PAYLOAD and legend.find("img") is None


def test_the_json_form() -> None:
    report = bf.Briefing(bf.Legend(SCALE, title="T", events=["2026-06-05"]),
                         bf.lab.CalendarHeatmap(_days(), date="d", value="v", colors=SCALE, legend=False))
    spec, data = bf.to_spec(report)
    assert spec["blocks"][0]["type"] == "Legend" and spec["blocks"][1]["legend"] is False
    assert bf.stringify(bf.from_spec(spec, data)) == bf.stringify(report)
