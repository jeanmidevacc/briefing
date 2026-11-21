"""What the JSON form of a report holds: each block type, its options, and their JSON Schema (#31).

Everything here is read from the block classes themselves: an option is a constructor
parameter, its JSON type comes from the type hint, its description from the class's
``Args:`` docstring, and whether it may be left out from its default. The few things
a hint can't say (which strings a choice accepts, that ``Plot.figure`` is a chart) are
in :data:`_CHOICES` and :data:`_OVERRIDES` below.

The schema built from this is checked in as ``briefing/schema/v1.json``;
``tests/test_spec/test_schema.py`` fails when the classes and the file drift apart.
"""
from __future__ import annotations

import collections.abc
import enum
import functools
import inspect
import re
import types
import typing as t
from dataclasses import dataclass
from pathlib import Path

from briefing.blocks.asset import DataTable, Plot, Table
from briefing.blocks.banner import Banner
from briefing.blocks.base import _NAME_RE, Block, ContainerBlock
from briefing.blocks.layout import Briefing, Group, Page, Select, Toggle
from briefing.blocks.text import HTML, Alert, BigNumber, Code, Formula, Text
from briefing.lab._blocks import CalendarHeatmap, DataDive, DataProfile

#: The format version this briefing reads and writes (``"briefing": 1``). It changes only
#: when JSON written for an older version would stop working.
FORMAT_VERSION = 1

#: Block types in the order the schema lists them; ``lab.`` blocks are named with their prefix.
_TYPES: tuple[tuple[str, type[Block]], ...] = (
    ("Text", Text),
    ("Group", Group),
    ("Select", Select),
    ("Toggle", Toggle),
    ("Page", Page),
    ("BigNumber", BigNumber),
    ("Alert", Alert),
    ("Banner", Banner),
    ("Plot", Plot),
    ("Table", Table),
    ("DataTable", DataTable),
    ("Code", Code),
    ("Formula", Formula),
    ("HTML", HTML),
    ("lab.DataProfile", DataProfile),
    ("lab.DataDive", DataDive),
    ("lab.CalendarHeatmap", CalendarHeatmap),
)

#: Options whose value is stored under another attribute than their own name.
_ATTRS: dict[tuple[str, str], str | None] = {
    ("Text", "text"): "content",
    ("Text", "file"): None,  # read once; the JSON form keeps its text
    ("HTML", "html"): "content",
    ("Code", "code"): "content",
    ("Formula", "formula"): "content",
}

#: Options whose JSON key isn't their parameter's name: ``type`` already names the block.
_KEYS: dict[tuple[str, str], str] = {("Select", "type"): "select_type"}

#: Text options that only accept these strings (the constructor checks them).
_CHOICES: dict[tuple[str, str], tuple[str, ...]] = {
    ("Briefing", "export"): Briefing.EXPORTS,
    ("Banner", "side"): ("left", "right"),
    ("lab.DataDive", "layout"): ("scatter", "tile"),
    ("lab.CalendarHeatmap", "agg"): CalendarHeatmap.AGGS,
    ("lab.CalendarHeatmap", "views"): ("days", "hours"),
    ("lab.CalendarHeatmap", "week_start"): ("monday", "sunday"),
    ("lab.CalendarHeatmap", "on_click"): ("rows",),
}

_DEFS = "#/$defs/"


def _ref(name: str) -> dict[str, t.Any]:
    return {"$ref": _DEFS + name}


#: Options whose type hint is too loose (``t.Any``) or too wide to say what JSON they take.
_OVERRIDES: dict[tuple[str, str], dict[str, t.Any]] = {
    ("Plot", "figure"): _ref("figure"),
    ("Banner", "image"): _ref("image"),
    ("lab.CalendarHeatmap", "events"): {
        "anyOf": [{"type": "array", "items": {"type": "string"}}, _ref("table"), {"type": "null"}]
    },
}


# ── stand-ins for the types that only exist under TYPE_CHECKING ───────────────


class _Frame:
    """``pd.DataFrame`` in a hint: a table."""


class _Series:
    """``pd.Series`` in a hint: only by reference."""


class _Styler:
    """A pandas ``Styler`` in a hint: only by reference."""


class _Pandas:
    DataFrame = _Frame
    Series = _Series


_HINT_NAMES = {"pd": _Pandas, "Styler": _Styler, "Block": Block}


# ── the model ─────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Field:
    """One option of a block: a constructor parameter."""

    name: str  # the parameter
    key: str  # its key in the JSON: the same, but for Select's type (select_type)
    schema: dict[str, t.Any]  # JSON Schema of its value, a reference aside
    required: bool
    default: t.Any  # inspect.Parameter.empty when required
    description: str
    attr: str | None  # where a block keeps its value; None: never written by to_spec


@dataclass(frozen=True)
class BlockType:
    """A block class as the JSON form sees it."""

    name: str
    cls: type[Block]
    fields: tuple[Field, ...]
    description: str

    @property
    def container(self) -> bool:
        return issubclass(self.cls, ContainerBlock)

    @property
    def min_blocks(self) -> int:
        return self.cls.min_blocks if issubclass(self.cls, ContainerBlock) else 0


@functools.cache
def block_types() -> dict[str, BlockType]:
    """Every block type the JSON form knows, by its ``type`` name."""
    return {name: _block_type(name, cls) for name, cls in _TYPES}


@functools.cache
def root_type() -> BlockType:
    """The report itself (:class:`~briefing.Briefing`): its options sit at the top of the JSON."""
    return _block_type("Briefing", Briefing)


def type_name(block: Block) -> str | None:
    """The ``type`` of *block* in the JSON form, or ``None`` for a class it doesn't know."""
    return next((name for name, cls in _TYPES if type(block) is cls), None)


def _block_type(name: str, cls: type[Block]) -> BlockType:
    docs = _arg_docs(cls.__doc__ or "")
    hints = t.get_type_hints(cls.__init__, localns=_HINT_NAMES)
    fields = []
    for param in inspect.signature(cls.__init__).parameters.values():
        if param.name in ("self", "blocks") or param.kind is param.VAR_POSITIONAL:
            continue
        key = (name, param.name)
        if key in _OVERRIDES:
            schema = _OVERRIDES[key]
        elif param.name == "name":
            schema = {"anyOf": [_ref("name"), {"type": "null"}]}
        else:
            schema = _to_schema(hints[param.name], _CHOICES.get(key))
        fields.append(Field(
            name=param.name,
            key=_KEYS.get(key, param.name),
            schema=schema,
            required=param.default is param.empty,
            default=param.default,
            description=docs.get(param.name, ""),
            attr=_ATTRS.get(key, param.name),
        ))
    return BlockType(name=name, cls=cls, fields=tuple(fields), description=_summary(cls.__doc__ or ""))


# ── type hints → JSON Schema ──────────────────────────────────────────────────

_SIMPLE = ("string", "integer", "number", "boolean", "null")


def _to_schema(hint: t.Any, choices: tuple[str, ...] | None = None) -> dict[str, t.Any]:
    origin, args = t.get_origin(hint), t.get_args(hint)
    if origin in (t.Union, types.UnionType):
        return _union([
            _to_schema(a, choices) for a in args
            if a not in (t.Any, _Series, _Styler) and t.get_origin(a) is not collections.abc.Callable  # by reference
        ])
    if origin is dict:
        return {"type": "object", "additionalProperties": _to_schema(args[1], choices)}
    if hint is type(None):
        return {"type": "null"}
    if hint is bool:
        return {"type": "boolean"}
    if hint is int:
        return {"type": "integer"}
    if hint is float:
        return {"type": "number"}
    if hint in (str, Path):
        return {"enum": list(choices)} if choices else {"type": "string"}
    if isinstance(hint, type) and issubclass(hint, enum.Enum):
        return {"enum": [m.value for m in hint]}
    if hint is _Frame:
        return _ref("table")
    if origin in (list, collections.abc.Sequence) or (origin is tuple and len(args) == 2 and args[1] is Ellipsis):
        return {"type": "array", "items": _to_schema(args[0], choices)}
    if origin is tuple:
        return {"type": "array", "prefixItems": [_to_schema(a) for a in args], "minItems": len(args),
                "maxItems": len(args)}
    raise TypeError(f"no JSON form for the type hint {hint!r}: add it to briefing.spec._model._OVERRIDES")


def _union(schemas: list[dict[str, t.Any]]) -> dict[str, t.Any]:
    """One schema for any of *schemas*: plain types merged, a choice standing for its string."""
    if any("enum" in s for s in schemas):
        schemas = [s for s in schemas if s != {"type": "string"}]
    simple: list[str] = []
    other: list[dict[str, t.Any]] = []
    for schema in schemas:
        if set(schema) == {"type"} and schema["type"] in _SIMPLE:
            simple.append(schema["type"])
        elif "anyOf" in schema:
            other.extend(schema["anyOf"])
        elif schema not in other:
            other.append(schema)
    if "number" in simple and "integer" in simple:
        simple.remove("integer")
    kinds = [k for k in _SIMPLE if k in simple]
    merged = ([{"type": kinds[0] if len(kinds) == 1 else kinds}] if kinds else []) + other
    return merged[0] if len(merged) == 1 else {"anyOf": merged}


# ── docstrings ────────────────────────────────────────────────────────────────

_ROLE = re.compile(r":\w+:`~?(?:[\w.]+\.)?([\w]+)`")


def _plain_text(rst: str) -> str:
    """A docstring's reStructuredText as plain text: roles become names, literals keep backticks."""
    return _ROLE.sub(r"\1", rst).replace("``", "`")


def _summary(doc: str) -> str:
    return _plain_text(" ".join(inspect.cleandoc(doc).split("\n\n")[0].split()))


def _arg_docs(doc: str) -> dict[str, str]:
    """``{parameter: description}`` from a Google-style ``Args:`` section."""
    docs: dict[str, str] = {}
    current: str | None = None
    inside = False
    for line in inspect.cleandoc(doc).splitlines():
        if line.strip() == "Args:":
            inside = True
            continue
        if not inside:
            continue
        if line and not line.startswith(" "):
            break
        entry = re.match(r"^ {4}\*{0,2}(\w+): ?(.*)$", line)
        if entry:
            current = entry.group(1)
            docs[current] = entry.group(2).strip()
        elif current and line.strip():
            docs[current] += " " + line.strip()
    return {name: _plain_text(text) for name, text in docs.items()}


# ── the JSON Schema ───────────────────────────────────────────────────────────


def _json_default(value: t.Any) -> t.Any:
    if isinstance(value, enum.Enum):
        return value.value
    if isinstance(value, tuple | list):
        return [_json_default(v) for v in value]
    return value


def _property(field: Field) -> dict[str, t.Any]:
    """A field's schema, a reference allowed in place of any value."""
    alternatives = field.schema.get("anyOf", [field.schema])
    prop: dict[str, t.Any] = {"description": field.description} if field.description else {}
    prop["anyOf"] = [*alternatives, _ref("ref")]
    if not field.required:
        prop["default"] = _json_default(field.default)
    return prop


def _object(block: BlockType, *, root: bool = False) -> dict[str, t.Any]:
    properties: dict[str, t.Any] = {}
    if root:
        properties["briefing"] = {
            "description": "The format version of this JSON (not briefing's version): "
            f"{FORMAT_VERSION}.",
            "const": FORMAT_VERSION,
        }
    else:
        properties["type"] = {"const": block.name}
    for field in block.fields:
        if field.attr is not None or field.name == "file":
            properties[field.key] = _property(field)
    required = ["briefing" if root else "type", *(f.key for f in block.fields if f.required)]
    if root:
        properties["blocks"] = {
            "description": "The report's blocks, in order: all of them Page blocks, or none.",
            "anyOf": [
                {"type": "array", "items": _ref("Page"), "minItems": 1},
                {"type": "array", "items": _ref("block"), "minItems": 1},
            ],
        }
        required.append("blocks")
    elif block.container:
        blocks: dict[str, t.Any] = {"description": "The child blocks, in order.", "type": "array",
                                    "items": _ref("block")}
        if block.min_blocks == 1:
            blocks["minItems"] = 1
            required.append("blocks")
        properties["blocks"] = blocks
    schema: dict[str, t.Any] = {"description": block.description, "type": "object", "properties": properties,
                                "required": required, "additionalProperties": False}
    if block.name == "Text":  # text= or file=
        schema["anyOf"] = [{"required": ["text"]}, {"required": ["file"]}]
    return schema


def build_schema() -> dict[str, t.Any]:
    """The JSON Schema of format :data:`FORMAT_VERSION`, built from the block classes."""
    types_ = block_types()
    defs: dict[str, t.Any] = {
        "block": {
            "description": "Any block but a Page (pages only go at the top level).",
            "oneOf": [_ref(name) for name in types_ if name != "Page"],
        },
        **{name: _object(block) for name, block in types_.items()},
        "name": {
            "description": "A block's name: a letter, then letters, digits, _ or -. It is the block's link "
            "(#page/name) and unique within its page.",
            "type": "string",
            "pattern": _NAME_RE.pattern,
        },
        "ref": {
            "description": "An object passed separately, by name: from_spec(spec, data={name: object}). "
            "Any option can be one.",
            "type": "object",
            "properties": {"ref": {"type": "string", "minLength": 1}},
            "required": ["ref"],
            "additionalProperties": False,
        },
        "table": {
            "description": "A table written into the JSON: column names, optional pandas dtypes "
            "(such as int64, float64, bool, object, datetime64[ns], category) and rows of values. "
            "Missing values are null; dates are ISO strings.",
            "type": "object",
            "properties": {
                "columns": {"type": "array", "items": {"type": "string"}},
                "dtypes": {"type": "array", "items": {"type": "string"}},
                "rows": {"type": "array", "items": {"type": "array"}},
            },
            "required": ["columns", "rows"],
            "additionalProperties": False,
        },
        "figure": {
            "description": "A chart written into the JSON: a Plotly figure's JSON or a Vega-Lite "
            "specification (drawn with Altair). Matplotlib and Bokeh figures go by reference.",
            "anyOf": [
                {"type": "object", "properties": {"plotly": {"type": "object"}}, "required": ["plotly"],
                 "additionalProperties": False},
                {"type": "object", "properties": {"vega-lite": {"type": "object"}}, "required": ["vega-lite"],
                 "additionalProperties": False},
            ],
        },
        "image": {
            "description": "An image file's path, or the image as a data: URI "
            "(data:image/png;base64,...).",
            "type": "string",
        },
    }
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": f"briefing report, format {FORMAT_VERSION}",
        **_object(root_type(), root=True),
        "description": "A briefing report as JSON: the same blocks and options as in Python. "
        "Render it with briefing.from_spec(spec, data) and check it with briefing.validate(spec, data).",
        "$defs": defs,
    }
