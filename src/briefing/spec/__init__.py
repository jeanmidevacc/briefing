"""A report as JSON: ``to_spec``, ``from_spec``, ``validate`` and ``schema`` (#31).

Python and JSON are two ways of writing the same report. The JSON names each block by
its class (``"type": "Text"``, ``"lab.DataDive"``) and its options by the constructor's
parameter names; tables and charts go into the JSON or, by name, into a ``data`` dict
passed alongside. ``briefing/schema/v1.json`` is the JSON Schema of the format.
"""
from __future__ import annotations

import copy
import functools
import json
import typing as t
from collections.abc import Mapping
from importlib.resources import files

from briefing.blocks.layout import Briefing
from briefing.renderers.size import DEFAULT_MAX_SIZE
from briefing.spec import _convert, _validate
from briefing.spec._diagnostic import Diagnostic
from briefing.spec._model import FORMAT_VERSION


def to_spec(report: object, *, inline: bool = False) -> tuple[dict[str, t.Any], dict[str, t.Any]]:
    """The JSON form of *report*, and the objects it names by reference.

    Every option is written as JSON, except those left at their default. Dataframes,
    figures and images go into the second dict and appear in the JSON as
    ``{"ref": "<name>"}``; :func:`from_spec` takes both back. A block's references are
    named after the block's ``name``, else its type (``"datatable-1"``).

    Args:
        report: A :class:`Briefing`, a block, or a list of blocks.
        inline: Write tables, Plotly and Altair charts and images into the JSON, each
            only when it comes back exactly the same (a plain DataFrame of numbers, text,
            booleans and dates, for instance). Matplotlib and Bokeh figures and styled
            tables always go by reference.

    Returns:
        ``(spec, data)``: the JSON form as a dict, ready for ``json.dumps``, and
        ``{name: object}`` for its references.

    Raises:
        BriefingError: For a block class briefing doesn't define, which has no JSON form.

    Example::

        spec, data = bf.to_spec(report)
        report_again = bf.from_spec(spec, data)
        print(json.dumps(bf.to_spec(report, inline=True)[0], indent=2))
    """
    return _convert.to_spec(report, inline=inline)


def from_spec(spec: object, data: Mapping[str, t.Any] | None = None) -> Briefing:
    """Build the report a JSON form describes.

    Args:
        spec: The JSON form: a dict, JSON text, or the path of a ``.json`` file.
        data: The objects its references name: ``{"sales": df, "trend": fig}``.

    Returns:
        The report, as if written in Python.

    Raises:
        BriefingError: When the JSON can't be built into a report; the message lists
            each problem with its place in the JSON. :func:`validate` returns them as
            :class:`Diagnostic` objects instead.

    Example::

        report = bf.from_spec({
            "briefing": 1,
            "blocks": [
                {"type": "Text", "text": "# Q1"},
                {"type": "DataTable", "df": {"ref": "sales"}},
            ],
        }, data={"sales": df})
        bf.save(report, "q1.html")
    """
    return _convert.from_spec(spec, data)


def validate(
    report_or_spec: object, data: Mapping[str, t.Any] | None = None, max_size: int | str | None = DEFAULT_MAX_SIZE
) -> list[Diagnostic]:
    """Every problem in a report or its JSON form, as a list; never raises.

    Checks the JSON's blocks and options against the format, each block's own checks,
    names (unique within their page, unlike the ids briefing makes up), and that the
    report renders. Without *data*, references are not checked, and neither is rendering.

    Errors stop the report from being built or rendered: unknown block types and options,
    wrong types, missing options, unknown references, duplicate names, ``Page`` blocks
    mixed with others or nested, empty containers. Warnings don't: a ``Select`` with
    fewer than two panels or without labels, deprecated options, the warnings blocks give
    (rows dropped, a sample drawn…), and a report bigger than *max_size*.

    Args:
        report_or_spec: A :class:`Briefing`, a block or a list of blocks, or a JSON form:
            a dict, JSON text, or the path of a ``.json`` file.
        data: The objects the JSON's references name, as for :func:`from_spec`.
        max_size: Warn (``too-big``) when the rendered report is bigger than this, as
            :func:`save` does; ``None`` doesn't check the size.

    Returns:
        The problems found, errors and warnings, each with where it is; empty when the
        report is fine.

    Example::

        problems = bf.validate(spec, data)
        if not any(p.severity == "error" for p in problems):
            bf.save(bf.from_spec(spec, data), "report.html")
        for p in problems:
            print(p)  # error unknown-option at /blocks/0/colums: Group has no option "colums". ...
    """
    return _validate.validate(report_or_spec, data, max_size)


@functools.cache
def _schema_text() -> str:
    return (files("briefing") / "schema" / f"v{FORMAT_VERSION}.json").read_text(encoding="utf-8")


def schema() -> dict[str, t.Any]:
    """The JSON Schema of a report's JSON form (format 1).

    The same file ships as ``briefing/schema/v1.json``. Each block type is a definition
    in ``$defs`` with a description and, for each option, its description and default.

    Returns:
        The schema, as a dict (a fresh copy each time).

    Example::

        options = bf.schema()["$defs"]["Group"]["properties"]
    """
    return copy.deepcopy(_parsed_schema())


@functools.cache
def _parsed_schema() -> dict[str, t.Any]:
    parsed: dict[str, t.Any] = json.loads(_schema_text())
    return parsed


__all__ = ["FORMAT_VERSION", "Diagnostic", "from_spec", "schema", "to_spec", "validate"]
