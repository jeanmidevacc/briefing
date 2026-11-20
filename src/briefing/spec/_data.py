"""Tables, charts and images written into the JSON form of a report (#31).

Each ``encode_*`` returns the JSON of an object, or ``None`` when that JSON wouldn't give
back exactly the same object; :func:`~briefing.spec.to_spec` then keeps the object as a
reference. Each ``decode_*`` builds the object again and raises
:class:`~briefing.BriefingError` with what is wrong.

pandas and the chart libraries are imported inside the functions, only when used.
"""
from __future__ import annotations

import base64
import binascii
import datetime as dt
import json
import math
import numbers
import typing as t
import urllib.parse

from briefing._error import BriefingError
from briefing.blocks.banner import _image_type

if t.TYPE_CHECKING:
    import pandas as pd

_INFINITIES = {"Infinity": math.inf, "-Infinity": -math.inf}


class _NoJSON(Exception):
    """A value with no exact JSON form."""


# ── tables ────────────────────────────────────────────────────────────────────


def _cell(value: object) -> t.Any:
    """One value of a column as JSON: missing values are null, dates ISO strings, infinities strings."""
    import pandas as pd

    if value is None or value is pd.NaT or value is pd.NA:
        return None
    if isinstance(value, bool) or type(value).__name__ == "bool_":
        return bool(value)
    if isinstance(value, numbers.Integral):
        return int(value)
    if isinstance(value, numbers.Real):
        number = float(value)
        if math.isnan(number):
            return None
        return "Infinity" if number == math.inf else "-Infinity" if number == -math.inf else number
    if isinstance(value, str):
        return value
    if isinstance(value, dt.date):  # datetime and pandas.Timestamp are dates too
        return value.isoformat()
    raise _NoJSON


def encode_table(frame: object) -> dict[str, t.Any] | None:
    """``{"columns", "dtypes", "rows"}`` for *frame*, or ``None`` when it wouldn't come back the same.

    Only a plain ``pandas.DataFrame`` qualifies: text column names, the default index,
    and values JSON can hold (numbers, text, booleans, dates, missing values).
    """
    import pandas as pd

    if type(frame) is not pd.DataFrame:
        return None
    index = frame.index
    if not (isinstance(index, pd.RangeIndex) and index.start == 0 and index.step == 1 and index.name is None):
        return None
    if not all(isinstance(c, str) for c in frame.columns) or frame.columns.has_duplicates or frame.columns.name:
        return None
    try:
        columns = [[_cell(v) for v in frame[c].tolist()] for c in frame.columns]
    except _NoJSON:
        return None
    spec = {
        "columns": list(frame.columns),
        "dtypes": [str(d) for d in frame.dtypes],
        "rows": [list(row) for row in zip(*columns, strict=True)] if columns else [],
    }
    try:
        back = decode_table(spec)
    except (BriefingError, ValueError, TypeError):
        return None
    return spec if _same_frame(frame, back) else None


def _same_frame(a: pd.DataFrame, b: pd.DataFrame) -> bool:
    import pandas as pd

    if len(a) != len(b):
        return False
    try:
        pd.testing.assert_frame_equal(a, b, check_exact=True)
    except AssertionError:
        return False
    for column in a.columns:  # object columns: the same Python types (None and NaN look alike above)
        if a[column].dtype == object and [type(v) for v in a[column]] != [type(v) for v in b[column]]:
            return False
    return True


def decode_table(spec: dict[str, t.Any]) -> pd.DataFrame:
    """A DataFrame from ``{"columns", "rows"}`` and optional ``"dtypes"``."""
    import pandas as pd

    columns, rows, dtypes = spec.get("columns"), spec.get("rows"), spec.get("dtypes")
    if not isinstance(columns, list) or not all(isinstance(c, str) for c in columns):
        raise BriefingError('a table\'s "columns" must be a list of column names.')
    if len(set(columns)) != len(columns):
        raise BriefingError('a table\'s "columns" must be different names.')
    if not isinstance(rows, list) or not all(isinstance(r, list) for r in rows):
        raise BriefingError('a table\'s "rows" must be a list of rows, each a list of values.')
    for i, row in enumerate(rows):
        if len(row) != len(columns):
            raise BriefingError(f"row {i} of the table has {len(row)} values for {len(columns)} columns.")
    if dtypes is None:
        return pd.DataFrame(rows, columns=columns) if rows else pd.DataFrame({c: [] for c in columns})
    if not isinstance(dtypes, list) or len(dtypes) != len(columns) or not all(isinstance(d, str) for d in dtypes):
        raise BriefingError('a table\'s "dtypes" must be a list of pandas dtype names, one per column.')
    data = {}
    for i, (name, dtype) in enumerate(zip(columns, dtypes, strict=True)):
        values = [row[i] for row in rows]
        if dtype.startswith(("float", "Float")):
            values = [_INFINITIES.get(v, v) if isinstance(v, str) else v for v in values]
        try:
            data[name] = pd.Series(values, dtype=dtype)
        except (TypeError, ValueError) as exc:
            raise BriefingError(f"column {name!r} doesn't hold {dtype} values: {exc}") from exc
    return pd.DataFrame(data)


# ── charts ────────────────────────────────────────────────────────────────────


def _plotly_json(figure: t.Any) -> t.Any:
    import plotly.io as pio

    return json.loads(pio.to_json(figure, validate=False))


def _template_name(figure: t.Any) -> str | None:
    """The name of *figure*'s template among Plotly's registered ones (``""``: the default)."""
    import plotly.io as pio

    if pio.templates.default and figure.layout.template == pio.templates[pio.templates.default]:
        return ""
    return next((name for name in pio.templates if figure.layout.template == pio.templates[name]), None)


def encode_figure(figure: object) -> dict[str, t.Any] | None:
    """``{"plotly": …}`` or ``{"vega-lite": …}`` for *figure*, or ``None``: kept by reference.

    A Plotly figure leaves out its template when it is Plotly's default one, and names it
    when it is another registered one. Either is written only when building it again gives
    the same chart (Plotly may order the keys of its JSON differently).
    """
    module = type(figure).__module__.split(".")[0]
    try:
        if module == "plotly" and type(figure).__name__ == "Figure":
            spec = _plotly_json(figure)
            template = _template_name(figure)
            if template is not None:
                spec.setdefault("layout", {}).pop("template", None)
                if template:
                    spec["layout"]["template"] = template
            same = _plotly_json(decode_figure({"plotly": spec})) == _plotly_json(figure)
            return {"plotly": spec} if same else None
        if module == "altair":
            vega = figure.to_dict()  # type: ignore[attr-defined]
            return {"vega-lite": vega} if decode_figure({"vega-lite": vega}).to_dict() == vega else None
    except Exception:  # noqa: BLE001 — any figure the library can't write and read back stays a reference
        return None
    return None


_ALTAIR_CLASSES = (
    ("layer", "LayerChart"),
    ("hconcat", "HConcatChart"),
    ("vconcat", "VConcatChart"),
    ("concat", "ConcatChart"),
    ("facet", "FacetChart"),
    ("repeat", "RepeatChart"),
)


def decode_figure(spec: dict[str, t.Any]) -> t.Any:
    """A Plotly figure from ``{"plotly": …}``, or an Altair chart from ``{"vega-lite": …}``."""
    if "plotly" in spec:
        try:
            import plotly.graph_objects as go
        except ImportError as exc:
            raise BriefingError('a {"plotly": …} chart needs plotly: pip install plotly') from exc
        if not isinstance(spec["plotly"], dict):
            raise BriefingError('"plotly" must be a Plotly figure\'s JSON: {"data": [...], "layout": {...}}.')
        try:
            return go.Figure(spec["plotly"])
        except ValueError as exc:
            raise BriefingError(f"Plotly can't read this figure: {_first_line(exc)}") from exc
    try:
        import altair as alt
    except ImportError as exc:
        raise BriefingError('a {"vega-lite": …} chart needs altair: pip install "briefing[altair]"') from exc
    vega = spec["vega-lite"]
    if not isinstance(vega, dict):
        raise BriefingError('"vega-lite" must be a Vega-Lite specification (an object).')
    kind = next((cls for key, cls in _ALTAIR_CLASSES if key in vega), "Chart")
    try:
        return getattr(alt, kind).from_dict(vega)
    except Exception as exc:  # noqa: BLE001 — Altair's schema errors have no common base we can name
        raise BriefingError(f"Altair can't read this Vega-Lite specification: {_first_line(exc)}") from exc


def _first_line(exc: BaseException) -> str:
    text = str(exc).strip()
    first = text.splitlines()[0] if text else type(exc).__name__
    return first if len(first) <= 300 else first[:297] + "..."


# ── images ────────────────────────────────────────────────────────────────────


def encode_image(data: object) -> str | None:
    """Image bytes as a ``data:`` URI, or ``None`` for anything else."""
    if not isinstance(data, bytes):
        return None
    mime = _image_type(data) or "application/octet-stream"
    return f"data:{mime};base64,{base64.b64encode(data).decode('ascii')}"


def decode_image(uri: str) -> bytes:
    """The bytes of a ``data:`` URI (base64 or percent-encoded)."""
    head, comma, body = uri.partition(",")
    if not comma:
        raise BriefingError("an image data: URI needs a comma before its data: data:image/png;base64,...")
    if head.endswith(";base64"):
        try:
            return base64.b64decode(body, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise BriefingError("the image data: URI isn't valid base64.") from exc
    return urllib.parse.unquote_to_bytes(body)
