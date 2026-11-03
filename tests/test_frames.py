"""Dataframe intake — pandas plus anything convertible to it."""
from __future__ import annotations

import pandas as pd
import pytest

import briefing as bf
from briefing._frames import is_pandas_dataframe, looks_like_dataframe, to_pandas


def test_pandas_passthrough_is_identity() -> None:
    df = pd.DataFrame({"a": [1, 2], "b": ["x", "y"]})
    assert to_pandas(df) is df


def test_dict_of_columns() -> None:
    out = to_pandas({"a": [1, 2], "b": [3, 4]}, block="T")
    assert list(out.columns) == ["a", "b"]
    assert out.shape == (2, 2)


def test_list_of_row_dicts() -> None:
    out = to_pandas([{"a": 1}, {"a": 2}])
    assert out["a"].tolist() == [1, 2]


def test_pyarrow_table_via_interchange_or_to_pandas() -> None:
    pa = pytest.importorskip("pyarrow")
    tbl = pa.table({"a": [1, 2, 3], "b": ["p", "q", "r"]})
    out = to_pandas(tbl, block="DataTable")
    assert isinstance(out, pd.DataFrame)
    assert out["a"].tolist() == [1, 2, 3]


def test_polars_like_object_uses_to_pandas() -> None:
    class FakePolars:
        def __init__(self) -> None:
            self._pd = pd.DataFrame({"a": [9, 8]})

        def to_pandas(self) -> pd.DataFrame:
            return self._pd

    out = to_pandas(FakePolars())
    assert out["a"].tolist() == [9, 8]


def test_unknown_object_raises_briefing_error() -> None:
    with pytest.raises(bf.BriefingError, match="could not turn"):
        to_pandas(object(), block="DataTable")


def test_is_pandas_dataframe() -> None:
    assert is_pandas_dataframe(pd.DataFrame())
    assert not is_pandas_dataframe({"a": [1]})


def test_is_pandas_dataframe_subclass() -> None:
    class MyFrame(pd.DataFrame):
        pass

    assert is_pandas_dataframe(MyFrame({"a": [1]}))


def test_looks_like_dataframe() -> None:
    assert looks_like_dataframe(pd.DataFrame())

    class HasDunder:
        def __dataframe__(self, *a, **k): ...

    assert looks_like_dataframe(HasDunder())
    assert not looks_like_dataframe("not a frame")
    assert not looks_like_dataframe(42)


def test_data_blocks_accept_a_non_pandas_frame() -> None:
    pa = pytest.importorskip("pyarrow")
    tbl = pa.table({"x": [1, 2, 3, 4], "g": ["a", "a", "b", "b"]})
    # Each data block should normalise the input and expose a pandas frame.
    assert isinstance(bf.DataTable(tbl).df, pd.DataFrame)
    assert isinstance(bf.lab.DataProfile(tbl).df, pd.DataFrame)
    assert isinstance(bf.lab.DataDive(tbl).df, pd.DataFrame)
    assert isinstance(bf.Table(tbl).data, pd.DataFrame)


def test_wrap_block_auto_wraps_a_non_pandas_frame() -> None:
    pa = pytest.importorskip("pyarrow")
    tbl = pa.table({"x": [1, 2]})
    report = bf.Briefing(tbl)
    assert type(report.blocks[0]).__name__ == "DataTable"
