"""bf.datasets: sample data generated from a seed, the same everywhere (#46)."""
from __future__ import annotations

import base64
import hashlib
import sys
import typing as t

import pandas as pd
import pytest

import briefing as bf
from tests.contract import RULES, check_user_text_escaped, parse_report

#: sha256 (first 16 hex digits) of each table as CSV, at its default size and seed 0. A change here
#: means the same name, size and seed no longer give the same rows: users' examples would change.
CHECKSUMS = {
    ("collection_log", "collection_log"): "6710ad8cf4dab10a",
    ("corpus", "corpus"): "d0b0f87a04e214c0",
    ("embeddings", "embeddings"): "83a1d2e6c9be1ef1",
    ("recsys", "history"): "95f75bd5f3835abc",
    ("recsys", "recs"): "392c8fc20b66d236",
    ("recsys", "catalog"): "ff9cefafb1fd04d4",
    ("sales", "sales"): "52727edc9d6ccd2a",
    ("train_test", "train"): "7ac0cb5e5c4f61ec",
    ("train_test", "test"): "32af0c98ef052f88",
}


def _tables(name: str, **kwargs: t.Any) -> dict[str, t.Any]:
    data = bf.datasets.load(name, **kwargs)
    return dict(data) if isinstance(data, bf.datasets.Tables) else {name: data}


def _digest(frame: pd.DataFrame) -> str:
    return hashlib.sha256(frame.to_csv(index=False).encode()).hexdigest()[:16]


def test_names() -> None:
    assert bf.datasets.names() == ["collection_log", "corpus", "embeddings", "recsys", "sales", "train_test"]
    assert {name for name, _ in CHECKSUMS} == set(bf.datasets.names())


@pytest.mark.parametrize("name", ["collection_log", "corpus", "embeddings", "recsys", "sales", "train_test"])
def test_the_same_name_size_and_seed_give_the_same_rows(name: str) -> None:
    tables = _tables(name)
    assert {(name, table) for table in tables} == {key for key in CHECKSUMS if key[0] == name}
    for table, frame in tables.items():
        assert _digest(frame) == CHECKSUMS[name, table], f"{name}.{table} changed"
    other = _tables(name, seed=1)
    assert any(_digest(frame) != _digest(other[table]) for table, frame in tables.items())


def _as_pandas(frame: t.Any) -> pd.DataFrame:
    df: pd.DataFrame = frame if isinstance(frame, pd.DataFrame) else frame.to_pandas()
    for column in df.columns:  # arrow hands list cells back as numpy arrays
        if df[column].map(lambda v: hasattr(v, "tolist") and not isinstance(v, str)).any():
            df[column] = df[column].map(lambda v: list(v.tolist()))
    return df


@pytest.mark.parametrize("engine", ["polars", "pyarrow"])
@pytest.mark.parametrize("name", ["collection_log", "corpus", "embeddings", "recsys", "sales", "train_test"])
def test_every_engine_gets_the_same_data(name: str, engine: str) -> None:
    pytest.importorskip(engine)
    expected = _tables(name, n=None)
    for table, frame in _tables(name, engine=engine).items():
        assert type(frame).__module__.split(".")[0] == engine
        got = _as_pandas(frame)
        pd.testing.assert_frame_equal(got, _as_pandas(expected[table]), check_dtype=False)


def test_missing_values_are_nulls_in_polars_and_pyarrow() -> None:
    pl = pytest.importorskip("polars")
    test = bf.datasets.load("train_test").test
    missing = int(test["income_k"].isna().sum())
    assert missing > 0
    polars_test = bf.datasets.load("train_test", engine="polars").test
    assert isinstance(polars_test, pl.DataFrame)
    assert polars_test["income_k"].null_count() == missing and polars_test["income_k"].is_nan().sum() == 0
    assert bf.datasets.load("train_test", engine="pyarrow").test["income_k"].null_count == missing


def test_n_sets_the_size() -> None:
    assert len(bf.datasets.load("sales", n=50)) == 50
    assert len(bf.datasets.load("embeddings", n=6)) == 6
    assert len(bf.datasets.load("corpus", n=2)) == 2
    split = bf.datasets.load("train_test", n=100)
    assert (len(split.train), len(split.test)) == (80, 20)
    rec = bf.datasets.load("recsys", n=3)
    assert rec.history["user_id"].nunique() == 3 and len(rec.catalog) == 96
    log = bf.datasets.load("collection_log", n=30)
    assert log["run_at"].dt.normalize().nunique() <= 30
    assert log["run_at"].max() < pd.Timestamp("2026-11-21") and log["run_at"].min() >= pd.Timestamp("2026-10-22")


def test_tables_reads_by_name_or_attribute() -> None:
    rec = bf.datasets.load("recsys")
    assert list(rec) == ["history", "recs", "catalog"] and len(rec) == 3
    assert rec.catalog is rec["catalog"]
    assert repr(rec) == f"Tables(history: {len(rec.history):,} rows, recs: 4,000 rows, catalog: 96 rows)"
    with pytest.raises(AttributeError, match="this dataset has no table 'ratings'; it has history, recs, catalog"):
        rec.ratings  # noqa: B018


# ── what each dataset is for ────────────────────────────────────────────────────


def test_sales() -> None:
    sales = bf.datasets.load("sales")
    assert sales["ordered_at"].is_monotonic_increasing and sales["ordered_at"].dt.year.unique().tolist() == [2025]
    expected = (sales["units"] * sales["unit_price"] * (1 - sales["discount"])).round(2)
    assert (sales["revenue"] - expected).abs().max() < 1e-9
    by_month = sales.groupby(sales["ordered_at"].dt.month).size()
    assert by_month[11] + by_month[12] > by_month[3] + by_month[4]  # busier at the end of the year
    assert set(sales["category"]) == {"Stationery", "Office", "Electronics"}
    assert sales["order_id"].is_unique


def test_collection_log_has_gaps_and_failures() -> None:
    log = bf.datasets.load("collection_log")
    days = log["run_at"].dt.normalize()
    assert days.nunique() < 120, "some days have no run"
    assert days.duplicated().any(), "some days run twice"
    failed = log[log["status"] == "failed"]
    assert len(failed) and (failed["rows"] == 0).all() and (log.loc[log["status"] == "ok", "rows"] > 0).all()
    assert log["run_at"].is_monotonic_increasing


def test_corpus_has_two_groups_with_their_own_words() -> None:
    corpus = bf.datasets.load("corpus")
    assert corpus["group"].value_counts().to_dict() == {"before": 200, "after": 200}
    words = {g: {w for ts in corpus.loc[corpus["group"] == g, "tokens"] for w in ts} for g in ("before", "after")}
    assert {"slow", "crash"} <= words["before"] - words["after"]
    assert {"fast", "search"} <= words["after"] - words["before"]
    assert {"checkout", "app"} <= words["before"] & words["after"]
    assert corpus.groupby("group")["rating"].mean()["after"] > corpus.groupby("group")["rating"].mean()["before"]
    first = corpus.iloc[0]
    assert all(token in first["text"].lower() for token in first["tokens"])


def test_train_test_drifts() -> None:
    split = bf.datasets.load("train_test")
    train, test = split.train, split.test
    assert list(train.columns) == list(test.columns)
    assert "trial" in set(test["plan"]) and "trial" not in set(train["plan"])
    assert test["age"].mean() > train["age"].mean() + 1
    assert test["income_k"].isna().mean() > train["income_k"].isna().mean()
    assert not set(train["customer_id"]) & set(test["customer_id"])


def test_recsys_recommends_only_what_was_not_watched() -> None:
    rec = bf.datasets.load("recsys")
    seen = set(zip(rec.history["user_id"], rec.history["item_id"], strict=True))
    assert not seen & set(zip(rec.recs["user_id"], rec.recs["item_id"], strict=True))
    per_list = rec.recs.groupby(["user_id", "model"])["rank"].apply(list)
    assert all(ranks == list(range(1, 11)) for ranks in per_list)
    assert set(rec.recs["model"]) == {"popularity", "personal"}
    assert set(rec.history["item_id"]) <= set(rec.catalog["item_id"])
    head, _, data = rec.catalog["thumbnail"].iloc[0].partition(",")
    assert head == "data:image/svg+xml;base64" and base64.b64decode(data).startswith(b"<svg")


def test_embeddings_are_six_clusters() -> None:
    points = bf.datasets.load("embeddings")
    assert points["cluster"].nunique() == 6
    centres = points.groupby("cluster")[["x", "y"]].mean()
    spread = points.groupby("cluster")[["x", "y"]].std().mean(axis=1)
    gaps = [((centres.iloc[i] - centres.iloc[j]) ** 2).sum() ** 0.5 for i in range(6) for j in range(i + 1, 6)]
    assert min(gaps) > spread.max(), "the clusters stand apart"


@pytest.mark.parametrize("name", ["collection_log", "corpus", "embeddings", "recsys", "sales", "train_test"])
def test_every_table_makes_a_report(name: str) -> None:
    for frame in _tables(name, n=None).values():
        soup = parse_report(bf.stringify(bf.Briefing(bf.DataTable(frame))))
        for check in RULES.values():
            if check is not check_user_text_escaped:  # it looks for a marker these tables don't carry
                check(soup)


# ── wrong arguments ─────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("args", "kwargs", "message"),
    [
        (("tips",), {},
         r"no dataset 'tips'\. Pass one of collection_log, corpus, embeddings, recsys, sales, train_test"),
        (("sales",), {"n": 0}, r"'sales' needs n= as a whole number of order lines, at least 1; got 0"),
        (("sales",), {"n": 2.5}, r"whole number"),
        (("sales",), {"n": True}, r"whole number"),
        (("embeddings",), {"n": 5}, r"at least 6"),
        (("sales",), {"seed": -1}, r"seed must be a whole number, 0 or more; got -1"),
        (("sales",), {"engine": "spark"}, r"engine must be one of pandas, polars, pyarrow; got 'spark'"),
    ],
)
def test_wrong_arguments_say_what_to_pass(args: tuple[t.Any, ...], kwargs: dict[str, t.Any], message: str) -> None:
    with pytest.raises(bf.BriefingError, match=message):
        bf.datasets.load(*args, **kwargs)


def test_a_missing_engine_says_how_to_get_it(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "polars", None)  # import polars now raises ImportError
    with pytest.raises(bf.BriefingError, match=r"needs polars, which briefing doesn't install: pip install polars"):
        bf.datasets.load("sales", engine="polars")
