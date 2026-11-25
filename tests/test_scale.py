"""bf.Scale and bf.color (#175): colours with a fixed meaning, mixed in OKLab."""
from __future__ import annotations

import typing as t

import pandas as pd
import pytest

import briefing as bf
from briefing.lab._render_calendar import render_calendar
from tests.html_helpers import attr, find_one, parse

INTEREST = ["#1b2c80", "#1f40be", "#9a3fc4", "#f5479a", "#f47b31", "#ffc46b"]


# ── bf.color ──────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(("hex_", "lab"), [
    ("#ffffff", (1.0, 0.0, 0.0)),
    ("#000000", (0.0, 0.0, 0.0)),
    ("#ff0000", (0.627955, 0.224863, 0.125846)),  # Ottosson's reference values
    ("#00ff00", (0.866440, -0.233888, 0.179498)),
    ("#0000ff", (0.452014, -0.032457, -0.311528)),
])
def test_oklab_matches_the_reference(hex_: str, lab: tuple[float, float, float]) -> None:
    assert bf.color.to_oklab(hex_) == pytest.approx(lab, abs=1e-4)
    assert bf.color.from_oklab(bf.color.to_oklab(hex_)) == hex_


def test_a_ramp_ends_on_its_anchors_and_keeps_rising_lightness() -> None:
    colors = bf.color.ramp(INTEREST, 101)
    assert colors[0] == INTEREST[0] and colors[-1] == INTEREST[-1] and len(colors) == 101
    lightness = [bf.color.lightness(c) for c in colors]
    assert all(b >= a - 1e-3 for a, b in zip(lightness, lightness[1:], strict=False))


def test_mixing_in_oklab_has_no_muddy_middle() -> None:
    mid = bf.color.mix("#0000ff", "#ffff00", 0.5)
    assert 0.6 < bf.color.lightness(mid) < 0.75  # an sRGB average (#808080) is far darker, L 0.6
    assert bf.color.mix("#123456", "#abcdef", 0) == "#123456" and bf.color.mix("#123456", "#abcdef", 2) == "#abcdef"


@pytest.mark.parametrize(("args", "match"), [((["#000"], 3), "at least two anchors"), ((["#000", "red"], 3),
                                             "hex colour"), ((["#000", "#fff"], 1), "n is a whole number")])
def test_bad_ramps(args: tuple[t.Any, ...], match: str) -> None:
    with pytest.raises(bf.BriefingError, match=match):
        bf.color.ramp(*args)


# ── bf.Scale ──────────────────────────────────────────────────────────────────


def test_a_scale_with_a_domain_gives_each_value_one_colour() -> None:
    scale = bf.Scale(INTEREST, domain=(0, 100))
    assert scale(0) == INTEREST[0] and scale(100) == INTEREST[-1] and scale(20) == INTEREST[1]
    assert scale(-5) == INTEREST[0] and scale(500) == INTEREST[-1]  # clamped


def test_a_diverging_scale_puts_its_middle_colour_at_the_centre() -> None:
    scale = bf.Scale(["#d73027", "#f7f7f7", "#1a9850"], domain=(-10, 30), center=0)
    assert scale(0) == "#f7f7f7" and scale(-10) == "#d73027" and scale(30) == "#1a9850"
    assert scale.position(-5, -10, 30) == 0.25 and scale.position(15, -10, 30) == 0.75


def test_steps_make_flat_classes() -> None:
    scale = bf.Scale(["#000000", "#ffffff"], domain=(0, 100), steps=3)
    assert [scale(v) for v in (0, 30, 34, 60, 67, 100)] == [
        "#000000", "#000000", "#636363", "#636363", "#ffffff", "#ffffff"]


@pytest.mark.parametrize(("kwargs", "match"), [
    ({"colors": "#000"}, "two or more hex colours"),
    ({"colors": ["#000"]}, "two or more hex colours"),
    ({"colors": ["#000", "teal"]}, "each colour must be a hex colour"),
    ({"colors": ["#000", "#fff"], "domain": (5, 5)}, "low below high"),
    ({"colors": ["#000", "#fff"], "domain": (0,)}, "domain is"),
    ({"colors": ["#000", "#fff"], "center": 0}, "odd number of colours"),
    ({"colors": ["#000", "#888", "#fff"], "domain": (0, 10), "center": 20}, "inside the domain"),
    ({"colors": ["#000", "#fff"], "steps": 1}, "steps is a whole number"),
])
def test_bad_scales(kwargs: dict[str, t.Any], match: str) -> None:
    with pytest.raises(bf.BriefingError, match=match):
        bf.Scale(**kwargs)


def test_calling_a_scale_without_a_domain_says_what_to_pass() -> None:
    with pytest.raises(bf.BriefingError, match="pass domain="):
        bf.Scale(["#000", "#fff"])(3)


# ── in the heatmaps ───────────────────────────────────────────────────────────


def _fills(block: bf.lab.CalendarHeatmap) -> dict[str, str]:
    soup = parse(render_calendar(block))
    return {attr(c, "data-date"): str(c.get("fill") or "") for c in soup.select("rect.bf-cal__day")}


def test_two_calendars_with_one_scale_agree_on_every_value() -> None:
    scale = bf.Scale(INTEREST, domain=(0, 100))
    low = pd.DataFrame({"d": pd.date_range("2026-01-01", periods=4), "v": [0, 10, 20, 30]})
    high = pd.DataFrame({"d": pd.date_range("2026-01-01", periods=4), "v": [20, 50, 80, 100]})
    a = _fills(bf.lab.CalendarHeatmap(low, date="d", value="v", colors=scale))
    b = _fills(bf.lab.CalendarHeatmap(high, date="d", value="v", colors=scale))
    assert a["2026-01-03"] == b["2026-01-01"] == scale(20)  # 20 is one colour in both
    assert a["2026-01-01"] == scale(0)  # zero is a value: no grey zero class


def test_without_a_domain_a_scale_spreads_over_the_data() -> None:
    df = pd.DataFrame({"d": pd.date_range("2026-01-01", periods=3), "v": [10, 15, 20]})
    fills = _fills(bf.lab.CalendarHeatmap(df, date="d", value="v", colors=bf.Scale(["#000000", "#ffffff"])))
    assert (fills["2026-01-01"], fills["2026-01-03"]) == ("#000000", "#ffffff")


def test_the_legend_shows_the_scale_between_its_ends() -> None:
    df = pd.DataFrame({"d": pd.date_range("2026-01-01", periods=3), "v": [10, 15, 20]})
    soup = parse(render_calendar(bf.lab.CalendarHeatmap(df, date="d", value="v",
                                                        colors=bf.Scale(INTEREST, domain=(0, 100)))))
    ramp = find_one(soup, ".bf-cal__legend .bf-cal__ramp")
    assert attr(ramp, "style").startswith(f"background:linear-gradient(to right, {INTEREST[0]}")
    assert find_one(soup, ".bf-cal__legend").get_text(" ").split()[:2] == ["0", "100"]


def test_a_time_heatmap_takes_a_scale() -> None:
    df = pd.DataFrame({"d": pd.date_range("2026-01-01", periods=60), "v": range(60)})
    html = bf.stringify(bf.Briefing(bf.lab.TimeHeatmap(df, date="d", rows="weekday", columns="month", value="v",
                                                       colors=bf.Scale(["#000000", "#ffffff"], steps=4))))
    fills = {attr(c, "fill") for c in parse(html).select("rect.bf-cal__cell[fill]")}
    assert fills <= set(bf.color.ramp(["#000000", "#ffffff"], 4)) and len(fills) > 1


def test_the_centre_goes_in_the_scale() -> None:
    with pytest.raises(bf.BriefingError, match=r"center= was removed .* Pass colors=bf\.Scale"):
        bf.lab.CalendarHeatmap(pd.DataFrame({"d": ["2026-01-01"]}), date="d", center=0,  # type: ignore[call-arg]
                               colors=bf.Scale(["#000", "#888", "#fff"]))


def test_the_json_form() -> None:
    df = pd.DataFrame({"d": pd.date_range("2026-01-01", periods=5), "v": range(5)})
    report = bf.Briefing(bf.lab.CalendarHeatmap(df, date="d", value="v",
                                                colors=bf.Scale(INTEREST, domain=(0, 4), steps=3)))
    spec, data = bf.to_spec(report)
    assert spec["blocks"][0]["colors"] == {"colors": INTEREST, "domain": [0.0, 4.0], "steps": 3}
    assert bf.stringify(bf.from_spec(spec, data)) == bf.stringify(report)
    spec["blocks"][0]["colors"] = {"colors": INTEREST, "domian": [0, 1]}
    assert [d.code for d in bf.validate(spec, data)] == ["wrong-type"]
