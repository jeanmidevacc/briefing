"""Property tests: any text, markup and dataframe render into a report that follows the contract (#45).

Hypothesis draws strings (unicode, control characters, markup, the contract's
script payload), raw HTML and dataframes (every common dtype, nulls, extreme
numbers) from ``tests/strategies.py``, and checks that each block renders them
without error, keeps user text escaped, leaves the rest of the report in place,
passes every rule in ``tests/contract.py`` and gives the same bytes twice.

The ``ci`` profile in ``conftest.py`` makes runs reproducible: CI draws the same
examples every time. Locally, examples are random and failures are kept in
``.hypothesis/`` so the next run tries them first.
"""
from __future__ import annotations

from collections.abc import Callable

import pandas as pd
import pytest
from hypothesis import assume, given

import briefing as bf
from briefing.blocks.base import Block
from tests.contract import MARKER, RULES, check_deterministic, check_user_text_escaped, parse_report
from tests.golden import NOW
from tests.html_helpers import find_one
from tests.strategies import dataframes, markup, texts


def _check(make: Callable[[], Block]) -> None:
    """Render ``make()`` and check it against the contract, twice for determinism."""

    def render() -> str:
        return bf.stringify(bf.Briefing(make()), name="Property report", now=NOW)

    soup = parse_report(render())
    for rule in RULES.values():
        rule(soup)
    check_user_text_escaped(soup)
    # Nothing a block holds may swallow what follows it, down to the last line.
    assert "Made with briefing" in find_one(soup, ".bf-report__footer").get_text()
    check_deterministic(render)


@given(content=texts.filter(lambda s: s and MARKER not in s), label=texts)
def test_text_renders_any_string(content: str, label: str) -> None:
    # Text("") is an error on purpose. Text is markdown with raw HTML by design, so the
    # script payload goes only in its label, which must stay escaped.
    _check(lambda: bf.Select(bf.Text(content, label=label), bf.Text("other", label="Other")))


def _parser_follows_raw_text_rules() -> bool:
    """Python's html.parser reads <textarea> as raw text, as browsers do, since its 2025 security releases."""
    return parse_report("<textarea><script></textarea><p id='after'></p>").find(id="after") is not None


@pytest.mark.skipif(not _parser_follows_raw_text_rules(), reason="this Python's html.parser predates the raw-text "
                    "rules browsers follow; CI's current Pythons and the browser test in test_text.py cover it")
@given(content=markup)
def test_raw_markup_stays_in_its_block(content: str) -> None:
    # Browsers end a comment at "<!-->" and "<!--->", as the HTML standard says; Python's
    # html.parser, which the contract uses, doesn't. The browser test in test_text.py covers them.
    assume("<!-->" not in content and "<!--->" not in content)
    _check(lambda: bf.Select(bf.HTML(content, label="A"), bf.Text(f"x{content}", label="B")))


@given(df=dataframes(), caption=texts)
def test_table_renders_any_frame(df: pd.DataFrame, caption: str) -> None:
    _check(lambda: bf.Table(df, caption=caption))


@given(df=dataframes(), caption=texts)
def test_datatable_renders_any_frame(df: pd.DataFrame, caption: str) -> None:
    _check(lambda: bf.DataTable(df, caption=caption))


@given(df=dataframes())
def test_dataprofile_renders_any_frame(df: pd.DataFrame) -> None:
    _check(lambda: bf.lab.DataProfile(df))


@given(df=dataframes())
def test_datadive_renders_any_frame(df: pd.DataFrame) -> None:
    _check(lambda: bf.lab.DataDive(df))
