"""Deprecated aliases kept for one release after the folio -> bulletin -> briefing rename."""
from __future__ import annotations

import warnings

import pytest

import briefing as bf

RENAMED = [
    ("Blocks", "Briefing"),
    ("BaseBlock", "Block"),
    ("save_report", "save"),
    ("stringify_report", "stringify"),
]


@pytest.mark.parametrize(("old", "new"), RENAMED)
def test_old_name_warns_and_returns_new_object(old: str, new: str) -> None:
    with pytest.warns(DeprecationWarning, match=rf"briefing\.{old}.*briefing\.{new}"):
        obj = getattr(bf, old)
    assert obj is getattr(bf, new)


@pytest.mark.parametrize(("old", "new"), RENAMED)
def test_new_name_does_not_warn(old: str, new: str) -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        getattr(bf, new)


MOVED_TO_LAB = ["DataProfile", "DataDive"]


@pytest.mark.parametrize("name", MOVED_TO_LAB)
def test_lab_block_top_level_warns_and_returns_lab_object(name: str) -> None:
    with pytest.warns(DeprecationWarning, match=rf"briefing\.{name}.*briefing\.lab\.{name}"):
        obj = getattr(bf, name)
    assert obj is getattr(bf.lab, name)


@pytest.mark.parametrize("name", MOVED_TO_LAB)
def test_lab_block_via_lab_does_not_warn(name: str) -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        getattr(bf.lab, name)


def test_unknown_attribute_still_raises_attributeerror() -> None:
    with pytest.raises(AttributeError):
        bf.DefinitelyNotAThing
