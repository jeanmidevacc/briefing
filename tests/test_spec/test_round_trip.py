"""Python and JSON write the same report: every scenario survives ``from_spec(*to_spec(r))`` (#31).

By reference, the report comes back byte for byte. Inline, too, except that Plotly and
Altair may order the keys of a chart's JSON differently once it is read back: those
reports must match once the golden mask has replaced the charts (the inline encoder has
already checked that each chart reads back equal, as data).
"""
from __future__ import annotations

import json

import pytest

import briefing as bf
from tests.golden import NOW, mask
from tests.scenarios import ESCAPE_SCENARIOS, REPORT_NAME, SCENARIOS, Frames


def _render(report: bf.Briefing) -> str:
    return bf.stringify(report, name=REPORT_NAME, now=NOW)


@pytest.mark.parametrize("scenario", list(SCENARIOS))
def test_every_scenario_round_trips_by_reference(scenario: str, frames: Frames) -> None:
    report = SCENARIOS[scenario](frames)
    spec, data = bf.to_spec(report)
    text = json.dumps(spec, allow_nan=False)  # plain JSON, nothing Python-only left in it
    assert _render(bf.from_spec(text, data)) == _render(report)


@pytest.mark.parametrize("scenario", list(SCENARIOS))
def test_every_scenario_round_trips_inline(scenario: str, frames: Frames) -> None:
    report = SCENARIOS[scenario](frames)
    spec, data = bf.to_spec(report, inline=True)
    text = json.dumps(spec, allow_nan=False)
    again, original = _render(bf.from_spec(text, data)), _render(report)
    if again != original:
        assert '"plotly"' in text or '"vega-lite"' in text, "only a chart's key order may differ"
        assert mask(again) == mask(original)


@pytest.mark.parametrize("scenario", list(ESCAPE_SCENARIOS))
def test_user_text_round_trips(scenario: str) -> None:
    report, name = ESCAPE_SCENARIOS[scenario]()
    spec, data = bf.to_spec(report, inline=True)
    assert bf.stringify(bf.from_spec(json.dumps(spec), data), name=name, now=NOW) == bf.stringify(
        report, name=name, now=NOW
    )


@pytest.mark.parametrize("scenario", list(SCENARIOS))
def test_validate_finds_no_error_in_any_scenario(scenario: str, frames: Frames) -> None:
    report = SCENARIOS[scenario](frames)
    errors = [d for d in bf.validate(report) if d.severity == "error"]
    assert errors == []
