"""Dataframe intake — accept more than just pandas.

``briefing`` renders tables and profiles against a pandas DataFrame internally,
but pandas is an optional extra (``pip install briefing[pandas]``) and callers
should not be forced to use pandas as *their* dataframe library.

:func:`to_pandas` normalises whatever a data block is handed into a pandas
DataFrame:

* a pandas DataFrame passes straight through;
* anything implementing the dataframe interchange protocol (``__dataframe__`` —
  polars, pyarrow, modin, cuDF, vaex, …) is converted via
  ``pandas.api.interchange.from_dataframe``;
* anything else exposing ``.to_pandas()`` (pyarrow Table, polars, …) uses that;
* a plain ``dict`` / list-of-rows is passed to the ``pandas.DataFrame``
  constructor.

A native pandas-free rendering path is out of scope for now (tracked in the
development plan); this keeps the door open to other dataframe libraries without
that rewrite.
"""
from __future__ import annotations

import contextlib
import sys
import typing as t

from briefing._error import BriefingError

if t.TYPE_CHECKING:
    import pandas as pd

_INSTALL_HINT = "install it with:  pip install briefing[pandas]"


def _import_pandas() -> t.Any:
    try:
        import pandas
    except ImportError as exc:  # pragma: no cover - exercised only without pandas
        raise BriefingError(f"This block needs pandas — {_INSTALL_HINT}") from exc
    return pandas


def is_pandas_dataframe(obj: object) -> bool:
    """True if *obj* is a pandas DataFrame, without importing pandas eagerly."""
    # If pandas was never imported, nothing can be a pandas DataFrame.
    pandas = sys.modules.get("pandas")
    return pandas is not None and isinstance(obj, pandas.DataFrame)


def looks_like_dataframe(obj: object) -> bool:
    """Heuristic for auto-wrapping: does *obj* look like a tabular frame?"""
    return (
        is_pandas_dataframe(obj)
        or hasattr(obj, "__dataframe__")
        or (hasattr(obj, "to_pandas") and callable(obj.to_pandas))
    )


def to_pandas(obj: object, *, block: str = "This block") -> pd.DataFrame:
    """Return *obj* as a pandas DataFrame, converting from other libraries.

    Args:
        obj: a pandas / polars / pyarrow / interchange-protocol frame, or
            something the ``pandas.DataFrame`` constructor accepts.
        block: name used in error messages (e.g. ``"DataTable"``).
    """
    pandas = _import_pandas()

    if isinstance(obj, pandas.DataFrame):
        return t.cast("pd.DataFrame", obj)

    # Dataframe interchange protocol — polars, pyarrow, modin, cuDF, vaex, …
    if hasattr(obj, "__dataframe__"):
        with contextlib.suppress(Exception):
            return t.cast("pd.DataFrame", pandas.api.interchange.from_dataframe(obj))

    # pyarrow.Table, polars.DataFrame, …
    to_pd = getattr(obj, "to_pandas", None)
    if callable(to_pd):
        return t.cast("pd.DataFrame", to_pd())

    # dict of columns / list of row dicts / numpy structured array …
    if isinstance(obj, dict | list):
        return t.cast("pd.DataFrame", pandas.DataFrame(obj))

    raise BriefingError(
        f"{block} could not turn {type(obj).__module__}.{type(obj).__qualname__} "
        "into a table. Pass a pandas / polars / pyarrow DataFrame, an object "
        "implementing the dataframe interchange protocol, or a dict of columns."
    )
