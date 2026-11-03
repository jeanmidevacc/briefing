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


# ── Plot(scale=...) (#7) ──────────────────────────────────────────────────────


def test_plot_scale_warns_and_points_to_figsize() -> None:
    with pytest.warns(DeprecationWarning, match=r"scale=.*removed after 0\.2.*figsize"):
        bf.Plot(object(), scale=2.0)


def test_plot_without_scale_does_not_warn() -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        bf.Plot(object())


def test_plot_scale_is_gone_after_0_2() -> None:
    # Fails from 0.3 on until `scale` is removed, alongside the other deprecated aliases.
    import inspect

    version = tuple(int(part) for part in bf.__version__.split(".")[:2])
    if version >= (0, 3):
        assert "scale" not in inspect.signature(bf.Plot).parameters
