"""Every public block and function documents itself, for the API reference (#41)."""
from __future__ import annotations

import enum
import inspect
import re
import typing as t

import pytest

import briefing as bf


def _public() -> list[tuple[str, t.Any]]:
    names = [(f"briefing.{n}", getattr(bf, n)) for n in bf.__all__]
    names += [(f"briefing.lab.{n}", getattr(bf.lab, n)) for n in bf.lab.__all__]
    return [(n, o) for n, o in names if inspect.isclass(o) or inspect.isfunction(o)]


def _parameters(obj: t.Any) -> list[str]:
    if inspect.isclass(obj) and issubclass(obj, enum.Enum | BaseException):
        return []  # enum members and exception messages are not documented as Args
    target = obj.__init__ if inspect.isclass(obj) else obj
    return [p for p in inspect.signature(target).parameters if p not in ("self", "cls")]


@pytest.mark.parametrize(("name", "obj"), _public(), ids=[n for n, _ in _public()])
def test_has_a_docstring_with_args(name: str, obj: t.Any) -> None:
    doc = inspect.getdoc(obj)
    assert doc, f"{name} has no docstring"
    params = _parameters(obj)
    if not params:
        return
    section = re.search(r"^Args:\n(.*?)(?=^\S|\Z)", doc, re.M | re.S)
    assert section, f"{name} takes {params} but has no Args: section"
    documented = set(re.findall(r"^\s+\**(\w+)(?:\s*\([^)]*\))?:", section.group(1), re.M))
    missing = [p for p in params if p not in documented]
    assert not missing, f"{name}: Args: doesn't document {missing}"


def test_the_walk_covers_the_api() -> None:
    names = {n for n, _ in _public()}
    assert {"briefing.Banner", "briefing.save_pdf", "briefing.lab.CalendarHeatmap"} <= names
