"""A dataframe's columns as the page tests them (#16, #238): one encoding for every receiver.

A ``DataDive`` carries its rows this way, and so does a ``DataTable`` that a lab block's
selection targets (``selects=``): numbers as numbers, dates as epoch milliseconds (UTC),
everything else as categories, a list of levels (their text, as :func:`text` cuts it) and
one code per row. A sender's tests (``lab/_select.py``) are written against this encoding,
so a selection finds the same rows in either receiver.
"""
from __future__ import annotations

import math
import typing as t

#: Text values longer than this are cut, with an ellipsis, to keep the file light.
MAX_TEXT = 200


def col_kind(series: t.Any) -> str:
    """``"numeric"``, ``"datetime"`` or ``"categorical"`` (booleans and text included)."""
    import pandas as pd

    if pd.api.types.is_bool_dtype(series):
        return "categorical"
    if pd.api.types.is_numeric_dtype(series):
        return "numeric"
    if pd.api.types.is_datetime64_any_dtype(series):
        return "datetime"
    return "categorical"


def text(value: t.Any) -> str:
    """A category's text on the page."""
    out = str(value)
    return out if len(out) <= MAX_TEXT else out[: MAX_TEXT - 1] + "…"


def encode(name: str, series: t.Any) -> dict[str, t.Any]:
    """One column for the page: ``{"name", "kind", "values"}``, or levels and codes for categories."""
    import pandas as pd

    kind = col_kind(series)
    if kind == "numeric":  # JSON has no NaN or infinity: both are missing, as before (#16)
        values = [None if pd.isna(v) or math.isinf(v) else (int(v) if float(v).is_integer() and abs(v) < 2**53
                  else float(v)) for v in series.tolist()]
        return {"name": name, "kind": kind, "values": values}
    if kind == "datetime":
        stamps = series.dt.tz_convert("UTC").dt.tz_localize(None) if series.dt.tz is not None else series
        ms = stamps.astype("datetime64[ms]").astype("int64").tolist()
        return {"name": name, "kind": kind, "values": [None if missing else v for v, missing in
                                                        zip(ms, series.isna().tolist(), strict=True)]}
    codes, levels = pd.factorize(series, use_na_sentinel=True)
    return {"name": name, "kind": "categorical", "levels": [text(v) for v in levels.tolist()],
            "codes": codes.tolist()}


__all__ = ["MAX_TEXT", "col_kind", "encode", "text"]
