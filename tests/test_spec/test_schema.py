"""The JSON Schema of the format: built from the block classes, checked in, and true to ``to_spec`` (#31)."""
from __future__ import annotations

import json
from importlib.resources import files

import pytest

import briefing as bf
from briefing.spec.__main__ import schema_text
from briefing.spec._model import block_types
from tests.scenarios import HOUR_VIEW_WARNING, SCENARIOS, Frames
from tests.test_spec.test_from_spec import EXAMPLE

pytestmark = pytest.mark.filterwarnings(HOUR_VIEW_WARNING)

SCHEMA = files("briefing") / "schema" / "v1.json"


def test_the_checked_in_schema_matches_the_block_classes() -> None:
    assert SCHEMA.read_text(encoding="utf-8") == schema_text(), (
        "the block classes changed: run `python -m briefing.spec` and commit briefing/schema/v1.json"
    )


def test_schema_returns_the_shipped_file_as_a_fresh_dict() -> None:
    first = bf.schema()
    assert first == json.loads(SCHEMA.read_text(encoding="utf-8"))
    first["$defs"].clear()
    assert bf.schema()["$defs"]


def test_every_block_type_and_option_is_described() -> None:
    defs = bf.schema()["$defs"]
    for name in block_types():
        assert defs[name]["description"], name
        for option, prop in defs[name]["properties"].items():
            assert option in ("type", "blocks") or prop.get("description"), f"{name}.{option} has no description"


def test_the_schema_is_valid_json_schema() -> None:
    jsonschema = pytest.importorskip("jsonschema")
    jsonschema.Draft202012Validator.check_schema(bf.schema())


def test_the_issues_example_follows_the_schema() -> None:
    jsonschema = pytest.importorskip("jsonschema")
    jsonschema.Draft202012Validator(bf.schema()).validate(EXAMPLE)


@pytest.mark.parametrize("scenario", list(SCENARIOS))
def test_what_to_spec_writes_follows_the_schema(scenario: str, frames: Frames) -> None:
    jsonschema = pytest.importorskip("jsonschema")
    spec, _ = bf.to_spec(SCENARIOS[scenario](frames), inline=True)
    jsonschema.Draft202012Validator(bf.schema()).validate(json.loads(json.dumps(spec)))
