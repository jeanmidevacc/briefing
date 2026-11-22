"""Check one option's JSON against its schema, and say in words what it should be (#31).

Only the part of JSON Schema that :mod:`briefing.spec._model` writes is understood:
``type``, ``enum``, ``const``, ``anyOf``, ``oneOf``, ``$ref``, ``items``, ``prefixItems``,
``minItems``, ``maxItems``, ``minLength``, ``pattern``, ``properties``, ``required`` and
``additionalProperties``. A whole number must be a JSON integer (``2``, not ``2.0``),
as the block constructors want.
"""
from __future__ import annotations

import functools
import json
import re
import typing as t

from briefing.spec._model import build_schema

_TYPES: dict[str, t.Callable[[object], bool]] = {
    "string": lambda v: isinstance(v, str),
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "number": lambda v: isinstance(v, int | float) and not isinstance(v, bool),
    "boolean": lambda v: isinstance(v, bool),
    "null": lambda v: v is None,
    "array": lambda v: isinstance(v, list),
    "object": lambda v: isinstance(v, dict),
}

_WORDS = {
    "string": "text",
    "integer": "a whole number",
    "number": "a number",
    "boolean": "true or false",
    "null": "null",
    "array": "a list",
    "object": "an object",
}

_DEF_WORDS = {
    "table": 'a table {"columns": [...], "rows": [[...]]}',
    "figure": 'a chart {"plotly": {...}} or {"vega-lite": {...}}',
    "image": "an image file path or a data: URI",
    "file": "a file path or a data: URI",
    "tab_style": 'a tab style {"layout": "stretch", "sticky": true, ...}',
    "ref": '{"ref": "<name>"}',
    "name": "a name (a letter, then letters, digits, _ or -)",
    "block": "a block",
}


@functools.cache
def _defs() -> dict[str, t.Any]:
    defs: dict[str, t.Any] = build_schema()["$defs"]
    return defs


def _target(schema: dict[str, t.Any]) -> str:
    return str(schema["$ref"]).rsplit("/", 1)[-1]


def refs_in(schema: dict[str, t.Any]) -> set[str]:
    """The ``$defs`` an option's schema accepts directly (``{"table", "ref"}``…)."""
    options = schema.get("anyOf", [schema])
    return {_target(s) for s in options if "$ref" in s}


def check(value: object, schema: dict[str, t.Any]) -> bool:
    """Whether *value* is what *schema* describes."""
    if "$ref" in schema:
        return check(value, _defs()[_target(schema)])
    if "anyOf" in schema and not any(check(value, s) for s in schema["anyOf"]):
        return False
    if "oneOf" in schema and sum(check(value, s) for s in schema["oneOf"]) != 1:
        return False
    if "const" in schema and not (value == schema["const"] and type(value) is type(schema["const"])):
        return False
    if "enum" in schema and not (isinstance(value, str) and value in schema["enum"]):
        return False
    if "type" in schema:
        kinds = schema["type"] if isinstance(schema["type"], list) else [schema["type"]]
        if not any(_TYPES[k](value) for k in kinds):
            return False
    if isinstance(value, str) and not _check_string(value, schema):
        return False
    if isinstance(value, list) and not _check_array(value, schema):
        return False
    return not isinstance(value, dict) or _check_object(value, schema)


def _check_string(value: str, schema: dict[str, t.Any]) -> bool:
    if len(value) < schema.get("minLength", 0):
        return False
    return "pattern" not in schema or re.search(schema["pattern"], value) is not None


def _check_array(value: list[t.Any], schema: dict[str, t.Any]) -> bool:
    if not schema.get("minItems", 0) <= len(value) <= schema.get("maxItems", len(value)):
        return False
    prefix = schema.get("prefixItems", [])
    if not all(check(v, s) for v, s in zip(value, prefix, strict=False)):
        return False
    return "items" not in schema or all(check(v, schema["items"]) for v in value[len(prefix):])


def _check_object(value: dict[str, t.Any], schema: dict[str, t.Any]) -> bool:
    if any(key not in value for key in schema.get("required", [])):
        return False
    properties = schema.get("properties", {})
    others = schema.get("additionalProperties", True)
    if others is False and any(key not in properties for key in value):
        return False
    if isinstance(others, dict) and not all(check(v, others) for key, v in value.items() if key not in properties):
        return False
    return all(check(value[key], s) for key, s in properties.items() if key in value)


def describe(schema: dict[str, t.Any]) -> str:
    """What *schema* accepts, in words: ``"a whole number"``, ``'one of "tabs", "dropdown"'``…"""
    if "$ref" in schema:
        target = _target(schema)
        return _DEF_WORDS.get(target, f"a {target} block")
    if "anyOf" in schema:
        words = [describe(s) for s in schema["anyOf"] if not ("$ref" in s and _target(s) == "ref")]
        return " or ".join(dict.fromkeys(words))
    if "enum" in schema:
        return "one of " + ", ".join(json.dumps(v) for v in schema["enum"])
    if "const" in schema:
        return json.dumps(schema["const"])
    kinds = schema.get("type", [])
    kinds = kinds if isinstance(kinds, list) else [kinds]
    if kinds == ["array"] and "prefixItems" in schema:
        return f"a list of {len(schema['prefixItems'])} {_plural(describe(schema['prefixItems'][0]))}"
    if kinds == ["array"] and "items" in schema:
        return f"a list of {_plural(describe(schema['items']))}"
    if kinds == ["object"] and isinstance(schema.get("additionalProperties"), dict):
        return f'an object {{"<column>": {describe(schema["additionalProperties"])}}}'
    return " or ".join(_WORDS[k] for k in kinds) or "a value"


def _plural(words: str) -> str:
    if words.startswith("one of "):
        return "values from " + words.removeprefix("one of ")
    for single, many in (("a whole number", "whole numbers"), ("a number", "numbers"), ("text", "texts")):
        words = words.replace(single, many)
    return words


def show(value: object) -> str:
    """*value* as short JSON, for a message."""
    try:
        text = json.dumps(value, ensure_ascii=False, default=lambda v: f"<{type(v).__name__}>")
    except (TypeError, ValueError):
        text = repr(value)
    return text if len(text) <= 60 else text[:57] + "..."
