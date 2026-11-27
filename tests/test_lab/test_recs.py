"""RecInspector (#18): fixed columns, models and users from recs, a summary per model, one user at a time."""
from __future__ import annotations

import json
import typing as t
import warnings

import pandas as pd
import pytest

import briefing as bf
from briefing.lab import _recs
from tests.golden import static_files
from tests.html_helpers import attr, classes, find_one, parse
from tests.scenarios import _recs_frames

_RECS_JS = static_files()["lab/static/recs.js"]
_RECS_CSS = static_files()["lab/static/recs.css"]


def _history(**columns: list[t.Any]) -> pd.DataFrame:
    base: dict[str, t.Any] = {"user": ["a", "a"], "item": ["x", "y"],
                              "timestamp": pd.to_datetime(["2026-01-01", "2026-01-02"])}
    return pd.DataFrame({**base, **columns})


def _recs_frame(**columns: list[t.Any]) -> pd.DataFrame:
    base: dict[str, list[t.Any]] = {"user": ["a", "a"], "item": ["y", "z"], "rank": [1, 2], "model": ["m", "m"]}
    return pd.DataFrame({**base, **columns})


def _soup(block: bf.lab.RecInspector) -> t.Any:
    return parse(bf.stringify(bf.Briefing(block)))


# ── the columns ───────────────────────────────────────────────────────────────


def test_a_missing_column_is_named_with_the_rename_that_fixes_it() -> None:
    recs = _recs_frame().rename(columns={"user": "user_id"})
    with pytest.raises(bf.BriefingError) as error:
        bf.lab.RecInspector(history=_history(), recs=recs)
    message = str(error.value)
    assert "'recs' needs the columns user, item, rank, model; it has user_id, item, rank, model" in message
    assert "recs.rename(columns={'user_id': 'user'})" in message


@pytest.mark.parametrize(("argument", "frame"), [
    ("history", _history().drop(columns="timestamp")),
    ("items", pd.DataFrame({"item": ["x"]})),
])
def test_each_frame_has_its_columns(argument: str, frame: pd.DataFrame) -> None:
    kwargs: dict[str, t.Any] = {"history": _history(), "recs": _recs_frame(), argument: frame}
    with pytest.raises(bf.BriefingError, match=f"'{argument}' needs the columns"):
        bf.lab.RecInspector(**kwargs)


def test_other_columns_are_ignored() -> None:
    plain = bf.lab.RecInspector(history=_history(), recs=_recs_frame())
    extra = bf.lab.RecInspector(history=_history(rating=[1, 2]), recs=_recs_frame(score=[0.9, 0.1]))
    assert extra.inspection == plain.inspection


def test_ids_match_as_text_across_frames() -> None:
    history = pd.DataFrame({"user": [1.0], "item": [7], "timestamp": [3]})
    recs = pd.DataFrame({"user": ["1"], "item": ["7"], "rank": [1], "model": ["m"]})
    inspection = bf.lab.RecInspector(history=history, recs=recs).inspection
    assert inspection.summary[0].seen == 1.0
    assert [u.id for u in inspection.users] == ["1"]


@pytest.mark.parametrize(("recs", "match"), [
    (_recs_frame(rank=["1", "2"]), "column 'rank' holds numbers"),
    (_recs_frame(rank=[True, False]), "column 'rank' holds numbers"),
    (_recs_frame(rank=[1.0, float("nan")]), "1 rank missing or infinite"),
    (_recs_frame(user=["a", None]), "1 row without a user; drop them first"),
    (_recs_frame(model=[None, None]), "2 rows without a model"),
    (_recs_frame().iloc[:0], "'recs' is empty"),
])
def test_recs_must_be_complete(recs: pd.DataFrame, match: str) -> None:
    with pytest.raises(bf.BriefingError, match=match):
        bf.lab.RecInspector(history=_history(), recs=recs)


def test_more_than_100_users_is_an_error_that_says_to_sample() -> None:
    users = [f"u{i}" for i in range(101)]
    recs = pd.DataFrame({"user": users, "item": ["x"] * 101, "rank": [1] * 101, "model": ["m"] * 101})
    with pytest.raises(bf.BriefingError, match="up to 100 users; 'recs' has 101. Sample them"):
        bf.lab.RecInspector(history=_history(), recs=recs)
    bf.lab.RecInspector(history=_history(), recs=recs.iloc[:100])


def test_more_than_4_models_is_an_error() -> None:
    recs = _recs_frame(user=["a"] * 5, item=["x"] * 5, rank=[1] * 5, model=list("abcde"))
    with pytest.raises(bf.BriefingError, match="up to 4 models side by side; 'recs' has 5"):
        bf.lab.RecInspector(history=_history(), recs=recs)


def test_the_limits_are_the_classs() -> None:
    assert (bf.lab.RecInspector.MAX_USERS, bf.lab.RecInspector.MAX_MODELS) == (_recs.MAX_USERS, _recs.MAX_MODELS)


# ── users, histories and lists ────────────────────────────────────────────────


def test_models_and_users_come_from_recs_in_order() -> None:
    inspection = bf.lab.RecInspector(**_recs_frames()).inspection
    assert inspection.models == ["base", "new", "third"]
    assert [u.id for u in inspection.users] == ["ana", "ben", "eve"]  # dee: history only


def test_history_is_most_recent_first_ties_in_order_undated_last() -> None:
    history = pd.DataFrame({
        "user": ["a"] * 4, "item": ["old", "tie1", "none", "tie2"],
        "timestamp": [pd.Timestamp("2026-01-01"), pd.Timestamp("2026-02-01"), pd.NaT, pd.Timestamp("2026-02-01")],
    })
    inspection = bf.lab.RecInspector(history=history, recs=_recs_frame()).inspection
    order = [(inspection.items[i], when) for i, when in inspection.users[0].history]
    assert order == [("tie1", "2026-02-01"), ("tie2", "2026-02-01"), ("old", "2026-01-01"), ("none", "")]


def test_a_history_that_does_not_sort_is_an_error() -> None:
    history = _history(timestamp=[1, "yesterday"])
    with pytest.raises(bf.BriefingError, match="must hold values that sort together"):
        bf.lab.RecInspector(history=history, recs=_recs_frame())


def test_lists_follow_rank_whatever_the_rows_order() -> None:
    recs = _recs_frame(user=["a"] * 3, item=["third", "first", "half"], rank=[3, 1, 2.5], model=["m"] * 3)
    inspection = bf.lab.RecInspector(history=_history(), recs=recs).inspection
    [rows] = inspection.users[0].lists
    assert rows is not None
    assert [(inspection.items[i], rank) for i, rank in rows] == [("first", "1"), ("half", "2.5"), ("third", "3")]


def test_the_summary_on_the_scenario() -> None:
    summary = {row.model: row for row in bf.lab.RecInspector(**_recs_frames()).inspection.summary}
    base, new, third = summary["base"], summary["new"], summary["third"]
    assert (base.users, base.recs, base.items) == (3, 7, 6)
    assert base.seen == pytest.approx(1 / 7)  # ana had seen i2
    assert base.coverage == pytest.approx(6 / 9)  # i1…i9: history, lists and catalogue
    assert base.popularity == 1.0 and new.popularity == 0.0
    assert base.overlap == {"new": pytest.approx((1 / 3 + 1 / 2) / 2), "third": pytest.approx(1 / 3)}
    assert third.overlap == {"base": 1.0, "new": 0.0}


def test_two_models_no_user_has_both_of_have_no_overlap() -> None:
    recs = _recs_frame(user=["a", "b"], model=["m", "n"])
    block = bf.lab.RecInspector(history=_history(), recs=recs)
    assert block.inspection.summary[0].overlap == {"n": None}
    assert "n —" in find_one(_soup(block), ".bf-recs__summary tbody").get_text()


# ── the HTML ──────────────────────────────────────────────────────────────────


def test_the_first_user_is_drawn_with_seen_and_shared_marks() -> None:
    soup = _soup(bf.lab.RecInspector(**_recs_frames()))
    section = find_one(soup, ".bf-recs__user")
    assert find_one(section, ".bf-recs__user-id").get_text() == "ana"
    base = find_one(section, '.bf-recs__model[data-k="0"]')
    marks = [(attr(li, "data-item"), [m.get_text() for m in li.select(".bf-recs__mark")])
             for li in base.select("li")]
    assert marks == [("i4", ["shared"]), ("i2", ["seen"]), ("i5", ["shared"])]
    assert "bf-recs__item--seen" in classes(base.select("li")[1])
    assert find_one(base, ".bf-recs__mark--shared")["title"] == "Also recommended by third"


def test_an_item_without_a_title_shows_its_id_and_the_switch_shows_ids() -> None:
    soup = _soup(bf.lab.RecInspector(**_recs_frames()))
    untitled = find_one(soup, '.bf-recs__strip [data-item="i3"]')
    assert untitled.select(".bf-recs__title") == [] and find_one(untitled, ".bf-recs__id").get_text() == "i3"
    assert attr(find_one(soup, ".bf-recs"), "data-show") == "titles"
    assert [b.get_text() for b in soup.select(".bf-recs__show")] == ["titles", "ids"]


def test_without_items_there_is_no_switch() -> None:
    soup = _soup(bf.lab.RecInspector(history=_history(), recs=_recs_frame()))
    assert soup.select(".bf-recs__show, .bf-recs__title") == []
    assert find_one(soup, ".bf-recs").get("data-show") is None


def test_a_user_without_history_or_without_a_list_says_so() -> None:
    recs = _recs_frame(user=["nobody", "a"], model=["m", "other"])
    soup = _soup(bf.lab.RecInspector(history=_history(), recs=recs))
    section = find_one(soup, ".bf-recs__user")
    assert [p.get_text() for p in section.select(".bf-recs__none")] == ["No history.", "No list."]


def test_one_model_has_no_overlap() -> None:
    soup = _soup(bf.lab.RecInspector(history=_history(), recs=_recs_frame()))
    assert "overlap" not in [th.get_text() for th in soup.select(".bf-recs__summary th")]


def test_the_data_holds_each_item_once() -> None:
    block = bf.lab.RecInspector(**_recs_frames())
    data = json.loads(find_one(_soup(block), "script.bf-recs__data").get_text())
    assert [item[0] for item in data["items"]] == ["i2", "i3", "i1", "i4", "i5", "i6", "i7", "i8"]
    assert data["items"][1] == ["i3", None, 1]
    assert [u["id"] for u in data["users"]] == ["ana", "ben", "eve"]
    assert data["users"][2]["lists"][1] is None  # eve: no list from "new"


def test_items_listed_twice_keep_their_first_title_and_warn() -> None:
    items = pd.DataFrame({"item": ["y", "y"], "title": ["First", "Second"]})
    with pytest.warns(UserWarning, match=r"more than once \('y'\); each keeps its first title"):
        block = bf.lab.RecInspector(history=_history(), recs=_recs_frame(), items=items)
    assert block.inspection.titles[block.inspection.items.index("y")] == "First"


def test_the_script_and_styles_ship_only_with_an_inspector() -> None:
    plain = bf.stringify(bf.Briefing(bf.lab.DataProfile(_history())))
    assert _RECS_JS not in plain and _RECS_CSS not in plain
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        html = bf.stringify(bf.Briefing(bf.lab.RecInspector(history=_history(), recs=_recs_frame()),
                                        bf.lab.RecInspector(history=_history(), recs=_recs_frame())))
    assert html.count(_RECS_JS) == 1 and html.count(_RECS_CSS) == 1
