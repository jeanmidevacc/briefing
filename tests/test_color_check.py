"""bf.color.check and Formatting.from_accent (#179)."""
from __future__ import annotations

import pytest

import briefing as bf


def _codes(findings: list[bf.color.Finding]) -> list[tuple[str, str]]:
    return [(f.level, f.code) for f in findings]


def test_contrast_matches_wcag() -> None:
    assert bf.color.contrast("#000000", "#ffffff") == pytest.approx(21.0)
    assert bf.color.contrast("#767676", "#ffffff") == pytest.approx(4.54, abs=0.01)
    assert bf.color.contrast("#abcdef", "#abcdef") == 1.0


def test_simulation_keeps_greys_and_merges_red_and_green() -> None:
    for condition in ("protanopia", "deuteranopia", "tritanopia"):
        assert bf.color.distance(bf.color.simulate("#808080", condition), "#808080") < 1
    red, green = "#d62728", "#2ca02c"
    assert bf.color.distance(bf.color.simulate(red, "deuteranopia"), bf.color.simulate(green, "deuteranopia")) < \
        bf.color.distance(red, green) / 2
    with pytest.raises(bf.BriefingError, match="condition is one of"):
        bf.color.simulate("#000", "achromatopsia")


def test_a_validated_palette_has_only_a_rare_condition_to_report() -> None:
    # Event colours a report checked with an outside validator (dark background, protan/deutan).
    findings = bf.color.check(["#2dd4bf", "#60a5fa", "#a3e635", "#ffffff"], background="#1a1a1a")
    assert _codes(findings) == [("info", "colour-blind")] and "tritanopia" in findings[0].message


def test_red_and_green_clash_for_colour_blind_readers() -> None:
    findings = bf.color.check(["#e41a1c", "#4daf4a"], background="#ffffff")
    assert ("warning", "colour-blind") in _codes(findings)


def test_low_contrast_and_too_close() -> None:
    findings = bf.color.check(["#fff8f8", "#1f77b4", "#2077b5"], background="#ffffff")
    assert _codes(findings) == [("warning", "low-contrast"), ("warning", "too-close")]
    assert findings[0].colors == ("#fff8f8", "#ffffff")


def test_sequential_and_diverging_lightness() -> None:
    assert bf.color.check(bf.color.ramp(["#3a5bd9", "#ffc46b"], 5), background="#000000", kind="sequential") == []
    bumpy = ["#1b2c80", "#ffc46b", "#9a3fc4"]
    assert _codes(bf.color.check(bumpy, background="#000000", kind="sequential"))[-1] == (
        "warning", "lightness-not-monotonic")
    good = bf.color.check(["#d73027", "#f7f7f7", "#1a9850"], background="#808080", kind="diverging")
    assert "lightness-not-monotonic" not in [f.code for f in good]  # (a light middle on grey: low contrast)
    assert ("warning", "lightness-not-monotonic") in _codes(
        bf.color.check(["#d73027", "#1a9850"], background="#808080", kind="diverging"))


def test_bad_arguments() -> None:
    with pytest.raises(bf.BriefingError, match="kind is"):
        bf.color.check(["#000", "#fff"], kind="qualitative")
    with pytest.raises(bf.BriefingError, match="background must be a hex colour"):
        bf.color.check(["#000", "#fff"], background="white")


@pytest.mark.parametrize("accent", ["#f5479a", "#ffeb3b", "#1b2c80", "#10b981", "#808080", "#000000", "#ffffff"])
@pytest.mark.parametrize("dark", [False, True])
def test_from_accent_reaches_its_contrast_levels(accent: str, dark: bool) -> None:
    theme = bf.Formatting.from_accent(accent, dark=dark)
    bg = theme.bg_color
    assert bf.color.contrast(theme.accent_color, bg) >= 4.5
    assert bf.color.contrast(theme.text_color, bg) >= 7.0
    assert bf.color.contrast(theme.muted_color, bg) >= 4.5
    assert (bf.color.lightness(bg) < 0.3) is dark


def test_from_accent_keeps_the_hue_and_takes_overrides() -> None:
    theme = bf.Formatting.from_accent("#1b2c80", radius="0.25rem")
    assert theme.accent_color == "#1b2c80" and theme.radius == "0.25rem"  # already dark enough on white
    with pytest.raises(bf.BriefingError, match="hex colour"):
        bf.Formatting.from_accent("pink")
