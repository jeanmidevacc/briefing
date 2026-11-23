"""Experimental functions (#199) say so: in a warning, once per session, and in their docstring."""
from __future__ import annotations

import inspect
import warnings
from collections.abc import Callable

import pytest

import briefing as bf
from briefing import _experimental

#: Every experimental function, by the name its warning gives it.
EXPERIMENTAL: dict[str, Callable[..., object]] = {
    "bf.deck.from_report": bf.deck.from_report,
}


def test_the_warning_is_a_user_warning_people_can_silence() -> None:
    assert issubclass(bf.ExperimentalWarning, UserWarning)
    assert "ExperimentalWarning" in bf.__all__


def test_experimental_warns_once_per_name() -> None:
    _experimental._warned.discard("bf.example")
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        _experimental.experimental("bf.example", stacklevel=2)
        _experimental.experimental("bf.example", stacklevel=2)
    assert len(caught) == 1 and caught[0].category is bf.ExperimentalWarning
    assert "bf.example is experimental" in str(caught[0].message)
    assert "filterwarnings('ignore', category=bf.ExperimentalWarning)" in str(caught[0].message)


@pytest.mark.parametrize("name", list(EXPERIMENTAL))
def test_each_experimental_function_says_so_in_its_docstring(name: str) -> None:
    assert (inspect.getdoc(EXPERIMENTAL[name]) or "").startswith("*Experimental.*")
