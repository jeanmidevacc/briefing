"""Hypothesis strategies for the property tests: strings, raw markup and dataframes a report may meet."""
from __future__ import annotations

import datetime as dt
import typing as t
from collections.abc import Callable

import pandas as pd
from hypothesis import strategies as st

from tests.contract import PAYLOAD

#: Strings that have broken HTML reports before, or would if they weren't escaped or closed.
_TRICKY = [
    PAYLOAD, "", " ", "</script>", "<!--", "-->", "<script>", "<style>", "<textarea>", '<a title="', "]]>",
    "&amp;", "&", "'\"", "\u202e", "\U0001f600", "a\r\nb", "\x00",
]

#: Any string, often one of the tricky ones.
texts = st.one_of(st.text(max_size=30), st.sampled_from(_TRICKY))

#: Pieces of raw HTML, so that joined they open, close and nest comments, tags and attributes.
_MARKUP_PIECES = [
    "<", ">", "/", "!", "?", "-", "=", '"', "'", " ", "\n", "a", "<!--", "-->", "--!>", "<!-->", "<script>",
    "</script>", "<style", "</style>", "<textarea>", "<xmp>", "<div", "<div>", "</div>", "<a title=", "<!x", "<?",
]

#: Raw HTML as the author of a ``Text`` or ``HTML`` block might leave it, closed or not.
markup = st.lists(st.sampled_from(_MARKUP_PIECES), max_size=12).map("".join)

_FLOATS = st.floats(allow_nan=True, allow_infinity=True) | st.sampled_from([0.0, -0.0, 1e308, -1e308, 5e-324])
_INTS = st.integers(min_value=-(2**63), max_value=2**63 - 1)
_DATETIMES = st.datetimes(min_value=dt.datetime(1900, 1, 1), max_value=dt.datetime(2200, 1, 1))


def _nullable(values: st.SearchStrategy[t.Any]) -> st.SearchStrategy[t.Any]:
    return st.one_of(st.none(), values)


def _series(values: st.SearchStrategy[t.Any], make: Callable[[list[t.Any]], pd.Series]) -> Callable[[int], t.Any]:
    return lambda rows: st.lists(values, min_size=rows, max_size=rows).map(make)


#: One column of each kind a report is likely to meet, as a function of its row count.
_COLUMNS: dict[str, Callable[[int], st.SearchStrategy[pd.Series]]] = {
    "int": _series(_INTS, lambda v: pd.Series(v, dtype="int64")),
    "nullable-int": _series(_nullable(_INTS), lambda v: pd.Series(v, dtype="Int64")),
    "float": _series(_FLOATS, lambda v: pd.Series(v, dtype="float64")),
    "bool": _series(st.booleans(), lambda v: pd.Series(v, dtype="bool")),
    "string": _series(_nullable(texts), pd.Series),
    "category": _series(_nullable(texts), lambda v: pd.Series(v, dtype="category")),
    "datetime": _series(_nullable(_DATETIMES), lambda v: pd.Series(pd.to_datetime(v))),
    "datetime-utc": _series(_nullable(_DATETIMES), lambda v: pd.Series(pd.to_datetime(v, utc=True))),
    "mixed": _series(_nullable(st.one_of(_INTS, _FLOATS, texts, st.booleans())), lambda v: pd.Series(v, dtype=object)),
}


@st.composite
def dataframes(draw: st.DrawFn) -> pd.DataFrame:
    """A dataframe of 0–12 rows and 1–5 columns of any kind, with unicode column names."""
    rows = draw(st.integers(min_value=0, max_value=12))
    names = draw(st.lists(texts, min_size=1, max_size=5, unique=True))
    kinds = [draw(st.sampled_from(sorted(_COLUMNS))) for _ in names]
    return pd.DataFrame({name: draw(_COLUMNS[kind](rows)) for name, kind in zip(names, kinds, strict=True)})
