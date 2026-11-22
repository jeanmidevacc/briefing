"""A deck as JSON (#197): ``{"briefing": 1, "slides": [...]}``, written, read back, validated."""
from __future__ import annotations

import json
import typing as t

import pandas as pd
import pytest

import briefing as bf
from tests.scenarios import SCENARIOS, Frames

DECK: dict[str, t.Any] = {
    "briefing": 1,
    "footer": "Sales analytics",
    "slides": [
        {"title": "Q3 review"},
        {"title": "Summary", "name": "summary", "blocks": [
            {"type": "Text", "text": "Revenue grew in **every** region."},
            {"type": "Group", "columns": 2, "blocks": [
                {"type": "BigNumber", "heading": "Revenue", "value": 4200000, "prev_value": 3900000},
                {"type": "BigNumber", "heading": "Margin", "value": 0.31, "format": "{:.0%}"},
            ]},
        ]},
        {"type": "Slide", "title": "Regions", "blocks": [{"type": "DataTable", "df": {"ref": "regions"}}]},
    ],
}


@pytest.fixture
def regions() -> pd.DataFrame:
    return pd.DataFrame({"region": ["North", "South"], "revenue": [412000, 287500]})


def test_from_spec_builds_the_deck(regions: pd.DataFrame) -> None:
    deck = bf.deck.from_spec(DECK, data={"regions": regions})
    assert deck.footer == "Sales analytics"
    assert [s.title for s in deck.slides] == ["Q3 review", "Summary", "Regions"]
    assert deck.slides[0].blocks == []
    assert deck.slides[1].name == "summary"
    assert [type(b).__name__ for b in deck.slides[1].blocks] == ["Text", "Group"]
    table = deck.slides[2].blocks[0]
    assert isinstance(table, bf.DataTable) and table.df.equals(regions)


def test_it_reads_json_text_too(regions: pd.DataFrame) -> None:
    assert len(bf.deck.from_spec(json.dumps(DECK), data={"regions": regions})) == 3


def test_to_spec_writes_a_deck_that_comes_back_the_same(regions: pd.DataFrame) -> None:
    deck = bf.deck.from_spec(DECK, data={"regions": regions})
    spec, data = bf.to_spec(deck)
    assert spec["briefing"] == 1 and spec["footer"] == "Sales analytics"
    assert spec["slides"][0] == {"title": "Q3 review"}
    assert spec["slides"][2]["blocks"][0]["df"] == {"ref": "datatable-1"}
    again = bf.deck.from_spec(spec, data)
    assert bf.to_spec(again) == (spec, data)


def test_to_spec_can_write_tables_inline(regions: pd.DataFrame) -> None:
    spec, data = bf.to_spec(bf.deck.from_spec(DECK, data={"regions": regions}), inline=True)
    assert data == {}
    assert spec["slides"][2]["blocks"][0]["df"]["rows"] == [["North", 412000], ["South", 287500]]


def test_what_to_spec_writes_follows_the_schema(regions: pd.DataFrame) -> None:
    jsonschema = pytest.importorskip("jsonschema")
    spec, _ = bf.to_spec(bf.deck.from_spec(DECK, data={"regions": regions}), inline=True)
    jsonschema.Draft202012Validator(bf.schema()).validate(json.loads(json.dumps(spec)))
    jsonschema.Draft202012Validator(bf.schema()).validate(DECK)


def test_the_schema_tells_a_deck_from_a_report() -> None:
    jsonschema = pytest.importorskip("jsonschema")
    validator = jsonschema.Draft202012Validator(bf.schema())
    assert not validator.is_valid({"briefing": 1, "slides": []})
    assert not validator.is_valid({"briefing": 1, "slides": [{}]})
    assert not validator.is_valid({"briefing": 1, "slides": [{"title": "a"}], "blocks": [{"type": "Text"}]})


@pytest.mark.parametrize("scenario", list(SCENARIOS))
def test_every_scenario_round_trips_on_a_slide(scenario: str, frames: Frames) -> None:
    report = SCENARIOS[scenario](frames)
    blocks = [b for page in report.blocks for b in (page.blocks if isinstance(page, bf.Page) else [page])]
    deck = bf.deck.Deck(bf.deck.Slide(*blocks, title=scenario))
    spec, data = bf.to_spec(deck)
    spec_again, data_again = bf.to_spec(bf.deck.from_spec(spec, data))
    assert spec_again == spec
    assert data_again.keys() == data.keys()


def test_validate_finds_nothing_wrong_in_a_good_deck(regions: pd.DataFrame) -> None:
    assert bf.validate(DECK, data={"regions": regions}) == []
    assert bf.validate(bf.deck.from_spec(DECK, data={"regions": regions})) == []


def _codes(spec: object, data: dict[str, t.Any] | None = None) -> list[tuple[str, str, str]]:
    return [(d.severity, d.code, d.path) for d in bf.validate(spec, data)]


@pytest.mark.parametrize(("spec", "expected"), [
    ({"briefing": 1, "slides": "x"}, ("error", "wrong-type", "/slides")),
    ({"briefing": 1, "slides": []}, ("error", "empty-container", "/slides")),
    ({"briefing": 1, "slides": [{}]}, ("error", "empty-container", "/slides/0")),
    ({"briefing": 1, "slides": ["x"]}, ("error", "not-a-block", "/slides/0")),
    ({"briefing": 1, "slides": [{"type": "Text", "text": "x"}]}, ("error", "unknown-type", "/slides/0/type")),
    ({"briefing": 1, "slides": [{"title": "a", "colour": "red"}]}, ("error", "unknown-option", "/slides/0/colour")),
    ({"briefing": 1, "slides": [{"title": 3}]}, ("error", "wrong-type", "/slides/0/title")),
    ({"briefing": 1, "slides": [{"title": "a", "blocks": {}}]}, ("error", "wrong-type", "/slides/0/blocks")),
    ({"briefing": 1, "slides": [{"title": "a"}], "theme": "dark"}, ("error", "unknown-option", "/theme")),
    ({"briefing": 1, "slides": [{"title": "a"}], "blocks": []}, ("error", "unknown-option", "/slides")),
    ({"briefing": 1, "slides": [{"blocks": [{"type": "Txt", "text": "a"}]}]},
     ("error", "unknown-type", "/slides/0/blocks/0/type")),
    ({"briefing": 1, "slides": [{"blocks": [{"type": "Page", "blocks": [{"type": "Text", "text": "a"}]}]}]},
     ("error", "misplaced-page", "/slides/0/blocks/0")),
    ({"slides": [{"title": "a"}]}, ("error", "missing-version", "")),
])
def test_validate_points_at_what_is_wrong(spec: dict[str, t.Any], expected: tuple[str, str, str]) -> None:
    assert expected in _codes(spec)


def test_names_are_unique_in_the_whole_deck() -> None:
    spec = {"briefing": 1, "slides": [
        {"title": "a", "name": "kpis"},
        {"blocks": [{"type": "Text", "text": "b", "name": "kpis"}]},
    ]}
    found = bf.validate(spec)
    assert [(d.code, d.path) for d in found] == [("duplicate-name", "/slides/1/blocks/0")]
    assert "unique in the deck" in (found[0].hint or "")


def test_a_heading_named_like_a_slide_is_a_clash_too() -> None:
    spec = {"briefing": 1, "slides": [
        {"title": "a", "name": "notes"},
        {"blocks": [{"type": "Text", "text": "## Notes {#notes}"}]},
    ]}
    assert ("error", "duplicate-name", "/slides/1/blocks/0") in _codes(spec)


def test_block_warnings_point_at_their_slide() -> None:
    spec = {"briefing": 1, "slides": [{"title": "a"}, {"blocks": [
        {"type": "Select", "blocks": [{"type": "Text", "text": "only", "label": "One"}]}]}]}
    assert ("warning", "too-few-panels", "/slides/1/blocks/0") in _codes(spec)


def test_a_missing_reference_is_reported_without_data_only_when_data_is_given() -> None:
    assert _codes(DECK) == []
    assert ("error", "unknown-ref", "/slides/2/blocks/0/df") in _codes(DECK, {})


def test_a_slide_in_a_reports_json_says_decks_have_slides() -> None:
    found = bf.validate({"briefing": 1, "blocks": [{"type": "Slide", "title": "a"}]})
    assert [(d.code, d.path) for d in found] == [("unknown-type", "/blocks/0/type")]
    assert '"slides" in place of "blocks"' in (found[0].hint or "")


def test_a_slide_in_a_python_report_is_reported_by_validate() -> None:
    found = bf.validate(bf.Briefing(bf.Group(bf.deck.Slide("a"))))
    assert [d.code for d in found] == ["unknown-type"]
    assert "goes in a bf.deck.Deck" in found[0].message


def test_from_spec_and_deck_from_spec_point_at_each_other(regions: pd.DataFrame) -> None:
    with pytest.raises(bf.BriefingError, match=r"is a deck .*bf\.deck\.from_spec"):
        bf.from_spec(DECK, data={"regions": regions})
    with pytest.raises(bf.BriefingError, match=r"is a report .*bf\.from_spec"):
        bf.deck.from_spec({"briefing": 1, "blocks": [{"type": "Text", "text": "a"}]})
    with pytest.raises(bf.BriefingError, match='an object with "slides"'):
        bf.deck.from_spec({"briefing": 1})
    with pytest.raises(bf.BriefingError, match="Can't read"):
        bf.deck.from_spec(t.cast(t.Any, [1, 2]))


def test_deck_from_spec_lists_every_problem() -> None:
    with pytest.raises(bf.BriefingError, match=r"isn't a deck briefing can build:\n- error empty-container"):
        bf.deck.from_spec({"briefing": 1, "slides": [{}]})
