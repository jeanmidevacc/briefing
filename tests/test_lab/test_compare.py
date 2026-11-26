"""DataCompare (#17): datasets compared column by column, statistics computed in Python."""
from __future__ import annotations

import datetime as dt
import json
import math
import typing as t

import numpy as np
import pandas as pd
import pytest

import briefing as bf
from briefing.lab import _compare
from tests.html_helpers import attr, find_one, parse

_A = pd.DataFrame({
    "age": [20, 30, 40, 50, 60, 0, None],
    "plan": ["basic", "pro", "basic", "pro", "basic", "team", None],
    "day": pd.to_datetime(pd.Series(["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04", None, "2026-01-05",
                                     "2026-01-06"])),
})
_B = pd.DataFrame({
    "age": [25, 35, 45, 55, 65, 75],
    "plan": ["pro", "pro", "pro", "basic", "trial", "trial"],
    "day": pd.to_datetime(["2026-01-03"] * 6),
    "new": [1, 2, 3, 4, 5, 6],
})


def _block(**kwargs: t.Any) -> bf.lab.DataCompare:
    return bf.lab.DataCompare({"train": _A, "test": _B}, **kwargs)


def _column(block: bf.lab.DataCompare, name: str) -> _compare.Column:
    return next(c for c in block.compared if c.name == name)


def _rows(block: bf.lab.DataCompare) -> t.Any:
    return parse(bf.stringify(bf.Briefing(block))).select(".bf-cmp__row")


# ── the measures ──────────────────────────────────────────────────────────────


@pytest.mark.parametrize("name", ["jensen_shannon", "hellinger", "total_variation", "psi"])
def test_a_distribution_is_at_distance_zero_from_itself(name: str) -> None:
    measure, _ = _compare.MEASURES[name]
    p = np.array([0.2, 0.3, 0.5])
    assert measure(p, p) == pytest.approx(0.0, abs=1e-12)


@pytest.mark.parametrize("name", ["jensen_shannon", "hellinger", "total_variation"])
def test_bounded_measures_reach_one_for_nothing_in_common(name: str) -> None:
    measure, _ = _compare.MEASURES[name]
    assert measure(np.array([1.0, 0.0]), np.array([0.0, 1.0])) == pytest.approx(1.0)


def test_the_measures_agree_with_their_formulas() -> None:
    p, q = np.array([0.5, 0.5]), np.array([0.9, 0.1])
    m = (p + q) / 2
    js = math.sqrt((np.sum(p * np.log2(p / m)) + np.sum(q * np.log2(q / m))) / 2)
    assert _compare.jensen_shannon(p, q) == pytest.approx(js)
    assert _compare.hellinger(p, q) == pytest.approx(math.sqrt(1 - (math.sqrt(0.45) + math.sqrt(0.05))))
    assert _compare.total_variation(p, q) == pytest.approx(0.4)
    assert _compare.psi(p, q) == pytest.approx(0.4 * math.log(0.9 / 0.5) + (-0.4) * math.log(0.1 / 0.5))
    assert _compare.jensen_shannon(p, q) == pytest.approx(_compare.jensen_shannon(q, p))  # symmetric


def test_psi_stays_finite_when_a_bin_is_empty() -> None:
    assert math.isfinite(_compare.psi(np.array([1.0, 0.0]), np.array([0.5, 0.5])))


# ── statistics ────────────────────────────────────────────────────────────────


def test_numbers_are_counted_on_bins_both_datasets_share() -> None:
    age = _column(_block(bins=5), "age")
    assert age.kind == "numeric"
    assert age.edges[0] == 0 and age.edges[-1] == 75 and len(age.edges) == 6
    train, test = age.sides
    assert train is not None and test is not None
    assert sum(train.counts) == 6 and sum(test.counts) == 6  # the missing age isn't counted
    assert train.missing == 1 and train.zeros == 1 and test.zeros == 0
    assert train.stats["median"] == 35 and test.stats["max"] == 75
    assert train.deciles is not None and len(train.deciles) == 9


def test_categories_share_their_values_and_top_one() -> None:
    plan = _column(_block(), "plan")
    assert plan.kind == "categorical"
    assert set(plan.labels) == {"basic", "pro", "team", "trial"} and not plan.other
    train, test = plan.sides
    assert train is not None and test is not None
    assert train.stats == {"distinct": 3, "top": "basic", "top_share": 0.5}
    assert test.stats["top"] == "pro"
    assert train.counts[plan.labels.index("trial")] == 0


def test_categories_beyond_the_top_go_in_other() -> None:
    a = pd.DataFrame({"v": [f"v{i}" for i in range(80)]})
    column = bf.lab.DataCompare([a, a]).compared[0]
    assert len(column.labels) == _compare.TOP_VALUES + 1 and column.labels[-1] == "other" and column.other
    side = column.sides[0]
    assert side is not None and sum(side.counts) == 80
    assert side.curve is not None and side.curve[-1] == (80, 1.0)  # more than 20 values: a cumulative curve


def test_dates_are_counted_on_shared_bins_in_epoch_milliseconds() -> None:
    day = _column(_block(), "day")
    assert day.kind == "datetime"
    assert day.edges[0] == pd.Timestamp("2026-01-01").value // 1_000_000
    train = day.sides[0]
    assert train is not None and train.stats["last"] == pd.Timestamp("2026-01-06").value // 1_000_000


def test_time_zones_are_compared_in_utc() -> None:
    utc = pd.DataFrame({"t": pd.to_datetime(["2026-01-01 12:00"]).tz_localize("UTC")})
    paris = pd.DataFrame({"t": pd.to_datetime(["2026-01-01 13:00"]).tz_localize("Europe/Paris")})
    column = bf.lab.DataCompare([utc, paris]).compared[0]
    assert column.edges[0] == column.edges[-1]
    assert column.sides[1] is not None and column.sides[1].distance == 0


def test_a_column_whose_type_differs_is_compared_as_categories() -> None:
    column = bf.lab.DataCompare([pd.DataFrame({"x": [1, 2]}), pd.DataFrame({"x": ["1", "two"]})]).compared[0]
    assert column.kind == "categorical" and column.type_differs
    assert column.labels == ["1", "2", "two"]


def test_nonuniformity_runs_from_spread_evenly_to_all_in_one() -> None:
    even = pd.DataFrame({"v": list("abcd")})
    one = pd.DataFrame({"v": list("aaaa")})
    column = bf.lab.DataCompare([even, one]).compared[0]
    assert [s.nonuniformity for s in column.sides if s is not None] == [pytest.approx(0.0), 1.0]


def test_measures_are_rounded_so_every_python_prints_the_same() -> None:
    # Regression: 1 - entropy / log(n) was 2.9e-15 on Python 3.11 and 0 on 3.12, whose sum() compensates.
    texts = pd.DataFrame({"v": [f"item_{i}" for i in range(200)]})
    column = bf.lab.DataCompare([texts, texts.iloc[::-1]]).compared[0]
    assert [s.nonuniformity for s in column.sides if s is not None] == [0.0, 0.0]
    assert _compare._nonuniformity([1, 1, 1]) == 0.0


def test_a_range_too_narrow_for_its_bins_still_counts() -> None:
    # Regression: np.histogram refuses 20 bins between 0 and the smallest float (found by Hypothesis).
    tiny = pd.DataFrame({"v": [0.0, 5e-324]})
    column = bf.lab.DataCompare([tiny, tiny]).compared[0]
    assert column.sides[0] is not None and sum(column.sides[0].counts) == 2


def test_a_range_wider_than_a_float_still_counts() -> None:
    huge = pd.DataFrame({"v": [-1e308, 1e308]})
    column = bf.lab.DataCompare([huge, huge]).compared[0]
    assert column.sides[0] is not None and column.sides[0].counts[0] == 1 and column.sides[0].counts[-1] == 1


def test_empty_and_all_missing_columns_have_no_distance() -> None:
    empty = pd.DataFrame({"v": pd.Series([], dtype="float64")})
    missing = pd.DataFrame({"v": [None, None]}, dtype="float64")
    for a, b in ((empty, empty), (missing, _A.rename(columns={"age": "v"})), (empty, missing)):
        column = bf.lab.DataCompare([a, b]).compared[0]
        assert all(side is None or side.distance is None for side in column.sides)
    bf.stringify(bf.Briefing(bf.lab.DataCompare([empty, missing])))


# ── distances and badges ──────────────────────────────────────────────────────


def test_each_dataset_is_measured_from_the_first() -> None:
    block = bf.lab.DataCompare({"a": _A, "b": _A, "c": _B})
    age = _column(block, "age")
    assert [s.distance for s in age.sides if s is not None] == [None, 0.0, pytest.approx(age.largest("distance"))]


def test_a_function_of_your_own_measures_and_names_the_distance() -> None:
    seen: list[tuple[t.Any, t.Any]] = []

    def biggest_gap(p: t.Any, q: t.Any) -> float:
        seen.append((p, q))
        return float(np.max(np.abs(p - q)))

    block = _block(distance=biggest_gap, distance_threshold=0.3)
    assert block.measure_title == "biggest_gap" and block.threshold == 0.3
    p, q = seen[0]
    assert isinstance(p, np.ndarray) and p.sum() == pytest.approx(1.0) and q.sum() == pytest.approx(1.0)
    html = bf.stringify(bf.Briefing(block))
    assert "Distance from train: biggest_gap, drifted above 0.3" in find_one(parse(html), ".bf-cmp__measure").get_text()


def test_a_function_without_a_threshold_marks_nothing_as_drifted() -> None:
    block = _block(distance=lambda p, q: 1.0, distance_name="always far")
    assert block.threshold is None and block.measure_title == "always far"
    soup = parse(bf.stringify(bf.Briefing(block)))
    assert soup.select(".bf-cmp__badge--drift") == []
    assert "drifted above" not in find_one(soup, ".bf-cmp__measure").get_text()


@pytest.mark.parametrize("result", [math.nan, math.inf])
def test_a_function_must_return_a_finite_number(result: float) -> None:
    with pytest.raises(bf.BriefingError, match="finite number"):
        _block(distance=lambda p, q: result)


def test_a_failing_function_names_the_column() -> None:
    def broken(p: t.Any, q: t.Any) -> float:
        raise ZeroDivisionError("oops")

    with pytest.raises(bf.BriefingError, match="'broken' failed on column 'age': oops"):
        _block(distance=broken)


def test_psi_has_its_own_threshold() -> None:
    assert _block(distance="psi").threshold == 0.20
    assert _block().threshold == 0.10
    assert _block(distance="psi", distance_threshold=0.5).threshold == 0.5


def test_badges_flag_columns_only_some_have_types_that_differ_and_drift() -> None:
    other = _B.assign(plan=[1, 2, 3, 4, 5, 6])
    soup = parse(bf.stringify(bf.Briefing(bf.lab.DataCompare({"train": _A, "test": other}))))
    badges = {attr(row, "data-name"): [b.get_text() for b in row.select(".bf-cmp__badge")]
              for row in soup.select(".bf-cmp__row")}
    assert badges["new"] == ["only in test"]
    assert badges["plan"][0] == "type differs" and badges["plan"][1].startswith("drifted · ")
    assert badges["day"][0].startswith("drifted")


def test_shares_above_their_thresholds_are_highlighted() -> None:
    row = next(r for r in _rows(_block(missing_threshold=0.1, zero_threshold=0.1)) if attr(r, "data-name") == "age")
    highs = [el.get_text() for el in row.select(".bf-cmp__high")]
    assert "14.3% (1)" in highs  # missing, in train
    assert len(highs) >= 2  # zeros too
    calm = next(r for r in _rows(_block(missing_threshold=0.5, zero_threshold=0.5)) if attr(r, "data-name") == "age")
    assert not any("%" in el.get_text() for el in calm.select(".bf-cmp__high"))


# ── the page ──────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(("sort", "first"), [("name", "age"), ("distance", "new"), ("missing", "age")])
def test_rows_follow_the_sort(sort: str, first: str) -> None:
    rows = _rows(_block(sort=sort))
    names = [attr(r, "data-name") for r in rows]
    if sort == "distance":  # the column only in test has no distance: it comes last
        assert names[-1] == "new"
        distances = [float(attr(r, "data-distance")) for r in rows[:-1]]
        assert distances == sorted(distances, reverse=True)
    else:
        assert names[0] == first


def test_columns_picks_and_orders_them() -> None:
    assert [attr(r, "data-name") for r in _rows(_block(columns=["plan", "age"]))] == ["age", "plan"]  # sorted by name
    block = _block(columns=["plan", "age"], sort="distance")
    assert {c.name for c in block.compared} == {"plan", "age"}


def test_each_row_carries_its_sort_keys() -> None:
    row = next(r for r in _rows(_block()) if attr(r, "data-name") == "age")
    assert attr(row, "data-kind") == "numeric"
    assert float(attr(row, "data-missing")) == pytest.approx(1 / 7, rel=1e-5)
    assert float(attr(row, "data-zeros")) == pytest.approx(1 / 7, rel=1e-5)
    assert 0 <= float(attr(row, "data-non-uniformity")) <= 1
    assert float(attr(row, "data-distance")) > 0


def test_a_dataset_without_the_column_says_so() -> None:
    row = next(r for r in _rows(_block()) if attr(r, "data-name") == "new")
    absent = find_one(row, ".bf-cmp__absent")
    assert "train" in absent.get_text() and "not in this dataset" in absent.get_text()


def test_the_legend_names_each_dataset_with_its_rows_and_colour() -> None:
    soup = parse(bf.stringify(bf.Briefing(bf.lab.DataCompare({"a": _A, "b": _B, "c": _B}))))
    legend = [el.get_text(" ", strip=True) for el in soup.select(".bf-cmp__dataset")]
    assert legend == ["a 7 rows", "b 6 rows", "c 6 rows"]
    swatches = [attr(el, "style") for el in soup.select(".bf-cmp__legend .bf-cmp__swatch")]
    assert swatches == ["background:var(--bf-cmp-0)", "background:var(--bf-cmp-1)", "background:var(--bf-cmp-2)"]


def test_a_list_names_the_datasets_by_position() -> None:
    assert list(bf.lab.DataCompare([_A, _B]).datasets) == ["1", "2"]


def test_polars_and_pyarrow_frames_are_accepted() -> None:
    pl = pytest.importorskip("polars")
    pa = pytest.importorskip("pyarrow")
    block = bf.lab.DataCompare({"pl": pl.from_pandas(_B), "pa": pa.Table.from_pandas(_B)})
    assert all(s is not None and s.distance in (None, 0.0) for c in block.compared for s in c.sides)


# ── checks ────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(("kwargs", "message"), [
    ({"datasets": {"only": _A}}, "two or more datasets"),
    ({"datasets": _A}, "as a dict"),
    ({"datasets": {"": _A, "b": _B}}, "must not be empty"),
    ({"datasets": {1: _A, "1": _B}}, "distinct"),
    ({"sort": "size"}, "'sort' is one of"),
    ({"missing_threshold": 1.5}, "'missing_threshold' must be a share"),
    ({"zero_threshold": -0.1}, "'zero_threshold' must be a share"),
    ({"bins": 1}, "'bins' must be a whole number from 2"),
    ({"bins": 2.5}, "'bins' must be a whole number"),
    ({"distance": "kl"}, "'distance' is one of"),
    ({"distance": 3}, "a measure's name or a function"),
    ({"distance_threshold": -1}, "'distance_threshold' must be a number of 0 or more"),
    ({"columns": ["nope"]}, "no dataset has 'nope'"),
    ({"columns": "age"}, "a list of column names"),
])
def test_wrong_options_say_what_to_pass(kwargs: dict[str, t.Any], message: str) -> None:
    options: dict[str, t.Any] = {"datasets": {"train": _A, "test": _B}, **kwargs}
    with pytest.raises(bf.BriefingError, match=message):
        bf.lab.DataCompare(**options)


# ── the JSON form ─────────────────────────────────────────────────────────────


def test_each_dataset_is_its_own_reference_or_table() -> None:
    report = bf.Briefing(_block(sort="distance", name="drift"))
    spec, data = bf.to_spec(report)
    assert spec["blocks"][0]["datasets"] == {"train": {"ref": "drift-train"}, "test": {"ref": "drift-test"}}
    assert set(data) == {"drift-train", "drift-test"}
    inline, nothing = bf.to_spec(report, inline=True)
    assert nothing == {} and set(inline["blocks"][0]["datasets"]["test"]) >= {"columns", "rows"}
    now = dt.datetime(2026, 1, 1)
    assert bf.stringify(bf.from_spec(json.dumps(inline)), now=now) == bf.stringify(report, now=now)


def test_a_function_of_your_own_goes_by_reference() -> None:
    def gap(p: t.Any, q: t.Any) -> float:
        return float(np.max(np.abs(p - q)))

    spec, data = bf.to_spec(bf.Briefing(_block(distance=gap)))
    ref = spec["blocks"][0]["distance"]["ref"]
    assert data[ref] is gap


def test_validate_explains_the_datasets_it_wants() -> None:
    wrong = {"briefing": 1, "blocks": [{"type": "lab.DataCompare", "datasets": [{"ref": "a"}]}]}
    [error] = [d for d in bf.validate(wrong) if d.severity == "error"]
    assert error.code == "wrong-type" and '{"<dataset>": a table' in error.message
    datasets = {"a": {"ref": "a"}, "b": {"ref": "x"}}
    missing = {"briefing": 1, "blocks": [{"type": "lab.DataCompare", "datasets": datasets}]}
    codes = [d.code for d in bf.validate(missing, data={"a": _A})]
    assert "unknown-ref" in codes
