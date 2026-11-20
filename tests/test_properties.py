"""Property tests: any text and any dataframe render into a report that follows the contract (#45).

Hypothesis draws strings (unicode, control characters, markup, the contract's
script payload) and dataframes (every common dtype, nulls, extreme numbers) and
checks that each block renders them without error, keeps user text escaped,
passes every rule in ``tests/contract.py`` and gives the same bytes twice.

The ``ci`` profile in ``conftest.py`` makes runs reproducible: CI draws the same
examples every time. Locally, examples are random and failures are kept in
``.hypothesis/`` so the next run tries them first.
"""
from __future__ import annotations

import datetime as dt
import typing as t
from collections.abc import Callable

import pandas as pd
from hypothesis import given
from hypothesis import strategies as st

import briefing as bf
from briefing.blocks.base import Block
from tests.contract import MARKER, PAYLOAD, RULES, check_deterministic, check_user_text_escaped, parse_report
from tests.golden import NOW

# ── strategies ────────────────────────────────────────────────────────────────

#: Strings that have broken HTML reports before, or would if they weren't escaped.
_TRICKY = [PAYLOAD, "", " ", "</script>", "<!--", "-->", "]]>", "&amp;", "&", "'\"", "‮", "😀", "a\r\nb", "\x00"]

texts = st.one_of(st.text(max_size=30), st.sampled_from(_TRICKY))

_FLOATS = st.floats(allow_nan=True, allow_infinity=True) | st.sampled_from([0.0, -0.0, 1e308, -1e308, 5e-324])
_INTS = st.integers(min_value=-(2**63), max_value=2**63 - 1)
_DATETIMES = st.datetimes(min_value=dt.datetime(1900, 1, 1), max_value=dt.datetime(2200, 1, 1))


def _nullable(values: st.SearchStrategy[t.Any]) -> st.SearchStrategy[t.Any]:
    return st.one_of(st.none(), values)


#: One column of each kind a report is likely to meet, as a function of its row count.
_COLUMNS: dict[str, Callable[[int], st.SearchStrategy[t.Any]]] = {
    "int": lambda n: st.lists(_INTS, min_size=n, max_size=n).map(lambda v: pd.Series(v, dtype="int64")),
    "nullable-int": lambda n: st.lists(_nullable(_INTS), min_size=n, max_size=n).map(
        lambda v: pd.Series(v, dtype="Int64")
    ),
    "float": lambda n: st.lists(_FLOATS, min_size=n, max_size=n).map(lambda v: pd.Series(v, dtype="float64")),
    "bool": lambda n: st.lists(st.booleans(), min_size=n, max_size=n).map(lambda v: pd.Series(v, dtype="bool")),
    "string": lambda n: st.lists(_nullable(texts), min_size=n, max_size=n).map(pd.Series),
    "category": lambda n: st.lists(_nullable(texts), min_size=n, max_size=n).map(
        lambda v: pd.Series(v, dtype="category")
    ),
    "datetime": lambda n: st.lists(_nullable(_DATETIMES), min_size=n, max_size=n).map(
        lambda v: pd.Series(pd.to_datetime(v))
    ),
    "datetime-utc": lambda n: st.lists(_nullable(_DATETIMES), min_size=n, max_size=n).map(
        lambda v: pd.Series(pd.to_datetime(v, utc=True))
    ),
    "mixed": lambda n: st.lists(_nullable(st.one_of(_INTS, _FLOATS, texts, st.booleans())), min_size=n, max_size=n)
    .map(lambda v: pd.Series(v, dtype="object")),
}


@st.composite
def dataframes(draw: st.DrawFn) -> pd.DataFrame:
    """A dataframe of 0–12 rows and 1–5 columns of any kind, with unicode column names."""
    rows = draw(st.integers(min_value=0, max_value=12))
    names = draw(st.lists(texts, min_size=1, max_size=5, unique=True))
    kinds = [draw(st.sampled_from(sorted(_COLUMNS))) for _ in names]
    return pd.DataFrame({name: draw(_COLUMNS[kind](rows)) for name, kind in zip(names, kinds, strict=True)})


# ── the property ──────────────────────────────────────────────────────────────


def _check(make: Callable[[], Block]) -> None:
    """Render ``make()`` and check it against the contract, twice for determinism."""

    def render() -> str:
        return bf.stringify(bf.Briefing(make()), name="Property report", now=NOW)

    soup = parse_report(render())
    for rule in RULES.values():
        rule(soup)
    check_user_text_escaped(soup)
    check_deterministic(render)


@given(content=texts.filter(lambda s: s and MARKER not in s), label=texts)
def test_text_renders_any_string(content: str, label: str) -> None:
    # Text("") is an error on purpose. Text is markdown with raw HTML by design, so the
    # script payload goes only in its label, which must stay escaped.
    _check(lambda: bf.Select(bf.Text(content, label=label), bf.Text("other", label="Other")))


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
