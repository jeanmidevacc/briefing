"""DataCompare's numbers (#17): each column's statistics in each dataset, and how far apart they are.

Everything the block shows is computed here, in Python; the page gets these statistics,
never the rows, so a ten-million-row dataset makes as small a report as a thousand-row one.

- A column's **kind** is ``"numeric"``, ``"datetime"`` or ``"categorical"`` (booleans and
  text). When the datasets disagree, the column is compared as categories (its values as text).
- Numbers and dates are counted on **bins shared** by every dataset, so their bars line up;
  categories on their most frequent values across the datasets, plus an "other".
- The **distance** of a dataset from the reference (the first one) compares those two
  distributions, as proportions: Jensen–Shannon unless the block names another measure or
  passes its own function.
- **Non-uniformity** is 1 minus the normalised entropy of a dataset's distribution: 0 when
  its values spread evenly, 1 when they all fall in one bin or value.
"""
from __future__ import annotations

import math
import typing as t
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

from briefing._error import BriefingError

if t.TYPE_CHECKING:
    import numpy as np
    import pandas as pd

#: A distance between two distributions over the same bins: the reference's proportions, then another's.
Measure = Callable[[t.Any, t.Any], float]

#: Categories kept for the distance and the page: the most frequent across the datasets; the rest is "other".
TOP_VALUES = 50

#: Above this many distinct values, categories are drawn as a cumulative curve instead of bars.
CUMULATIVE_ABOVE = 20

#: Points kept on a cumulative curve.
CURVE_POINTS = 100

#: PSI smooths empty bins to this proportion, as is usual, so its logarithm stays finite.
_PSI_FLOOR = 1e-4


# ── the measures ──────────────────────────────────────────────────────────────


def jensen_shannon(p: np.ndarray, q: np.ndarray) -> float:
    """The Jensen–Shannon distance, in base 2: 0 for the same distribution, 1 for nothing in common."""
    import numpy as np

    m = (p + q) / 2

    def kl(a: np.ndarray) -> float:
        mask = a > 0
        return float(np.sum(a[mask] * np.log2(a[mask] / m[mask])))

    return math.sqrt(min(1.0, max(0.0, (kl(p) + kl(q)) / 2)))


def hellinger(p: np.ndarray, q: np.ndarray) -> float:
    """The Hellinger distance: 0 to 1."""
    import numpy as np

    return math.sqrt(max(0.0, 1.0 - float(np.sum(np.sqrt(p * q)))))


def total_variation(p: np.ndarray, q: np.ndarray) -> float:
    """The total variation distance: half the sum of the gaps, 0 to 1."""
    import numpy as np

    return float(np.sum(np.abs(p - q))) / 2


def psi(p: np.ndarray, q: np.ndarray) -> float:
    """The population stability index, from 0 with no upper bound; empty bins count as 0.01%."""
    import numpy as np

    a, b = np.maximum(p, _PSI_FLOOR), np.maximum(q, _PSI_FLOOR)
    return float(np.sum((b - a) * np.log(b / a)))


#: The measures a DataCompare names, each with its default "drifted" threshold.
MEASURES: dict[str, tuple[Measure, float]] = {
    "jensen_shannon": (jensen_shannon, 0.10),
    "hellinger": (hellinger, 0.10),
    "total_variation": (total_variation, 0.10),
    "psi": (psi, 0.20),
}

#: What the page calls each measure.
MEASURE_TITLES = {
    "jensen_shannon": "Jensen–Shannon",
    "hellinger": "Hellinger",
    "total_variation": "total variation",
    "psi": "PSI",
}


# ── one column ────────────────────────────────────────────────────────────────


@dataclass
class Side:
    """One column in one dataset: its counts and statistics, and its distribution on the shared bins."""

    dtype: str
    rows: int
    missing: int
    zeros: int | None = None  # numbers only
    stats: dict[str, t.Any] = field(default_factory=dict)  # mean, std… (numbers), first, last (dates), distinct, top…
    counts: list[int] = field(default_factory=list)  # on the column's shared bins or values
    deciles: list[float] | None = None  # numbers only
    curve: list[tuple[int, float]] | None = None  # categories: (rank, share of the values the top *rank* cover)
    nonuniformity: float | None = None
    distance: float | None = None  # from the reference; None for the reference itself

    @property
    def values(self) -> int:
        """How many values aren't missing."""
        return self.rows - self.missing


@dataclass
class Column:
    """One column across the datasets: ``sides[k]`` is ``None`` where dataset *k* doesn't have it."""

    name: str
    kind: str  # "numeric", "datetime" or "categorical"
    sides: list[Side | None]
    type_differs: bool = False
    edges: list[float] = field(default_factory=list)  # numbers and dates (epoch ms): bins + 1 edges
    labels: list[str] = field(default_factory=list)  # categories: the values counted, then "other" if any
    other: bool = False  # whether the last label is the rest of the values

    @property
    def present(self) -> list[bool]:
        return [side is not None for side in self.sides]

    def largest(self, what: str) -> float | None:
        """The largest of *what* (``"missing"``, ``"zeros"``, ``"nonuniformity"``, ``"distance"``) across datasets."""
        found = [v for side in self.sides if side is not None and (v := _share(side, what)) is not None]
        return max(found) if found else None


def _share(side: Side, what: str) -> float | None:
    if what == "missing":
        return side.missing / side.rows if side.rows else None
    if what == "zeros":
        return side.zeros / side.rows if side.zeros is not None and side.rows else None
    value: float | None = getattr(side, what)
    return value


def kind_of(series: pd.Series) -> str:
    """``"numeric"``, ``"datetime"`` or ``"categorical"``: how a column is compared."""
    import pandas as pd

    if pd.api.types.is_bool_dtype(series):
        return "categorical"
    if pd.api.types.is_numeric_dtype(series):
        return "numeric"
    if pd.api.types.is_datetime64_any_dtype(series):
        return "datetime"
    return "categorical"


def _nonuniformity(counts: Sequence[int]) -> float | None:
    total = sum(counts)
    if not total:
        return None
    used = [c for c in counts if c]
    if len(counts) < 2 or len(used) < 2:
        return 1.0
    entropy = -sum(c / total * math.log(c / total) for c in used)
    return max(0.0, min(1.0, 1 - entropy / math.log(len(counts))))


def _finite(series: pd.Series) -> np.ndarray:
    import numpy as np

    values = series.dropna().to_numpy(dtype="float64", na_value=np.nan)
    finite: np.ndarray = values[np.isfinite(values)]
    return finite


def _epoch_ns(series: pd.Series) -> np.ndarray:
    stamps = series.dropna()
    if getattr(stamps.dt, "tz", None) is not None:
        stamps = stamps.dt.tz_convert("UTC").dt.tz_localize(None)
    return stamps.astype("datetime64[ns]").astype("int64").to_numpy()


def _histograms(arrays: list[np.ndarray | None], bins: int) -> tuple[list[float], list[list[int]]]:
    """Counts of each array on *bins* equal bins over all their values, and the bins' edges."""
    import numpy as np

    present = [a for a in arrays if a is not None and a.size]
    if not present:
        return [], [[] for _ in arrays]
    low = min(float(a.min()) for a in present)
    high = max(float(a.max()) for a in present)
    if low == high:
        edges = [low, high]
        return edges, [[int(a.size)] if a is not None else [] for a in arrays]
    # Halve everything when the span overflows a float (-1e308 … 1e308), as DataProfile does.
    scale = 1.0 if math.isfinite(high - low) else 0.5
    out: list[list[int]] = []
    for a in arrays:
        if a is None:
            out.append([])
            continue
        # Each value's bin by hand: np.histogram refuses a range too narrow for its bins (0 … 5e-324).
        position = (a * scale - low * scale) / (high * scale - low * scale)
        index = np.minimum((position * bins).astype("int64"), bins - 1)
        out.append([int(c) for c in np.bincount(index, minlength=bins)])
    edges = [low + (high * scale - low * scale) / scale * k / bins for k in range(bins + 1)]
    edges[-1] = high
    return edges, out


def _number_side(series: pd.Series, values: np.ndarray) -> Side:
    import numpy as np

    side = Side(dtype=str(series.dtype), rows=len(series), missing=int(series.isna().sum()))
    side.zeros = int((series == 0).sum())
    infinite = int(series.dropna().size - values.size)
    if values.size:
        with np.errstate(over="ignore", invalid="ignore"):  # near ±1e308, a mean or std overflows: shown as inf
            side.stats = {
                "mean": float(values.mean()), "std": float(values.std(ddof=1)) if values.size > 1 else None,
                "min": float(values.min()), "median": float(np.median(values)), "max": float(values.max()),
            }
            side.deciles = [float(v) for v in np.quantile(values, [k / 10 for k in range(1, 10)])]
    if infinite:
        side.stats["infinite"] = infinite
    return side


def _date_side(series: pd.Series, stamps: np.ndarray) -> Side:
    side = Side(dtype=str(series.dtype), rows=len(series), missing=int(series.isna().sum()))
    if stamps.size:
        side.stats = {"first": int(stamps.min()) // 1_000_000, "last": int(stamps.max()) // 1_000_000}  # epoch ms
    return side


def _text(value: t.Any) -> str:
    return str(value)


def _category_counts(series: pd.Series) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value, n in series.dropna().map(_text).value_counts(sort=False).items():
        counts[str(value)] = counts.get(str(value), 0) + int(n)
    return counts


def _curve(counts: dict[str, int]) -> list[tuple[int, float]]:
    ordered = sorted(counts.values(), reverse=True)
    total = sum(ordered)
    if not total:
        return []
    ranks = sorted({max(1, round(len(ordered) * k / CURVE_POINTS)) for k in range(1, CURVE_POINTS + 1)} | {1})
    running, out, at = 0, [], 0
    for rank in ranks:
        while at < rank:
            running += ordered[at]
            at += 1
        out.append((rank, running / total))
    return out


def compare_column(name: str, frames: Sequence[pd.DataFrame], bins: int) -> Column:
    """The statistics of column *name* in each frame that has it, on shared bins or values."""
    series: list[pd.Series | None] = [frame[name] if name in frame.columns else None for frame in frames]
    kinds = {kind_of(s) for s in series if s is not None}
    differs = len(kinds) > 1
    kind = "categorical" if differs else kinds.pop()

    if kind == "numeric":
        arrays = [_finite(s) if s is not None else None for s in series]
        edges, counts = _histograms(arrays, bins)
        sides: list[Side | None] = [
            _number_side(s, a) if s is not None and a is not None else None for s, a in zip(series, arrays, strict=True)
        ]
        column = Column(name, kind, sides, edges=edges)
    elif kind == "datetime":
        stamps = [_epoch_ns(s) if s is not None else None for s in series]
        edges_ns, counts = _histograms([a.astype("float64") if a is not None else None for a in stamps], bins)
        sides = [
            _date_side(s, a) if s is not None and a is not None else None for s, a in zip(series, stamps, strict=True)
        ]
        column = Column(name, kind, sides, edges=[e / 1_000_000 for e in edges_ns])
    else:
        tallies = [_category_counts(s) if s is not None else None for s in series]
        shares: dict[str, float] = {}
        for tally in tallies:
            total = sum(tally.values()) if tally else 0
            for value, n in (tally or {}).items():
                shares[value] = shares.get(value, 0.0) + n / total
        labels = sorted(shares, key=lambda v: (-shares[v], v))[:TOP_VALUES]
        kept = set(labels)
        other = any(v not in kept for v in shares)
        counts = []
        sides = []
        for s, tally in zip(series, tallies, strict=True):
            if s is None or tally is None:
                counts.append([])
                sides.append(None)
                continue
            row = [tally.get(v, 0) for v in labels]
            if other:
                row.append(sum(n for v, n in tally.items() if v not in kept))
            counts.append(row)
            side = Side(dtype=str(s.dtype), rows=len(s), missing=int(s.isna().sum()))
            values = sum(tally.values())
            top = min(tally.items(), key=lambda item: (-item[1], item[0])) if tally else None  # ties: first by name
            side.stats = {"distinct": len(tally)}
            if top is not None:
                side.stats.update(top=top[0], top_share=top[1] / values)
            side.nonuniformity = _nonuniformity(list(tally.values())) if tally else None
            if max(len(t_) for t_ in tallies if t_ is not None) > CUMULATIVE_ABOVE:
                side.curve = _curve(tally)
            sides.append(side)
        column = Column(name, kind, sides, labels=labels + (["other"] if other else []), other=other)

    for each, row in zip(column.sides, counts, strict=True):
        if each is not None:
            each.counts = row
            if kind != "categorical":
                each.nonuniformity = _nonuniformity(row)
    column.type_differs = differs
    return column


def measure_distances(column: Column, measure: Measure, title: str) -> None:
    """Set each dataset's distance from the reference on *column*, with *measure*."""
    import numpy as np

    reference = column.sides[0]
    if reference is None or not sum(reference.counts):
        return
    p = np.asarray(reference.counts, dtype="float64") / sum(reference.counts)
    for side in column.sides[1:]:
        if side is None or not sum(side.counts):
            continue
        q = np.asarray(side.counts, dtype="float64") / sum(side.counts)
        try:
            value = float(measure(p, q))
        except Exception as exc:  # the user's own function: say where it failed
            raise BriefingError(f"DataCompare: the distance {title!r} failed on column {column.name!r}: {exc}") from exc
        if not math.isfinite(value):
            raise BriefingError(
                f"DataCompare: the distance {title!r} gave {value} on column {column.name!r}; "
                "it must return a finite number."
            )
        side.distance = value


__all__ = [
    "MEASURES",
    "MEASURE_TITLES",
    "Column",
    "Side",
    "compare_column",
    "hellinger",
    "jensen_shannon",
    "kind_of",
    "measure_distances",
    "psi",
    "total_variation",
]
