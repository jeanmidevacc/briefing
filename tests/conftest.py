"""Shared pytest fixtures for the briefing test suite."""
from __future__ import annotations

import pandas as pd
import pytest

# ── DataFrame fixtures ────────────────────────────────────────────────────────


@pytest.fixture
def df_mixed() -> pd.DataFrame:
    """DataFrame covering all common dtype categories, with some nulls."""
    import numpy as np

    rng = np.random.default_rng(42)
    n = 200
    categories = ["alpha", "beta", "gamma", "delta"]

    df = pd.DataFrame(
        {
            "id": range(n),
            "numeric_int": rng.integers(0, 1000, n),
            "numeric_float": rng.uniform(0.0, 100.0, n),
            "category": pd.Categorical([categories[i % 4] for i in range(n)]),
            "text": [f"item_{i}" for i in range(n)],
            "flag": [bool(i % 2) for i in range(n)],
            "nullable_int": [None if i % 10 == 0 else int(i) for i in range(n)],
            "nullable_float": [None if i % 7 == 0 else float(i) * 1.5 for i in range(n)],
            "timestamp": pd.date_range("2024-01-01", periods=n, freq="D"),
        }
    )
    return df


@pytest.fixture
def df_empty() -> pd.DataFrame:
    """Empty DataFrame — zero rows, zero columns."""
    return pd.DataFrame()


@pytest.fixture
def df_single_row() -> pd.DataFrame:
    """DataFrame with exactly one row."""
    return pd.DataFrame({"a": [1], "b": ["hello"], "c": [3.14]})


@pytest.fixture
def df_all_null() -> pd.DataFrame:
    """DataFrame where every value is null."""
    import numpy as np

    return pd.DataFrame(
        {
            "x": [np.nan, np.nan, np.nan],
            "y": [None, None, None],
        }
    )


@pytest.fixture
def df_large() -> pd.DataFrame:
    """DataFrame with 15 000 rows — triggers sampling / truncation warnings."""
    import numpy as np

    rng = np.random.default_rng(0)
    return pd.DataFrame(
        {
            "a": rng.integers(0, 100, 15_000),
            "b": rng.uniform(0, 1, 15_000),
            "c": [f"cat_{i % 5}" for i in range(15_000)],
        }
    )


@pytest.fixture
def df_constant() -> pd.DataFrame:
    """DataFrame where every column has only one unique value (zero-variance)."""
    return pd.DataFrame({"x": [42] * 50, "y": ["same"] * 50})


# ── calendar fixtures (lab.CalendarHeatmap, #19) ──────────────────────────────


@pytest.fixture
def df_pipeline_log() -> pd.DataFrame:
    """A daily pipeline log from mid-November 2025 to mid-February 2026 (across a year boundary).

    One row per run: most days run once, some twice; a few days have no run at all
    (gaps) and some runs failed (``rows == 0``).
    """
    import numpy as np

    rng = np.random.default_rng(19)
    days = pd.date_range("2025-11-17", "2026-02-15", freq="D")
    gaps = {pd.Timestamp("2025-12-25"), pd.Timestamp("2026-01-01"), pd.Timestamp("2026-01-17")}
    rows = []
    for day in days:
        if day in gaps:
            continue
        for run in range(2 if day.day % 7 == 0 else 1):
            failed = day.day in (3, 14) and run == 0
            rows.append({"run_at": day + pd.Timedelta(hours=6 + run * 8), "team": "ingest" if run == 0 else "export",
                         "rows": 0 if failed else int(rng.integers(800, 1200))})
    return pd.DataFrame(rows)


@pytest.fixture
def df_signed() -> pd.DataFrame:
    """Daily values that go negative and positive (a balance), 60 days from 2026-03-01."""
    import numpy as np

    rng = np.random.default_rng(5)
    days = pd.date_range("2026-03-01", periods=60, freq="D")
    return pd.DataFrame({"day": days, "balance": np.round(rng.normal(0, 40, len(days)), 1)})


@pytest.fixture
def df_events() -> pd.DataFrame:
    """Events for the pipeline log: a multi-day freeze, a migration, and a single-day incident."""
    return pd.DataFrame({
        "start": pd.to_datetime(["2025-12-22", "2026-01-26", "2026-02-03"]),
        "end": pd.to_datetime(pd.Series(["2026-01-02", "2026-01-28", None])),
        "label": ["Holiday freeze", "Migration", "Incident"],
    })
